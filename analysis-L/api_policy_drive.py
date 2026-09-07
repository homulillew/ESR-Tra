#!/usr/bin/env python3
"""api 驱动强策略标准评测 —— 单局（一 qid × 一 mode）自动跑完。

与 strong_policy_drive.py（我手动回填 .act.json）的差别：
  - 策略动作由 **api（Lanz-Medium = 强策略模型）** 自动产出，不进我的人工回填。
  - 每条样本（qid×mode）**新建一个全新 LanzClient session**，杜绝跨样本/跨方法污染，
    也没有共享持久上下文（修复 strong12 中"同一持续上下文逐局推进"的污染）。
  - ESR 的 verify 判定由 **同一个 api session** 产出（忠实复刻原 strong12"我用一个脑子
    同时当策略与 verify"），不是任何本地模型。
  - API 调用做异常捕获：httpx 超时/HTTP 状态/连接错误 均按【原对话 messages】重试
    （指数退避，最多 retries 次），保证从同一会话状态续走，不丢历史。

两流程（工具面）：
  esr      : [search, open_page, read_evidence, update_state, verify_answer, submit_answer]
  baseline : [search, open_page, finish]   # 用户裁定：删掉必然被拒的 read_evidence（无 TaskState）

循环（单样本）：
  1) 组装策略 prompt（question + allowed_actions + 最近 search hits + 已开证据 chunk 视图 +
     task_state(ESR) + guidance），不含任何 gold/gold_docid。
  2) 调 api，要求输出下一动作的 JSON（{"action": ...}）。
  3) 真实 ESREnvironment 执行该动作（真 BM25），观察结果；ESR verify 单独走 verify prompt。
  4) 循环直至 submit/finish/max_turns。

终止 info 写 result dict：outcome / turns / submitted_answer / tool_calls / verify_rounds。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

# lanz_client 位于仓库 api 目录；确保能 import 到（即使 cwd 在别处）。
_HERE = Path(__file__).resolve().parent
_API_DIR = _HERE.parent / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from esr_grpo.environment import ESREnvironment
from esr_grpo.retrieval import EchoRetrievalClient
from esr_grpo.models import Evidence, VerificationResult, VerificationStatus, to_primitive

RETRIEVAL_URL = "http://127.0.0.1:8000"

# 用户裁定：baseline(BC+ 基础工具) 删除 read_evidence（无 TaskState → 必然被拒的死工具）。
STRATEGY_ACTIONS = {
    "esr": ["search", "open_page", "read_evidence", "update_state", "verify_answer", "submit_answer"],
    "baseline": ["search", "open_page", "finish"],
}

# verify 每次送入 api 的单条证据字符上限 / 总预算（过长会被 needs_revision 打回逼精简）
EVIDENCE_CHAR_CAP = 60_000
VERIFY_BUDGET = 480_000

ACTION_INSTRUCTION = {
    "esr": (
        "从 allowed_actions 里选一个动作，只输出一个 JSON 对象：\n"
        '{"action":"search","query":"<检索词>"}\n'
        '{"action":"open_page","docid":"<search_hits里的docid>","search_action_id":"<hits所属search的action_id，如 a5>"}\n'
        '{"action":"read_evidence","evidence_id":"<task_state.evidence_directory里的id>"}\n'
        '{"action":"update_state","answer":"<候选答案>","evidence_findings":[{"evidence_id":"<id>","finding":"<从该证据看到的事实>"}],"supporting_evidence":["<证据id>"]}\n'
        '{"action":"verify_answer"}\n'
        '{"action":"submit_answer"}\n'
        "说明：submit_answer 只有当前 verification_status=supported 且无 gap 才通过。"
        "open_page 只能打开最近一次（或本次会话里）search hits 里的 docid，且必须原样回传那个 search 的真实 action_id"
        "（形如 a1/a2/...，见『最近动作历史』或 hits 标注）；不要编造 action_id，否则会被拒绝。"
    ),
    "baseline": (
        "从 allowed_actions 里选一个动作，只输出一个 JSON 对象：\n"
        '{"action":"search","query":"<检索词>"}\n'
        '{"action":"open_page","docid":"<search_hits里的docid>","search_action_id":"<hits所属search的action_id，如 a5>"}\n'
        '{"action":"finish","answer":"<最终答案>"}\n'
        "说明：finish 会直接提交最终答案，请只在你有把握给出最终答案时调用。"
        "open_page 只能打开最近一次（或本次会话里）search hits 里的 docid，且必须原样回传那个 search 的真实 action_id"
        "（形如 a1/a2/...，见『最近动作历史』或 hits 标注）；不要编造 action_id，否则会被拒绝。"
    ),
}

VERIFY_INSTRUCTION = (
    "你是事实核查校验器。判断给定【答案】能否被【引用证据文本】充分支持。\n"
    '只输出一个 JSON：{"verification_status":"supported"|"needs_revision","gaps":[缺失项描述],'
    '"rationale":"<一句话理由>"}\n'
    "supported 要求：证据文本确实点名了答案所陈述的实体/事实，且逻辑链成立，无关键缺口。"
    "needs_revision 时，gaps 列出缺失的关键证据/事实（一条一项），供策略定向补证据。"
)

# 最近动作历史注入给模型的轮次上限（避免无限膨胀上下文）
MAX_ACTION_HISTORY = 30


def load_question(dataset: str, qid: str) -> str:
    """只取 query（gold 绝不过手）。"""
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


class ApiSession:
    """对 LanzClient 的薄封装：带【原对话】重试。每次请求快照当前 messages，
    失败时用同一份 messages 指数退避重试（保持会话连续）。"""

    def __init__(self, model: str = "Lanz-Medium", timeout: float = 180.0,
                 max_tokens: int = 512, retries: int = 5):
        from lanz_client import LanzClient
        self.client = LanzClient(model=model, timeout=timeout, max_tokens=max_tokens)
        self.retries = retries

    def _call_with_retry(self, messages: list[dict]):
        last_exc = None
        for attempt in range(1, self.retries + 1):
            try:
                return self.client._call(messages)
            except (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException,
                    TimeoutError, ConnectionError) as exc:
                last_exc = exc
                if attempt >= self.retries:
                    break
                time.sleep(min(2 ** (attempt - 1), 20))
        raise RuntimeError(f"api call failed after {self.retries} tries: {last_exc}")

    def send_user(self, text: str) -> str:
        """追加一条 user 消息并取回复文本（自动维护历史）。"""
        self.client.history.append(self.client.user(text))
        js = self._call_with_retry(self.client.history)
        answer = self.client._extract_text(js)
        self.client.history.append(self.client.assistant(answer))
        return answer

    def send_user_dict(self, text: str, *, times: int) -> str:
        """带重试的用户消息发送（同一会话历史），times<=0 表示不追加历史直接重试。"""
        return self.send_user(text)  # send_user 内部已按原对话重试


def strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[^\n]*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


def parse_action_json(text: str) -> dict:
    """从模型文本里提取动作 JSON。先整体 json.loads，失败则取首个 {...} 花括号块。"""
    text = strip_code_fence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError as exc:
            raise ValueError(f"action not valid json: {exc}; text={text[:200]!r}") from exc
    raise ValueError(f"no action json found in: {text[:200]!r}")


class ApiDriver:
    def __init__(self, *, dataset, qid, mode, store, search_top_k=20, max_turns=50,
                 model="Lanz-Medium", retries=5):
        self.qid = str(qid)
        self.mode = mode
        self.tag = f"{self.qid}_{self.mode}"
        self.max_turns = max_turns
        self.search_top_k = search_top_k

        self.question = load_question(dataset, self.qid)
        if not self.question:
            raise SystemExit(f"query {self.qid} not found in {dataset}")

        store_path = Path(store)
        if store_path.exists():
            store_path.unlink()

        self.session = ApiSession(model=model, retries=retries)
        self.retriever = EchoRetrievalClient(RETRIEVAL_URL)
        self.verifier = _ApiVerifier(self.session, self.tag)
        self.env = ESREnvironment(self.question, self.retriever, self.verifier,
                                  store_path=str(store))

        self.cursor = 0
        self.turn = 0
        self.hits: list[dict] = []
        self.last_search_action_id: str | None = None
        self.actions: list[dict] = []
        self.opened_evidence: list[dict] = []  # [{evidence_id, docid, title, content, truncated}]

    def span(self, n: int = 3) -> list:
        s = [{"segment_index": 0, "start": self.cursor, "end": self.cursor + n}]
        self.cursor += n
        return s

    # ---------- 动作执行（真实环境门禁） ----------
    def exec_search(self, query: str) -> dict:
        self.turn += 1
        r = self.env.search(query, top_k=self.search_top_k, token_spans=self.span(), turn_id=f"t{self.turn}")
        self.hits = _hits_primitive(r["results"])
        self.last_search_action_id = r["action_id"]
        self.actions.append({"turn": f"t{self.turn}", "kind": "search", "query": query,
                             "hits": len(self.hits), "action_id": r["action_id"]})
        return {"ok": True, "turn": f"t{self.turn}", "action_id": r["action_id"]}

    def exec_open(self, docid: str, search_action_id) -> dict:
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
        self.actions.append({"turn": f"t{self.turn}", "kind": "open_page", "docid": docid,
                             "evidence_id": eid})
        return {"ok": True, "turn": f"t{self.turn}", "evidence_id": eid}

    def exec_read(self, evidence_id: str) -> dict:
        self.turn += 1
        try:
            r = self.env.read_evidence(evidence_id, token_spans=self.span(), turn_id=f"t{self.turn}")
        except Exception as exc:
            self.actions.append({"turn": f"t{self.turn}", "kind": "read_evidence_attempt",
                                 "evidence_id": evidence_id, "rejected": str(exc)[:300]})
            return {"ok": False, "turn": f"t{self.turn}", "rejected": str(exc)}
        for e in self.opened_evidence:
            if e["evidence_id"] == str(evidence_id):
                e["content"] = r.get("content", e["content"])
        self.actions.append({"turn": f"t{self.turn}", "kind": "read_evidence", "evidence_id": evidence_id})
        return {"ok": True, "turn": f"t{self.turn}", "content": r.get("content", "")}

    def exec_update(self, answer, findings, support) -> dict:
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
        self.actions.append({"turn": f"t{self.turn}", "kind": "finish", "answer": self.env.submitted_answer})
        return {"ok": True, "turn": f"t{self.turn}", "submitted_answer": self.env.submitted_answer}

    # ---------- 状态渲染（不含 gold） ----------
    def _rendered_evidence(self):
        out = []
        for e in self.opened_evidence[-6:]:
            out.append(f"[{e['evidence_id']}] doc {e['docid']} {e['title']}\n{e['content'][:60_000]}")
        return "\n\n".join(out)

    def build_prompt(self, guidance: str = "") -> str:
        state = self.env.current_state
        hist = self.actions[-MAX_ACTION_HISTORY:]
        hist_lines = "\n".join(
            f"#{a['turn']} {a['kind']}"
            + (f"  query={a.get('query')!r} hits={a.get('hits')}" if "query" in a else "")
            + (f"  docid={a.get('docid')}" if "docid" in a else "")
            + (f"  evidence_id={a.get('evidence_id')}" if "evidence_id" in a else "")
            + (f"  status={a.get('verification_status')}" if "verification_status" in a else "")
            + (f"  REJECTED: {a.get('rejected')}" if a.get("rejected") else "")
            for a in hist) or "(尚无动作)"

        hits_block = "\n".join(
            f"[{h['rank']}] docid={h['docid']} | {h['title']} | {h['snippet']}"
            for h in self.hits
        ) or "(尚无 search 结果；请先 search)"
        hits_owner = (
            f"(以上 hits 来自 search action_id={self.last_search_action_id}；"
            "打开其中文档时必须原样回传这个 search_action_id)"
            if self.last_search_action_id else ""
        )

        evidence_block = self._rendered_evidence() or "(尚未打开任何文档)"

        parts = [
            "你现在是一个执行证据检索与作答的 Agent。请仅依据下方提供的真实检索结果作答，不要编造。",
            f"题目：{self.question}",
            f"当前可用动作：{STRATEGY_ACTIONS[self.mode]}",
            "",
            "最近动作历史：",
            hist_lines,
            "",
            "最近一次 search 命中的文档（open_page 只能从这里选 docid）",
            hits_owner,
            hits_block,
            "",
            "已打开的文档证据（chunk 视图）：",
            evidence_block,
        ]
        if self.mode == "esr":
            parts.append(f"当前 TaskState：{json.dumps(to_primitive(state), ensure_ascii=False) if state else '(尚无，先 update_state)'}")
            if guidance:
                parts.append(f"【环境提示】{guidance}")
        parts.append(ACTION_INSTRUCTION[self.mode])
        return "\n\n".join(parts)

    def _action_from_model(self, guidance: str = "") -> dict:
        """调 api 产出下一动作 JSON；非法 JSON 让模型重出（原对话继续）。"""
        prompt = self.build_prompt(guidance)
        for _ in range(3):
            text = self.session.send_user(prompt)
            try:
                return parse_action_json(text)
            except ValueError:
                # 重试时带上提示，要求输出 JSON
                prompt = "你上一条回复不含可解析的动作 JSON。请只输出动作 JSON（见 allowed_actions），不要任何额外文字。"
        raise RuntimeError(f"action json unparseable after retries; last={text[:200]!r}")

    # ---------- 主循环 ----------
    def run(self) -> dict:
        outcome = "max_turns"
        try:
            while True:
                if self.env.is_submitted:
                    outcome = "submitted"
                    break
                if self.turn >= self.max_turns:
                    outcome = "max_turns"
                    break
                guidance = self._next_step_guidance()
                act = self._action_from_model(guidance)
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
        except RuntimeError as exc:
            outcome = f"error:{exc}"

        return {
            "tag": self.tag, "qid": self.qid, "mode": self.mode, "outcome": outcome,
            "turns": self.turn, "submitted_answer": self.env.submitted_answer,
            "tool_calls": self._tool_counts(),
            "opened_docids": [e["docid"] for e in self.opened_evidence],
            "verify_rounds": self.verifier.round,
        }

    def _tool_counts(self) -> dict:
        c = Counter()
        for a in self.actions:
            kind = a.get("kind", "")
            if kind.endswith("_attempt"):
                kind = kind[: -len("_attempt")]
            c[kind] += 1
        return {"search": c["search"], "open_page": c["open_page"], "read_evidence": c["read_evidence"],
                "update_state": c["update_state"], "verify_answer": c["verify_answer"],
                "submit_answer": c["submit_answer"], "finish": c["finish"], "total": self.turn}

    def _next_step_guidance(self) -> str:
        try:
            return self.env._next_step_guidance(self.env.current_state) or ""
        except Exception:
            return ""


class _ApiVerifier:
    """把 api session 借给 ESREnvironment 当 verifier：verify = 让同一 api 模型出 verdict JSON。"""

    def __init__(self, session: ApiSession, tag: str):
        self.session = session
        self.tag = tag
        self.round = 0

    def verify(self, question: str, answer: str, evidence: Sequence[Evidence]) -> VerificationResult:
        self.round += 1
        segs, total = [], 0
        for it in evidence:
            content = it.content
            if len(content) > EVIDENCE_CHAR_CAP:
                content = content[:EVIDENCE_CHAR_CAP]
            seg = f"[{it.evidence_id}] {it.source.title}\n{content}"
            if total + len(seg) > VERIFY_BUDGET:
                return VerificationResult(VerificationStatus.NEEDS_REVISION,
                                          ("被引用原始证据过长超出预算,请精简 supporting_evidence 后重新验证",),
                                          "referenced evidence exceeds budget")
            segs.append(seg)
            total += len(seg)
        prompt = (
            "【校验任务】\n"
            f"题目：{question}\n"
            f"待校验答案：{answer}\n"
            f"引用证据：\n{(chr(10)*2).join(segs) if segs else '(无可用证据)'}\n\n"
            + VERIFY_INSTRUCTION
        )
        for _ in range(3):
            try:
                text = self.session.send_user(prompt)
                v = parse_action_json(text)
            except (ValueError, RuntimeError):
                prompt = "你上一条回复不含可解析的校验 JSON。请只输出校验 JSON，不要额外文字。"
                continue
            status = v.get("verification_status")
            if status == "supported":
                return VerificationResult(VerificationStatus.SUPPORTED, (), str(v.get("rationale", "")))
            if status == "needs_revision":
                gaps = [str(g).strip() for g in v.get("gaps", []) if str(g).strip()]
                return VerificationResult(VerificationStatus.NEEDS_REVISION,
                                          tuple(gaps) or ("当前答案未通过校验",), str(v.get("rationale", "")))
        return VerificationResult(VerificationStatus.NEEDS_REVISION, ("校验无法解析，请重试",), "unparseable verdict")


def _hits_primitive(results) -> list[dict]:
    out = []
    for i, h in enumerate(results):
        docid = str(h.get("docid"))
        if not docid:
            continue
        out.append({"rank": i, "docid": docid,
                    "title": str(h.get("title", ""))[:200],
                    "snippet": str(h.get("snippet", h.get("text", "")))[:400]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--query-id", required=True)
    ap.add_argument("--mode", required=True, choices=["esr", "baseline"])
    ap.add_argument("--store", required=True)
    ap.add_argument("--search-top-k", type=int, default=20)
    ap.add_argument("--max-turns", type=int, default=50)
    ap.add_argument("--model", default="Lanz-Medium")
    ap.add_argument("--retries", type=int, default=5)
    args = ap.parse_args()

    d = ApiDriver(dataset=args.dataset, qid=args.query_id, mode=args.mode,
                  store=args.store, search_top_k=args.search_top_k,
                  max_turns=args.max_turns, model=args.model, retries=args.retries)
    result = d.run()
    print(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()


if __name__ == "__main__":
    main()