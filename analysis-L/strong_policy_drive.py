#!/usr/bin/env python3
"""强策略(我)标准评测 12 条 —— 单局回填驱动（ESR vs baseline 双模式）。

职责：用【我(Claude)】作为唯一策略模型，驱动一个真实 ESREnvironment 跑完一局；
不给 gold（标准评测），max_turns=50，检索选 docid 只从 search hits 里诚实挑选。

与 drive_harness.py 的差别：
  - 交互从「stdin 实时 JSON」改为「文件回填」：脚本把当前上下文写 .ctx.json，等我写 .act.json。
  - 支持双模式 mode={esr,baseline}；baseline 以 finish(answer) 收尾（无 ESR 门禁），
    只暴露 search/open_page/read_evidence/finish 四工具。
  - ESR 的 verify 判定由【我】回填（仿 me_verifier_batch 的 MyVerifier 回填协议），
    不使用任何本地/外部模型作策略或 verifier。
  - 全程深保证：gold / gold_docs / gold docid 绝不进 .ctx.json。

文件协议（单局，workdir 下以 <tag>=<qid>_<mode> 为前缀）：
  策略通道（我推进下一动作）:
    <tag>.ctx.json  状态机回填：question + hits + 已开证据 + task_state + allowed_actions
    <tag>.act.json  我写：{"action": ..., ...}（见 STRATEGY_ACTIONS）
  裁判通道（ESR verify 由我判）:
    <tag>.r<k>.prompt.json   脚本写 (question, answer, evidence) 求我判
    <tag>.r<k>.verdict.json  我写 {"verification_status": ..., "gaps":[...], "rationale":...}

终止：ESR 成功 submit_answer / baseline 成功 finish / turn>=max_turns / 无新 act 且退出。
幂等：缺 act 只写 ctx 等待；重跑同 store 默认清空重来（--keep-store 保留续行）。
每动作结果（含 rejected/legal）写入动作历史，供我复盘。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Sequence

from esr_grpo.environment import ESREnvironment, ActionKind
from esr_grpo.retrieval import EchoRetrievalClient
from esr_grpo.models import Evidence, VerificationResult, VerificationStatus, to_primitive

RETRIEVAL_URL = "http://127.0.0.1:8000"

STRATEGY_ACTIONS = {
    "esr": ["search", "open_page", "read_evidence", "update_state", "verify_answer", "submit_answer"],
    "baseline": ["search", "open_page", "read_evidence", "finish"],
}

# verify 裁判回填的每轮证据字符预算（超长会被 needs_revision 打回，逼精简 supporting）
BUDGET = 480_000


class MyVerifier:
    """回填式 verifier：每次 verify 把 (question, answer, evidence) 写 .prompt.json，
    等我写 .verdict.json 判定（supported / needs_revision + gaps）。"""

    def __init__(self, tag: str, workdir: Path, timeout: float = 43200.0):
        self.tag = tag
        self.workdir = workdir
        self.timeout = timeout
        self.round = 0

    def verify(self, question: str, answer: str, evidence: Sequence[Evidence]) -> VerificationResult:
        self.round += 1
        tag = f"{self.tag}.r{self.round}"
        prompt_path = self.workdir / f"{tag}.prompt.json"
        verdict_path = self.workdir / f"{tag}.verdict.json"
        segs, total = [], 0
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
        payload = {
            "qid": self.tag.split("_")[0],
            "mode": self.tag.split("_")[1],
            "verify_id": tag,
            "question": question,
            "answer": answer,
            "evidence_ids": [it.evidence_id for it in evidence],
            "evidence_text": "\n\n".join(segs) if segs else "(无可用证据)",
        }
        prompt_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if verdict_path.exists():
            verdict_path.unlink()
        deadline = time.time() + self.timeout
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
        raise TimeoutError(f"verdict not provided within {self.timeout}s: {verdict_path}")


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


def _hits_primitive(results) -> list[dict]:
    """把 search 返回的 hits 收敛成「策略只从这里选 docid」的诚实简表。"""
    out = []
    for i, h in enumerate(results):
        docid = str(h.get("docid"))
        if not docid:
            continue
        out.append({
            "rank": i,
            "docid": docid,
            "title": str(h.get("title", ""))[:200],
            "snippet": str(h.get("snippet", h.get("text", "")))[:400],
        })
    return out


class EpisodeDriver:
    def __init__(self, *, dataset, qid, mode, store, workdir, max_turns, search_top_k):
        self.qid = qid
        self.mode = mode
        self.tag = f"{qid}_{mode}"
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.max_turns = max_turns
        self.search_top_k = search_top_k

        question = load_question(dataset, qid)
        if not question:
            raise SystemExit(f"query {qid} not found in {dataset}")
        self.question = question

        store_path = Path(store)
        if store_path.exists():
            store_path.unlink()
        self.retriever = EchoRetrievalClient(RETRIEVAL_URL)
        self.verifier = MyVerifier(self.tag, self.workdir)
        self.env = ESREnvironment(question, self.retriever, self.verifier, store_path=str(store))

        self.cursor = 0
        self.turn = 0
        self.hits = []                # 最近一次 search 的 hits 简表
        self.last_search_action_id = None
        self.actions = []             # 已执行动作摘要（含被拒）
        self.opened_evidence = []     # [{evidence_id, docid, title, content, truncated}]

    def span(self, n: int = 3) -> list:
        s = [{"segment_index": 0, "start": self.cursor, "end": self.cursor + n}]
        self.cursor += n
        return s

    # ---------- 动作执行（真实门禁） ----------
    def exec_search(self, query: str) -> dict:
        self.turn += 1
        r = self.env.search(query, top_k=self.search_top_k, token_spans=self.span(), turn_id=f"t{self.turn}")
        self.hits = _hits_primitive(r["results"])
        self.last_search_action_id = r["action_id"]
        self.actions.append({"turn": f"t{self.turn}", "kind": "search",
                             "query": query, "hits": len(self.hits),
                             "action_id": r["action_id"]})
        return {"ok": True, "turn": f"t{self.turn}", "action_id": r["action_id"]}

    def exec_open(self, docid: str, search_action_id: str | None) -> dict:
        self.turn += 1
        try:
            r = self.env.open_page(docid, search_action_id=search_action_id,
                                   token_spans=self.span(), turn_id=f"t{self.turn}")
        except Exception as exc:
            self.actions.append({"turn": f"t{self.turn}", "kind": "open_page_attempt",
                                 "docid": docid, "rejected": str(exc)[:300]})
            return {"ok": False, "turn": f"t{self.turn}", "rejected": str(exc)}
        eid = r["evidence_id"]
        src = r.get("source") or {}
        self.opened_evidence.append({
            "evidence_id": eid,
            "docid": str(src.get("docid", docid)),
            "title": str(src.get("title", ""))[:200],
            "content": r.get("content", ""),
            "truncated": r.get("truncated", False),
        })
        self.actions.append({"turn": f"t{self.turn}", "kind": "open_page",
                             "docid": docid, "evidence_id": eid})
        return {"ok": True, "turn": f"t{self.turn}", "evidence_id": eid}

    def exec_read(self, evidence_id: str) -> dict:
        self.turn += 1
        try:
            r = self.env.read_evidence(evidence_id, token_spans=self.span(), turn_id=f"t{self.turn}")
        except Exception as exc:
            self.actions.append({"turn": f"t{self.turn}", "kind": "read_evidence_attempt",
                                 "evidence_id": evidence_id, "rejected": str(exc)[:300]})
            return {"ok": False, "turn": f"t{self.turn}", "rejected": str(exc)}
        # 有被拒读之外，把最新内容也刷新进 opened_evidence（chunk 视图可能与 open 返回一致）
        self.actions.append({"turn": f"t{self.turn}", "kind": "read_evidence", "evidence_id": evidence_id})
        return {"ok": True, "turn": f"t{self.turn}", "content": r.get("content", "")}

    def exec_update(self, answer: str, findings: list, support: list) -> dict:
        self.turn += 1
        try:
            r = self.env.update_state(answer, findings, support,
                                      token_spans=self.span(), turn_id=f"t{self.turn}")
        except Exception as exc:
            self.actions.append({"turn": f"t{self.turn}", "kind": "update_state_attempt",
                                 "rejected": str(exc)[:300]})
            return {"ok": False, "turn": f"t{self.turn}", "rejected": str(exc)}
        self.actions.append({"turn": f"t{self.turn}", "kind": "update_state", "ok": True})
        return {"ok": True, "turn": f"t{self.turn}", "task_state": r.get("task_state")}

    def exec_verify(self) -> dict:
        self.turn += 1
        try:
            r = self.env.verify_answer(token_spans=self.span(), turn_id=f"t{self.turn}")
        except Exception as exc:
            self.actions.append({"turn": f"t{self.turn}", "kind": "verify_answer_attempt",
                                 "rejected": str(exc)[:300]})
            return {"ok": False, "turn": f"t{self.turn}", "rejected": str(exc)}
        status = r.get("verification_status")
        gaps = [g.get("description") for g in r.get("gaps", [])]
        self.actions.append({"turn": f"t{self.turn}", "kind": "verify_answer",
                             "verification_status": status, "n_gaps": len(gaps)})
        return {"ok": True, "turn": f"t{self.turn}", "verification_status": status,
                "gaps": gaps, "rationale": r.get("rationale")}

    def exec_submit(self) -> dict:
        self.turn += 1
        try:
            r = self.env.submit_answer(token_spans=self.span(), turn_id=f"t{self.turn}")
        except Exception as exc:
            self.actions.append({"turn": f"t{self.turn}", "kind": "submit_answer_attempt",
                                 "rejected": str(exc)[:300]})
            return {"ok": False, "turn": f"t{self.turn}", "rejected": str(exc)}
        self.actions.append({"turn": f"t{self.turn}", "kind": "submit_answer", "ok": True})
        return {"ok": True, "turn": f"t{self.turn}", "submitted_answer": self.env.submitted_answer}

    def exec_finish(self, answer: str) -> dict:
        self.turn += 1
        try:
            r = self.env.finish(answer, token_spans=self.span(), turn_id=f"t{self.turn}")
        except Exception as exc:
            self.actions.append({"turn": f"t{self.turn}", "kind": "finish_attempt",
                                 "rejected": str(exc)[:300]})
            return {"ok": False, "turn": f"t{self.turn}", "rejected": str(exc)}
        self.actions.append({"turn": f"t{self.turn}", "kind": "finish",
                             "answer": self.env.submitted_answer})
        return {"ok": True, "turn": f"t{self.turn}", "submitted_answer": self.env.submitted_answer}

    # ---------- 回填通道 ----------
    def write_ctx(self, done: bool) -> None:
        """写 .ctx.json 等我这步动作（done=True 表示已终止，等读 is_done 标志）。"""
        ctx = {
            "tag": self.tag,
            "mode": self.mode,
            "turn": self.turn,
            "max_turns": self.max_turns,
            "question": self.question,
            "allowed_actions": STRATEGY_ACTIONS[self.mode],
            "search_hits": self.hits,                 # 策略只能从这里面选 docid
            "last_search_action_id": self.last_search_action_id,
            "opened_evidence": [
                {"evidence_id": e["evidence_id"], "docid": e["docid"],
                 "title": e["title"], "truncated": e["truncated"],
                 "content": e["content"][:60_000]}   # 已开证据 chunk 视图，供强策略阅读推理
                for e in self.opened_evidence],
            "task_state": to_primitive(self.env.current_state) if self.env.current_state else None,
            "evidence_archive_count": len(self.env.store.list_evidence()),
            "action_history": self.actions[-20:],
            "done": done,
            "prompt_for_me": self._prompt_for_me(),
        }
        p = self.workdir / f"{self.tag}.ctx.json"
        p.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")
        # 清掉可能遗留的旧 act，要求新鲜决策
        ap = self.workdir / f"{self.tag}.act.json"
        if ap.exists() and done:
            ap.unlink()

    def _prompt_for_me(self) -> str:
        if self.mode == "baseline":
            return ("你已读取上下文。下一步从 allowed_actions 里选一个动作，写 act.json："
                    "{\"action\":\"search\",\"query\":...} | "
                    "{\"action\":\"open_page\",\"docid\":\"<search_hits里的docid>\",\"search_action_id\":...} | "
                    "{\"action\":\"read_evidence\",\"evidence_id\":...} | "
                    "{\"action\":\"finish\",\"answer\":\"<最终答案>\"}。"
                    "finish 会直接提交，请只在有把握给出最终答案时调用。")
        return ("你已读取上下文。下一步从 allowed_actions 里选一个动作，写 act.json："
                "{\"action\":\"search\",\"query\":...} | "
                "{\"action\":\"open_page\",\"docid\":\"<search_hits里的docid>\",\"search_action_id\":...} | "
                "{\"action\":\"read_evidence\",\"evidence_id\":...} | "
                "{\"action\":\"update_state\",\"answer\":\"<答案>\",\"evidence_findings\":[{\"evidence_id\":...,\"finding\":...}],"
                "\"supporting_evidence\":[...]} | {\"action\":\"verify_answer\"} | "
                "{\"action\":\"submit_answer\"}。submit_answer 需 verification_status=supported 且无 gap 才能通过门禁。")

    def read_act(self) -> dict | None:
        p = self.workdir / f"{self.tag}.act.json"
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {"error": "bad act json"}

    # ---------- 主循环 ----------
    def run(self) -> dict:
        outcome = None
        while True:
            # 终止判断
            if self.env.is_submitted:
                outcome = f"submitted"
                break
            if self.turn >= self.max_turns:
                outcome = "max_turns"
                break
            # 写上下文等我这步
            self.write_ctx(done=False)
            act = None
            while act is None:
                act = self.read_act()
                if act is None:
                    time.sleep(1.0)
            # 清空本次 act，避免被重复消费
            (self.workdir / f"{self.tag}.act.json").unlink(missing_ok=True)
            if "error" in act:
                continue
            a = act.get("action")
            if a == "search":
                self.exec_search(str(act.get("query", "")))
            elif a == "open_page":
                self.exec_open(str(act.get("docid", "")), act.get("search_action_id"))
            elif a == "read_evidence":
                self.exec_read(str(act.get("evidence_id", "")))
            elif a in ("update_state", "update"):
                self.exec_update(str(act.get("answer", "")),
                                 act.get("evidence_findings", []),
                                 act.get("supporting_evidence", []))
            elif a in ("verify_answer", "verify"):
                self.exec_verify()
            elif a in ("submit_answer", "submit"):
                self.exec_submit()
            elif a == "finish":
                self.exec_finish(str(act.get("answer", "")))
            else:
                self.actions.append({"turn": "?", "kind": "unknown_action", "action": a})

        self.write_ctx(done=True)
        return {
            "tag": self.tag,
            "qid": self.qid,
            "mode": self.mode,
            "outcome": outcome,
            "turns": self.turn,
            "submitted_answer": self.env.submitted_answer,
            "tool_calls": self._tool_counts(),
            "opened_docids": [e["docid"] for e in self.opened_evidence],
            "verify_rounds": self.verifier.round,
        }

    def _tool_counts(self) -> dict:
        from collections import Counter
        c = Counter()
        for a in self.actions:
            kind = a.get("kind", "")
            if kind.endswith("_attempt"):
                kind = kind[: -len("_attempt")]
            c[kind] += 1
        return {"search": c["search"], "open_page": c["open_page"], "read_evidence": c["read_evidence"],
                "update_state": c["update_state"], "verify_answer": c["verify_answer"],
                "submit_answer": c["submit_answer"], "finish": c["finish"],
                "total": self.turn}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--query-id", required=True)
    ap.add_argument("--mode", required=True, choices=["esr", "baseline"])
    ap.add_argument("--store", required=True, help="sqlite 轨迹输出路径")
    ap.add_argument("--workdir", default="/tmp/strong12_work", help="ctx/act/verdict 回填目录")
    ap.add_argument("--max-turns", type=int, default=50)
    ap.add_argument("--search-top-k", type=int, default=20)
    args = ap.parse_args()

    d = EpisodeDriver(dataset=args.dataset, qid=args.query_id, mode=args.mode,
                      store=args.store, workdir=args.workdir,
                      max_turns=args.max_turns, search_top_k=args.search_top_k)
    result = d.run()
    # 单行紧凑 JSON，保证编排方取 stdout 最后一行即可完整解析（multiline indent 会截到孤括号）
    print(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()


if __name__ == "__main__":
    main()