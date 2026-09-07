#!/usr/bin/env python3
"""【我(Claude)当 verifier + 真实 harness】12 条扩测驱动脚本（分离实验 Part 2）。

同 me_verifier_harness.py 机制：我既当策略又当 verifier，检索真实 BM25，harness 门禁全真实。
本版批处理 12 条：逐条 search→open(命中含 gold 的正确 docid)→update_state(gold)→verify→submit。
verify 用「回填式 MyVerifier」：每次 verify 把 (question,answer,evidence原文) 写成
  /tmp/meverify_v/meverify_<qid>_r<k>.prompt.json
由我读后写 <k>.verdict.json 判定，脚本读回填进 env。所有门禁(coverage/stale/已验证/submit路径)全真实。

相较 q324 pilot 的关键修正：
- 为每条提供【已验证含 gold 的 docid】候选（5 条 strongA 真阳性原本 open 到不含 gold 的 doc，必须换正确 doc，
  否则连正确 verifier 也无正当证据支撑）。
- read_evidence 放在 update_state 登记新 eid 之后，避免脚本顺序误触 "requires Evidence ID in directory"。
- 逐条(而非全批统一)等方式推进，每轮最多到 N rounds；缺 verdict 则等待(脚本幂等可重跑续行)。

CASE 表 docid_cands 中的第一个含 gold（已用 BM25 实证）。脚本优先在 search hits 里选中它。
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

# 12 条：qid -> (gold_answer, 含 gold 的 docid 候选[首个实证含gold], 初始检索词)
CASES = {
    "186": ("Galacta: The Battle for Saturn",
            ["39978", "2855", "22411", "3079"],
            "Galacta Battle for Saturn Froggo 1991 shareware DOS"),
    "56": ("Last Christmas",
            ["17156"],
            "Last Christmas ReFrame Stamp 2018 2023 festival movie"),
    "1041": ("Adaku",
            ["61696"],
            "Adaku Bonang TV presenter Revlon radio Africa"),
    "1089": ("Zius Galit",
            ["86834"],
            "Zius Galit song anthem pandemic parody"),
    "1198": ("Robert Mugabe",
            ["83077"],
            "Robert Mugabe first Prime Minister landlocked country"),
    "324": ("Svetlana Gromenkova",
            ["85213"],
            "Svetlana Gromenkova poker champion 2008 World Series of Poker ladies"),
    "364": ("Bada Lee",
            ["47063"],
            "Bada Lee Street Woman Fighter smoke choreographer"),
    "391": ("María Constanza Guzmán",
            ["22666"],
            "María Constanza Guzmán interviewer Hispanic Studies archive"),
    "517": ("Peter King",
            ["67431"],
            "Peter King 2005 policeman Iracema Kinsey"),
    "636": ("2011",
            ["19992"],
            "2011 heritage plaque foundation renamed Simon van der Stel"),
    "772": ("Secretary",
            ["93372"],
            "school longest serving employee secretary church dancers township"),
    "83": ("Joseph Dalton Hooker",
            ["39837"],
            "Joseph Dalton Hooker yerba type divination harsh stones"),
}

MAX_ROUNDS_DEFAULT = 3


class MyVerifier:
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
        if verdict_path.exists():
            verdict_path.unlink()
        deadline = time.time() + 3600  # 后台等待我回填；可重跑续行
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
                return VerificationResult(VerificationStatus.NEEDS_REVISION,
                                          gaps or ("当前答案未通过校验",), rationale)
            time.sleep(0.5)
        raise TimeoutError(f"verdict not provided within 3600s: {verdict_path}")


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


def run_one(dataset, qid, gold, docid_cands, query, store, max_rounds):
    question = load_question(dataset, qid)
    if not question:
        return {"qid": qid, "error": "query not found"}
    if os.path.exists(store):
        os.remove(store)
    retriever = EchoRetrievalClient(RETRIEVAL_URL)
    verifier = MyVerifier(qid)
    env = ESREnvironment(question, retriever, verifier, store_path=store)
    cursor = 0
    def span(n=3):
        nonlocal cursor
        s = [{"segment_index": 0, "start": cursor, "end": cursor + n}]
        cursor += n
        return s
    turn = 0
    opened_docids = set()
    opened_eids = []
    outcome = None
    actions = []
    def act(name, **kw):
        nonlocal turn
        turn += 1
        try:
            return getattr(env, name)(**kw, token_spans=span(), turn_id=f"t{turn}")
        except Exception as exc:
            return {"__reject__": str(exc)}

    cur_query = query
    for rnd in range(max_rounds):
        s = act("search", query=cur_query, top_k=20)
        if not s or "__reject__" in s:
            return {"qid": qid, "stage": f"search_r{rnd}", "error": s}
        hits = [str(h["docid"]) for h in s["results"]]
        actions.append(("search", s["action_id"], "ok"))
        # 优先含 gold 的候选（未开过的）
        docid = next((d for d in docid_cands if d in hits and d not in opened_docids), None)
        if docid is None:
            docid = next((d for d in docid_cands if d not in opened_docids), None)  # 候选本身可能不在 hits,仍尝试
        if docid is None:
            docid = next((d for d in hits if d not in opened_docids), None)
        if docid is None:
            return {"qid": qid, "stage": "no_new_doc", "opened": list(opened_docids)}
        page = act("open_page", docid=docid, search_action_id=s["action_id"])
        if not page or "__reject__" in page:
            return {"qid": qid, "stage": f"open_r{rnd}", "error": page}
        eid = page["evidence_id"]
        opened_docids.add(docid)
        opened_eids.append(eid)
        actions.append(("open_page", page["action_id"], docid))
        # update_state（先登记 eid，read_evidence 才在 directory 里）
        findings = [{"evidence_id": e, "finding": f"supports {gold}."} for e in opened_eids]
        u = act("update_state", answer=gold, evidence_findings=findings,
                supporting_evidence=opened_eids)
        if u and "__reject__" in u:
            return {"qid": qid, "stage": f"update_r{rnd}", "error": u}
        # read_evidence（现在 eid 已在 directory）
        rd = act("read_evidence", evidence_id=eid)
        if rd and "__reject__" in rd:
            actions.append(("read_evidence", None, f"reject:{rd['__reject__'][:60]}"))
        else:
            actions.append(("read_evidence", rd.get("action_id"), "ok"))
        # verify —— MyVerifier 等我回填
        v = act("verify_answer")
        if not v or "__reject__" in v:
            return {"qid": qid, "stage": f"verify_r{rnd}", "error": v}
        vstatus = v.get("verification_status")
        gaps = [g.get("description") for g in v.get("gaps", [])]
        sys.stderr.write(json.dumps({"qid": qid, "round": rnd, "opened": list(opened_docids),
                                     "verify": vstatus, "n_gaps": len(gaps)}, ensure_ascii=False) + "\n")
        if vstatus == "supported":
            sb = act("submit_answer")
            if sb and "__reject__" not in sb:
                outcome = "submitted"
            else:
                outcome = "blocked_submit"
                actions.append(("submit", None, str(sb)))
            break
        # needs_revision：下轮用含 gold 候选再开一篇 or 停在当前
        # 这里简化：若 t1 就有 gold 但仍拒，那就是 verifier 仍不给过 → 停在 needs_revision 等终止
        cur_query = query + " evidence"

    return {"qid": qid, "gold": gold, "outcome": outcome or "needs_revision",
            "turns": turn, "opened": list(opened_docids), "verify_rounds": verifier.round,
            "final_verify": vstatus if 'vstatus' in locals() else None,
            "final_gaps": gaps if 'gaps' in locals() else [],
            "supports": opened_eids}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--qids", nargs="*", default=list(CASES.keys()),
                    help="要跑的 qid 列表；缺省全部 12 条")
    ap.add_argument("--max-rounds", type=int, default=MAX_ROUNDS_DEFAULT)
    ap.add_argument("--out", default="/data1/ESR-GRPO-Code-L/analysis-L/mev_12_result.json")
    args = ap.parse_args()

    results = []
    for qid in args.qids:
        if qid not in CASES:
            print(f"skip unknown {qid}", flush=True)
            continue
        gold, docids, query = CASES[qid]
        store = f"/tmp/mev_{qid}.db"
        print(f"== meV {qid} ({gold!r}) round<= {args.max_rounds} docid_cands={docids}", flush=True)
        try:
            r = run_one(args.dataset, qid, gold, docids, query, store, args.max_rounds)
            results.append(r)
            print(f"   -> {r.get('outcome')} verify={r.get('final_verify')} opened={r.get('opened')} "
                  f"gaps={len(r.get('final_gaps', []))}", flush=True)
        except Exception as ex:
            results.append({"qid": qid, "gold": gold, "error": str(ex)})
            print(f"   !! {ex}", flush=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()