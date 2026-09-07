#!/usr/bin/env python3
"""【我(Claude)当 verifier + 真实 harness】分离实验驱动脚本。

目标：彻底把 harness 层 与 4B 模型能力层分开。
- 策略：脚本按强策略(我设计的动作序列)推进，同样经过真实门禁
- verifier：不再走 4B 服务(OpenAICompatibleVerifier:8005)，
  而是「回填式」MyVerifier —— verify 时把 (question,answer,evidence原文) 写成 prompt 文件，
  由我(外部强能力)读后写入 verdict 文件判定 supported/needs_revision+gaps，
  脚本读回填进 ESREnvironment.verifier。所有 env 门禁(coverage/stale/已验证/submit路径)仍全真实执行。
- retriever：真实 BM25 EchoRetrievalClient(:8000)
- environment：真实 ESREnvironment

若「我当verifier」能顺利 supported→submit 且门禁全部正常放行/拦截，则证明 harness 链路本身完美、卡死全在4B；
若这样还卡死，才能定位为 harness 真缺陷。

用法：
  python me_verifier_harness.py --query-id 324 --dataset ... --store /tmp/mev_324.db [--max-rounds 8]
每轮 verify 会产生 /tmp/meverify_<qid>_r<k>.prompt.json，我判后写 /tmp/meverify_<qid>_r<k>.verdict.json：
  {"verification_status":"supported|needs_revision","gaps":[...],"rationale":"..."}
脚本自动读取继续；缺 verdict 文件则等待(可轮询或手动分次)。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from esr_grpo.environment import ESREnvironment
from esr_grpo.retrieval import EchoRetrievalClient
from esr_grpo.models import Evidence, VerificationResult, VerificationStatus

RETRIEVAL_URL = "http://127.0.0.1:8000"
VERDICT_DIR = "/tmp/meverify_v"
BUDGET = 480_000


class MyVerifier:
    """回填式 verifier：把判定请求写到磁盘，由外部强能力(我)读后回填。"""

    def __init__(self, qid: str, workdir: str = VERDICT_DIR):
        self.qid = qid
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.round = 0

    def verify(self, question: str, answer: str, evidence: Sequence[Evidence]) -> VerificationResult:
        self.round += 1
        tag = f"meverify_{self.qid}_r{self.round}"
        prompt_path = self.workdir / f"{tag}.prompt.json"
        verdict_path = self.workdir / f"{tag}.verdict.json"
        # 构造与 OpenAICompatibleVerifier 相同的观察(evidence 原文)
        segs = []
        total = 0
        for it in evidence:
            content = it.content
            if len(content) > 60_000:
                content = content[:60_000]
            seg = f"[{it.evidence_id}] {it.source.title}\n{content}"
            if total + len(seg) > BUDGET:
                return VerificationResult(
                    VerificationStatus.NEEDS_REVISION,
                    ("被引用原始证据过长超出预算,请精简 supporting_evidence 后重新验证",),
                    "referenced evidence exceeds budget")
            segs.append(seg)
            total += len(seg)
        evidence_text = "\n\n".join(segs) if segs else "(无可用证据)"
        payload = {
            "qid": self.qid,
            "verify_id": tag,
            "question": question,
            "answer": answer,
            "evidence_ids": [it.evidence_id for it in evidence],
            "evidence_text": evidence_text,
        }
        prompt_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        # 清掉旧的/无关 verdict
        if verdict_path.exists():
            verdict_path.unlink()
        # 等待外部回填(最多 wait 秒)；用存在性+内容合法做判据
        deadline = time.time() + 600
        while time.time() < deadline:
            if verdict_path.exists():
                try:
                    v = json.loads(verdict_path.read_text(encoding="utf-8"))
                except Exception:
                    time.sleep(0.5)
                    continue
                status = v.get("verification_status")
                if status not in ("supported", "needs_revision"):
                    raise ValueError(f"bad verdict status {status!r}")
                gaps = tuple(str(g).strip() for g in v.get("gaps", []) if str(g).strip())
                rationale = str(v.get("rationale", ""))
                if status == "supported":
                    return VerificationResult(VerificationStatus.SUPPORTED, (), rationale)
                return VerificationResult(VerificationStatus.NEEDS_REVISION, gaps or ("当前答案未通过校验",), rationale)
            time.sleep(0.5)
        raise TimeoutError(f"verdict not provided within 600s: {verdict_path}")


def load_question(dataset: str, qid: str) -> str:
    with open(dataset, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(rec.get("query_id")) == str(qid):
                return rec.get("query", rec.get("question", ""))
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--query-id", required=True)
    ap.add_argument("--store", required=True)
    ap.add_argument("--answer", help="gold answer（强策略已知），缺省时从 prompt 回填")
    ap.add_argument("--max-rounds", type=int, default=8)
    args = ap.parse_args()

    question = load_question(args.dataset, args.query_id)
    if not question:
        print(json.dumps({"error": f"query {args.query_id} not found"})); sys.exit(2)

    store = Path(args.store)
    if store.exists():
        store.unlink()
    retriever = EchoRetrievalClient(RETRIEVAL_URL)
    verifier = MyVerifier(args.query_id)
    env = ESREnvironment(question, retriever, verifier, store_path=str(store))

    cursor = 0
    def span(n: int = 3) -> list:
        nonlocal cursor
        s = [{"segment_index": 0, "start": cursor, "end": cursor + n}]
        cursor += n
        return s

    # 强策略动作序列：每轮 search→open(命中正确docid)→read_evidence→update_state→verify
    # 这里由脚本(我设计的策略)驱动，动作同真实批量，门禁全走 env。
    # 待验证 docid 候选（与 strongA 一致的实际命中文档）
    docid_cands = ["24297", "85213", "42885", "61674", "62272", "93649", "4649"]
    queries = [
        "Svetlana Gromenkova poker champion 2008 World Series of Poker ladies",
        "Svetlana Gromenkova sibling piano learned to play",
        "Svetlana Gromenkova third tournament nurse animal rights film",
        "World Series of Poker 2008 final table ladies champion",
        "Svetlana Gromenkova web design 2009 2015 winnings",
    ]
    gold = args.answer or "Svetlana Gromenkova"

    turn = 0
    opened: set[str] = set()
    opened_eids: list[str] = []
    outcome = None
    actions_log = []

    def act(name, **kw):
        nonlocal turn
        turn += 1
        try:
            r = getattr(env, name)(**kw, token_spans=span(), turn_id=f"t{turn}")
            return r
        except Exception as exc:
            return {"__reject__": str(exc)}

    for rnd in range(args.max_rounds):
        q = queries[rnd] if rnd < len(queries) else queries[-1]
        # 1) search
        s = act("search", query=q)
        if not s or "__reject__" in s:
            print(json.dumps({"qid": args.query_id, "round": rnd, "stage": "search",
                              "rejected": s}, ensure_ascii=False)); outcome = "blocked"; break
        hits = [str(h["docid"]) for h in s["results"]]
        actions_log.append(("search", s.get("action_id"), "ok"))
        # 2) open：优先已命中的已知正确doc，否则新未开过doc
        docid = next((d for d in docid_cands if d in hits and d not in opened), None)
        if docid is None:
            docid = next((d for d in hits if d not in opened), None)
        if docid is None:
            print(json.dumps({"qid": args.query_id, "round": rnd, "stage": "no_new_doc",
                              "hits": hits, "opened": list(opened)}, ensure_ascii=False))
            outcome = "no_new_doc"; break
        page = act("open_page", docid=docid, search_action_id=s["action_id"])
        if not page or "__reject__" in page:
            print(json.dumps({"qid": args.query_id, "round": rnd, "stage": "open",
                              "rejected": page}, ensure_ascii=False)); outcome = "blocked"; break
        eid = page["evidence_id"]
        opened.add(docid)
        opened_eids.append(eid)
        actions_log.append(("open_page", page.get("action_id"), docid))
        # 3) read_evidence 新 eid
        rd = act("read_evidence", evidence_id=eid)
        if rd and "__reject__" in rd:
            actions_log.append(("read_evidence", None, f"reject:{rd['__reject__'][:60]}"))
        # 4) update_state，supporting=全部已开 eid，固定 finding 文案
        findings = [{"evidence_id": e, "finding": f"supports {gold}."} for e in opened_eids]
        u = act("update_state", answer=gold, evidence_findings=findings,
                supporting_evidence=opened_eids)
        if u and "__reject__" in u:
            print(json.dumps({"qid": args.query_id, "round": rnd, "stage": "update",
                              "rejected": u}, ensure_ascii=False)); outcome = "blocked"; break
        # 5) verify —— 这里走 MyVerifier，等我回填
        v = act("verify_answer")
        if not v or "__reject__" in v:
            print(json.dumps({"qid": args.query_id, "round": rnd, "stage": "verify",
                              "rejected": v}, ensure_ascii=False)); outcome = "blocked"; break
        vstatus = v.get("verification_status")
        gaps = [g.get("description") for g in v.get("gaps", [])]
        print(json.dumps({"qid": args.query_id, "round": rnd, "opened": list(opened),
                          "verify": vstatus, "gaps": gaps}, ensure_ascii=False, default=str))
        if vstatus == "supported":
            sb = act("submit_answer")
            if sb and "__reject__" not in sb:
                outcome = "submitted"
                print(json.dumps({"qid": args.query_id, "round": rnd, "outcome": "SUBMITTED",
                                  "submitted": sb.get("submitted_answer")}, ensure_ascii=False))
                break
            else:
                print(json.dumps({"qid": args.query_id, "round": rnd, "stage": "submit",
                                  "rejected": sb}, ensure_ascii=False)); outcome = "blocked_submit"; break

    # 收尾
    summary = {
        "query_id": args.query_id,
        "outcome": outcome or "max_rounds",
        "turns": turn,
        "opened_docids": list(opened),
        "verify_rounds": verifier.round,
        "actions": [a if a else None for a in actions_log],
    }
    print(json.dumps({"final": summary}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()