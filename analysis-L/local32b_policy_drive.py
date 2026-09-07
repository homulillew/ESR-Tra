#!/usr/bin/env python3
"""本地 Qwen3-32B 驱动强策略标准评测 —— 单局（一 qid × 一 mode）自动跑完。

与 analysis-L/api_policy_drive.py 同构：动作由 **本地 Qwen3-32B (:8002)** 自动产出，
verify 判定也由**同一个本地 32B session** 产出（镜像 api12"一个脑子同当策略与 verify"）。

目的：把 api12（策略=api Lanz-Medium、verifier=api）这一对照臂换成
**策略=Qwen3-32B、verifier=Qwen3-32B**，max_turns 提到 100，随机抽 100 条。

相对 api12 的三个本地适配：
  1. Local32BSession —— httpx 直接 POST :8002/v1/chat/completions（OpenAI 兼容），
     chat_template_kwargs={'enable_thinking': False} 关闭 Qwen3 思考块（保证动作 JSON 可解析、
     不烧 max_tokens），维护 messages 历史，失败用【同一份 messages】指数退避重试。
  2. 上下文护栏 —— 32B 窗口只有 40960 token(~13 万字符)。每轮 send_user 前检查消息总长，
     超限则裁剪最旧证据/hits 再发（LOCAL_CTX_CHARS 上限）；verify 的 evidence 预算也压下来。
  3. action_budget=100 对齐 max_turns=100（默认 30 会在 30 轮就催收敛）。

两流程（工具面，与 api12 一致）：
  esr      : [search, open_page, read_evidence, update_state, verify_answer, submit_answer]
  baseline : [search, open_page, finish]   # 用户裁定：删掉必然被拒的 read_evidence

循环：组装 prompt → 本地32B 出动作 JSON → 真实 ESREnvironment 执行(真 BM25) → 观察结果
  → 循环至 submit/finish/max_turns。gold 绝不过手，全程运行期不接触。
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
from typing import Sequence

import httpx

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent / "src") not in sys.path:
    sys.path.insert(0, str(_HERE.parent / "src"))

from esr_grpo.environment import ESREnvironment
from esr_grpo.retrieval import EchoRetrievalClient
from esr_grpo.models import Evidence, VerificationResult, VerificationStatus, to_primitive

RETRIEVAL_URL = "http://127.0.0.1:8000"
LOCAL_URL = "http://127.0.0.1:8002/v1/chat/completions"
LOCAL_MODEL = "Qwen3-32B"

# 用户裁定：baseline 删除 read_evidence（无 TaskState → 必然被拒的死工具）。
STRATEGY_ACTIONS = {
    "esr": ["search", "open_page", "read_evidence", "update_state", "verify_answer", "submit_answer"],
    "baseline": ["search", "open_page", "finish"],
}

# ---- 上下文护栏（适配 40960-token 窗口）----
# 窗口 40960 token。实测证据长文（含转义 HTML/JSON dump）token 密度高达 ~2.6 token/字符，
# 故按"token 估算"裁剪而非按字符数——否则 12 万字符能到 ~30 万 token，必然 400 超限。
# 留余量：内容总估算 ≤32k token、verify ≤30k token（估算用的是 2.6 最坏上界 ⇒ 实际必然更小，
# 再叠加 system/动作历史/600 生成也稳在 40960 窗口内）。
MAX_CTX_TOKENS = 30000          # 单次 send_user 前 session 内容 token 估算上限
MAX_VERIFY_TOKENS = 30000       # verify 单条消息内容 token 估算上限（含整段证据）
TOK_PER_CHAR_WORST = 5.0        # 实测最坏 token/字符比（escape HTML/JSON dump 证据实测达 4.1，取 5.0 上届保安全）
# 单条证据渲染上限 / verify 单次送达证据总预算（token-安全：按 5.0 最坏上届反推，单条即不超窗口）。
EVIDENCE_CHAR_CAP = int(MAX_CTX_TOKENS / TOK_PER_CHAR_WORST)           # 6000 字符/条
# 单条消息内容字符预算（按最坏 5.0 token/字符反推，保证单条消息稳在窗口内）。
LOCAL_VERIFY_CHARS = int(MAX_VERIFY_TOKENS / TOK_PER_CHAR_WORST)       # verify 引用证据总字符预算 ~6000
ACTION_EVIDENCE_CHARS = int(MAX_CTX_TOKENS / TOK_PER_CHAR_WORST)       # 动作 prompt 总 evidence 字符预算 ~6000
# 已打开证据最多保留展示条数（滚动窗口，防长轨迹爆窗口）。
MAX_RENDERED_EVIDENCE = 8
# 最近动作历史注入上限（避免上下文无限膨胀）。
MAX_ACTION_HISTORY = 30

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


def strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[^\n]*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


def parse_action_json(text: str) -> dict:
    """从模型文本里提取动作 JSON。先整体 json.loads，失败则取首个 {...} 花括号块。
    兼容 Qwen3 可能残留的 <thinking> 前缀 / 结尾杂文（最终 JSON 通常紧随其后）。"""
    text = strip_code_fence(text)
    # 取最后一个独立的 JSON 对象块更稳：模型往往思考完才输出动作 JSON。
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    blocks = re.findall(r"\{.*?\}", text, re.DOTALL)
    for b in reversed(blocks):
        try:
            return json.loads(b)
        except json.JSONDecodeError:
            continue
    raise ValueError(f"no action json found in: {text[:200]!r}")


class Local32BSession:
    """对 :8002 的薄封装：OpenAI 兼容 chat completions + 【同一份 messages】重试。
    带上下文护栏：send 前检查累计长度，超限裁剪最旧内容。"""

    def __init__(self, url: str = LOCAL_URL, model: str = LOCAL_MODEL,
                 timeout: float = 300.0, max_tokens: int = 600, retries: int = 5,
                 ctx_tokens: int = MAX_CTX_TOKENS):
        self.url = url
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.retries = retries
        self.ctx_tokens = ctx_tokens
        self.messages: list[dict] = []
        self.history_len = 0  # 仅记录 user+assistant 的内容字符数，供护栏判断

    def system(self, text: str) -> dict:
        return {"role": "system", "content": text}

    def user(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def assistant(self, text: str) -> dict:
        return {"role": "assistant", "content": text}

    def _payload(self, messages: list[dict]) -> dict:
        return {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": 0.0,
            "chat_template_kwargs": {"enable_thinking": False},
        }

    def _call_once(self, messages: list[dict]) -> str:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self.url, json=self._payload(messages))
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"] or ""

    def _call_with_retry(self, messages: list[dict]) -> str:
        last_exc = None
        for attempt in range(1, self.retries + 1):
            try:
                return self._call_once(messages)
            except (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException,
                    TimeoutError, ConnectionError) as exc:
                last_exc = exc
                if attempt >= self.retries:
                    break
                time.sleep(min(2 ** (attempt - 1), 20))
        raise RuntimeError(f"local 32B call failed after {self.retries} tries: {last_exc}")

    # ---- 上下文护栏（按 token 估算，适配 40960-token 窗口）----
    def _est_tokens(self, text: str) -> int:
        """最坏 token 上界估算：实测证据长文（转义 HTML/JSON dump）≈2.6 token/字符。
        用其上界做裁剪，保证即使全是最坏密度内容也不超窗口。"""
        return int(len(text) * TOK_PER_CHAR_WORST)

    def _total_tokens(self) -> int:
        return sum(self._est_tokens(m.get("content", "")) for m in self.messages if m.get("content"))

    def trim_oldest(self):
        """从最早的非 system 消息开始丢弃，直到 token 估算回落到 ctx_tokens 内。
        保留 system 引导与【最后一条正在请求的消息】（否则会把刚追加的当前 prompt 也裁空，导致空对话 400）。"""
        while self._total_tokens() > self.ctx_tokens and len(self.messages) > 1:
            dropped = False
            for i, m in enumerate(self.messages[:-1]):  # 绝不裁最后一条
                if m.get("role") == "system":
                    continue
                self.messages.pop(i)
                dropped = True
                break
            if not dropped:
                break  # 前面全是 system，只剩最后一条，无从裁

    def send_user(self, text: str) -> str:
        """追加一条 user 消息，护栏裁剪后取回复文本（自动维护历史）。"""
        self.messages.append(self.user(text))
        if self._total_tokens() > self.ctx_tokens:
            self.trim_oldest()
        answer = self._call_with_retry(self.messages)
        self.messages.append(self.assistant(answer))
        return answer


class Local32BDriver:
    def __init__(self, *, dataset, qid, mode, store, search_top_k=20, max_turns=100,
                 retries=5):
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

        self.session = Local32BSession(retries=retries)
        self.retriever = EchoRetrievalClient(RETRIEVAL_URL)
        self.verifier = _Local32BVerifier(self.session, self.tag)
        self.env = ESREnvironment(self.question, self.retriever, self.verifier,
                                  store_path=str(store),
                                  action_budget=max_turns)

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

    # ---------- 动作执行（真实环境门禁，与 api12 完全一致） ----------
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
        """滚动窗口：最多展示最近 MAX_RENDERED_EVIDENCE 条证据，每条 ≤ EVIDENCE_CHAR_CAP，
        且【合计】≤ ACTION_EVIDENCE_CHARS（单条消息 token 上界，防超窗口 400）。
        按时间保留最近，超预算从旧到新截断。"""
        out = []
        budget = ACTION_EVIDENCE_CHARS
        for e in self.opened_evidence[-MAX_RENDERED_EVIDENCE:]:
            content = e["content"]
            if len(content) > EVIDENCE_CHAR_CAP:
                content = content[:EVIDENCE_CHAR_CAP] + f"...[截断]"
            block = f"[{e['evidence_id']}] doc {e['docid']} {e['title']}\n{content}"
            if len(block) > budget:
                block = block[:budget] + f"...[总预算截断]"
                out.append(block)
                break
            out.append(block)
            budget -= len(block)
            if budget <= 0:
                break
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
        """调本地 32B 产出下一动作 JSON；非法 JSON 让模型重出（原对话继续，护栏自动收）。"""
        prompt = self.build_prompt(guidance)
        for _ in range(3):
            text = self.session.send_user(prompt)
            try:
                return parse_action_json(text)
            except ValueError:
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


class _Local32BVerifier:
    """把本地 32B session 借给 ESREnvironment 当 verifier：verify = 让同一 32B 出 verdict JSON。"""

    def __init__(self, session: Local32BSession, tag: str):
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
            if total + len(seg) > LOCAL_VERIFY_CHARS:
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
    ap.add_argument("--max-turns", type=int, default=100)
    ap.add_argument("--retries", type=int, default=5)
    args = ap.parse_args()

    d = Local32BDriver(dataset=args.dataset, qid=args.query_id, mode=args.mode,
                       store=args.store, search_top_k=args.search_top_k,
                       max_turns=args.max_turns, retries=args.retries)
    result = d.run()
    print(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()


if __name__ == "__main__":
    main()