"""与模型服务解耦的多轮 Agent Loop。

该模块用于 Benchmark 推理和协议调试。分布式 RL rollout 的精确 token 范围由
verl/SGLang 集成层提供，不能用这里的近似范围代替训练元数据。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from .environment import ESREnvironment, IllegalActionError
from .models import TokenSpan, to_primitive


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Mapping[str, Any]
    call_id: str = ""
    token_spans: tuple[TokenSpan, ...] = ()


@dataclass(frozen=True)
class PolicyTurn:
    content: str
    tool_calls: tuple[ToolCall, ...]
    raw: Any = None
    # 参数解析被丢弃的 tool call 的注记（非法 JSON / arguments 非对象），
    # 由 AgentRunner 拼进 nudge 提示让模型重发。
    dropped_notes: tuple[str, ...] = ()


def _to_openai_tool_call(item: ToolCall) -> dict[str, Any]:
    """把 ToolCall 转成 OpenAI Chat Completions 消息里 assistant `tool_calls`
    项的标准结构 `{id, type, function:{name, arguments}}`。

    运行时（本地 model 服务）要求这个嵌套结构，否则第二轮把工具回调
    塞回给模型时会 400（缺 id/type/function 字段）。训练时的精确 token
    范围由 verl/SGLang 集成层覆盖，与这里无关。
    """
    return {
        "id": item.call_id,
        "type": "function",
        "function": {
            "name": item.name,
            "arguments": json.dumps(item.arguments, ensure_ascii=False),
        },
    }
    raw: Mapping[str, Any] | None = None


class Policy(Protocol):
    def next_turn(self, messages: Sequence[Mapping[str, Any]], context: Mapping[str, Any]) -> PolicyTurn: ...


SYSTEM_PROMPT = """你是长程检索 Agent。你的研究必须收敛到可验证的答案，不能无限搜索。

工具协议（严格按此推进）：
1. search：查找候选文档。返回的 hits 只是候选，不是证据。
2. open_page：打开 search 返回的文档，保存为不可变 Evidence。打开后系统会截断显示原文头部。
3. update_state：读完有用 Evidence 后【必须】调用，把 finding 和候选答案写入 TaskState。
   answer 字段填你认为的候选【答案本身】（可以是'暂无候选'表示还在查证，但绝不能写搜索计划或过程描述）。
   绝不连续多轮只 search+open_page 而不 update_state。
4. verify_answer：当 TaskState 已形成候选答案、主要证据就绪时调用，让校验（同一模型、新开上下文）
   审计候选答案是否【真的是问题所指的那个实体/答案】且被证据充分支持。证据支持了错误实体也应判不通过。
5. submit_answer：仅在验证返回 supported 且 gaps 为空时调用。未验证前不得提交。
6. read_evidence：按 Evidence ID 重新读取已保存的原文验证旧材料。

协议约束：
- 打开完一批 Evidence 后，下一步【必须】是 update_state 整理，而不是继续 open 下一批。
- 答案基本形成后，必须 verify_answer，不能停在反复 search。
- 【重要】同一个 TaskState 只能 verify 一次。verify 返回 needs_revision 后，不能再次 verify 同一个状态（会被拒绝），
  必须先 update_state 修正 answer 或解决 gaps，才能再次 verify。
- 系统每轮会给出 next_step_guidance，按它推进，除非你有更强的理由。
- 不要在普通文本中绕过 submit_answer 直接给最终答案。

示例一次完整工作流（3~4 轮即可收敛）：
1. search(query="关键条件") → 得到候选 hits。
2. open_page(docid, search_action_id) → 保存 Evidence，通常系统记为 e1。
3. update_state(answer="初步候选答案", evidence_findings=[{evidence_id:"e1", finding:"原文明确说明……"}], supporting_evidence=["e1"])。
4. verify_answer() → 若验证器返回 supported 且无 Gap，submit_answer()；若返回 needs_revision，
   则先 search/open 补证据 → update_state 修正 → 再 verify，不要对着同一状态反复 verify。
不要在缺少关键条件时反复盲搜；找到一片能回答核心问题的证据后立即转入 update_state→verify。"""


OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "在固定语料中检索文档",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": "打开某次 search 返回的文档并保存为不可变 Evidence",
            "parameters": {
                "type": "object",
                "properties": {
                    "docid": {"type": "string"},
                    "search_action_id": {"type": "string"},
                },
                "required": ["docid", "search_action_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_evidence",
            "description": "按 Evidence ID 重新读取证据原文。默认返回按问题相关度排序的关键片段；可传 offset(字符偏移)续读原文后续部分",
            "parameters": {
                "type": "object",
                "properties": {
                    "evidence_id": {"type": "string"},
                    "offset": {"type": "integer", "default": 0},
                },
                "required": ["evidence_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_state",
            "description": "写入或修正 finding，更新答案和主要证据；gaps 保持不变",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "evidence_findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "evidence_id": {"type": "string"},
                                "finding": {"type": "string"},
                            },
                            "required": ["evidence_id", "finding"],
                        },
                    },
                    "supporting_evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["answer", "evidence_findings", "supporting_evidence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_answer",
            "description": "让独立验证器根据主要 Evidence 检查当前答案",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_answer",
            "description": "提交已通过验证的 TaskState.answer",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


BASELINE_SYSTEM_PROMPT = """你是信息检索 Agent。你的任务是通过搜索并阅读材料来回答问题。

工作流：
1. search(query)：检索候选文档，返回 hits（候选，不是证据）。
2. open_page(docid, search_action_id)：打开一篇 search 返回的文档，阅读其内容。
3. read_evidence(evidence_id)：重新阅读某篇已打开的证据。
4. finish(answer)：当你确信已从材料中得出答案时调用，提交最终答案。

约束：
- 不要重复搜索同样的词，优先利用已打开文档中的新信息改进下一次搜索。
- 只有当你有足够依据时才 finish，不要过早提交。
- 给出的是【答案本身】，不是搜索计划或过程描述。
在普通文本中给出最终答案不会被记录，必须通过 finish(answer) 提交。"""


BASELINE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "在固定语料中检索文档",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": "打开某次 search 返回的文档并保存为 Evidence",
            "parameters": {
                "type": "object",
                "properties": {
                    "docid": {"type": "string"},
                    "search_action_id": {"type": "string"},
                },
                "required": ["docid", "search_action_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_evidence",
            "description": "按 Evidence ID 重新读取证据原文。默认返回按问题相关度排序的关键片段；可传 offset(字符偏移)续读原文后续部分",
            "parameters": {
                "type": "object",
                "properties": {
                    "evidence_id": {"type": "string"},
                    "offset": {"type": "integer", "default": 0},
                },
                "required": ["evidence_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "提交最终答案结束检索",
            "parameters": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
            },
        },
    },
]


def _post_chat_with_retry(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    *,
    timeout_seconds: float,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """POST chat/completions，对 5xx/超时/连接错误做指数退避重试。

    HTTP 4xx 属请求本身问题（重试无用），但把响应体带进异常便于诊断——
    vLLM 的 400 错误体里通常有具体 reason。
    """
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            if exc.code < 500:
                raise RuntimeError(f"chat/completions HTTP {exc.code}: {detail}") from exc
            last_error = RuntimeError(f"chat/completions HTTP {exc.code}: {detail}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = RuntimeError(f"chat/completions 网络错误: {exc}")
        if attempt < max_attempts - 1:
            time.sleep(2 ** attempt * 2)  # 2s, 4s
    raise last_error if last_error else RuntimeError("chat/completions 重试耗尽")


@dataclass
class OpenAIChatPolicy:
    base_url: str
    model: str
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_seconds: float = 180.0
    tools: list[dict[str, Any]] = field(default_factory=lambda: list(OPENAI_TOOLS))

    def next_turn(self, messages: Sequence[Mapping[str, Any]], context: Mapping[str, Any]) -> PolicyTurn:
        contextual_messages = list(messages) + [
            {
                "role": "user",
                "content": "当前系统状态：\n" + json.dumps(context, ensure_ascii=False),
            }
        ]
        body = {
            "model": self.model,
            "messages": contextual_messages,
            "tools": self.tools,
            "tool_choice": "auto",
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        api_key = os.getenv(self.api_key_env)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        raw = _post_chat_with_retry(
            f"{self.base_url.rstrip('/')}/chat/completions",
            body,
            headers,
            timeout_seconds=self.timeout_seconds,
        )
        message = raw["choices"][0]["message"]
        calls: list[ToolCall] = []
        dropped: list[str] = []
        offset = 0
        for item in message.get("tool_calls", []):
            function = item["function"]
            raw_arguments = function.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_arguments)
            except (json.JSONDecodeError, TypeError):
                # 模型把 arguments 写坏成非法 JSON：丢弃该 call，让 nudge 路径要求重发，
                # 而不是整条查询崩死。
                dropped.append(f"{function['name']}:非法JSON({str(raw_arguments)[:60]})")
                continue
            if not isinstance(arguments, dict):
                # 模型把 arguments 双重编码成字符串/数组：同样丢弃重发。否则
                # dict(字符串) 会在 execute_tool 处抛 ValueError。
                dropped.append(f"{function['name']}:arguments非对象({type(arguments).__name__})")
                continue
            # Chat Completions API 不返回 tool call 的 token 位置。这里的范围只用于
            # 推理日志可视化，训练时会由 SGLang tokenizer 覆盖。
            approximate_length = max(1, len(json.dumps(item, ensure_ascii=False)) // 4)
            calls.append(
                ToolCall(
                    name=function["name"],
                    arguments=arguments,
                    call_id=str(item.get("id", "")),
                    token_spans=(TokenSpan(0, offset, offset + approximate_length),),
                )
            )
            offset += approximate_length
        return PolicyTurn(str(message.get("content") or ""), tuple(calls), raw, dropped_notes=tuple(dropped))


@dataclass
class AgentRunner:
    environment: ESREnvironment
    policy: Policy
    max_turns: int = 50
    max_parallel_calls: int = 5
    max_noop_retries: int = 2
    # 序列化消息超过该字节数时触发压缩；None 表示禁用。
    compact_message_chars: int | None = 28_000
    # "esr"：结构化研究状态；"baseline"：无 ESR 的普通检索 agent。
    mode: str = "esr"

    def run(self) -> dict[str, Any]:
        system_prompt = SYSTEM_PROMPT if self.mode == "esr" else BASELINE_SYSTEM_PROMPT
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": self.environment.question},
        ]
        turns: list[dict[str, Any]] = []
        noop = 0
        for turn_index in range(self.max_turns):
            turn = self.policy.next_turn(messages, self.environment.render_context(mode=self.mode))
            assistant = {
                "role": "assistant",
                "content": turn.content,
                "tool_calls": [_to_openai_tool_call(item) for item in turn.tool_calls],
            }
            messages.append(assistant)
            if not turn.tool_calls:
                noop += 1
                if noop > self.max_noop_retries:
                    turns.append({"turn": turn_index, "error": "policy returned no tool call"})
                    break
                nudge_parts = []
                if turn.dropped_notes:
                    # 参数解析层丢弃的 tool call：明确告诉模型错在哪，要求重发
                    nudge_parts.append(
                        "你刚才的工具调用参数格式错误，已被系统丢弃："
                        + "；".join(turn.dropped_notes)
                        + "。arguments 必须是合法 JSON 对象（如 {\"query\": \"...\"}）。"
                    )
                nudge_parts.append("请根据 next_step_guidance 继续推进研究（必须选择并调用一个工具，参数为合法 JSON 对象）。")
                turns.append({"turn": turn_index, "nudge": "no usable tool call; prompting to continue"})
                messages.append(
                    {
                        "role": "user",
                        "content": nudge_parts[0] if len(nudge_parts) == 1 else "".join(nudge_parts),
                    }
                )
                continue
            calls = list(turn.tool_calls[: self.max_parallel_calls])
            # baseline 模式下限定工具集：过滤掉模型误生成的 ESR 专属工具
            if self.mode != "esr":
                allowed = {t["function"]["name"] for t in self.policy.tools}
                calls = [c for c in calls if c.name in allowed]
                if not calls:
                    turns.append({"turn": turn_index, "error": "policy emitted only disallowed tools"})
                    messages.append(
                        {
                            "role": "user",
                            "content": "当前模式只允许 search / open_page / read_evidence / finish 四种工具，请重新选择一个工具。",
                        }
                    )
                    continue
            parallel_names = {"search", "open_page", "read_evidence"}
            if len(calls) > 1 and all(item.name in parallel_names for item in calls):
                results = self.environment.execute_parallel(
                    [
                        {
                            "name": item.name,
                            "arguments": dict(item.arguments),
                            "token_spans": [to_primitive(span) for span in item.token_spans],
                        }
                        for item in calls
                    ],
                    turn_id=f"t{turn_index + 1}",
                )
            elif len(calls) == 1:
                item = calls[0]
                try:
                    result = self.environment.execute_tool(
                            item.name,
                            item.arguments,
                            token_spans=item.token_spans,
                            turn_id=f"t{turn_index + 1}",
                        )
                except IllegalActionError as exc:
                    result = {"error": str(exc), "action_id": exc.action_id, "legal": False}
                results = [result]
            else:
                turns.append({"turn": turn_index, "error": "state-changing actions must be serial"})
                break
            for call, result in zip(calls, results):
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.call_id,
                        "name": call.name,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            turns.append(
                {
                    "turn": turn_index,
                    "assistant": assistant,
                    "tool_results": results,
                }
            )
            if self.mode == "baseline":
                self._maybe_baseline_finish_nudge(messages, turn_index)
            elif self.mode == "esr":
                self._maybe_esr_recovery(messages, results)
            self._maybe_compact(messages, turn_index)
            if self.environment.is_submitted:
                break
        if self.mode == "baseline" and not self.environment.is_submitted:
            # 预算用尽仍未 finish：从最近一条 assistant 内容里提取最佳猜测，强制提交，
            # 保证 baseline 总是给出一个终答，避免"无限检索却无输出"的不公平塌缩。
            fallback = _extract_baseline_answer(messages)
            if fallback:
                self.environment.finish(fallback)
        return {
            "submitted": self.environment.is_submitted,
            "answer": self.environment.submitted_answer,
            "turns": turns,
            "messages": messages,
            "episode": self.environment.snapshot(),
        }

    def _maybe_esr_recovery(self, messages: list[dict[str, Any]], results: list[dict[str, Any]]) -> None:
        """ESR 模式下修复常见的无效空转：模型对同一 TaskState 重复 verify_answer 被硬拒绝。

        ESR 状态机规定同一个 TaskState 只能 verify 一次，重复 verify 会返回
        "already been verified"。模型不解规则时会对着同一状态反复空转。
        检测到此类拒绝后，注入一条强指导消息，督促先 update_state 修正，而非继续 verify。
        """
        for result in results:
            if (isinstance(result, dict)
                    and result.get("legal") is False
                    and "already been verified" in str(result.get("error", ""))):
                messages.append({
                    "role": "user",
                    "content": (
                        "你刚才的 verify_answer 被拒绝，因为当前 TaskState 已经验证过，不能重复验证。"
                        "下一步【必须】先调用 update_state 修正 answer 或补充 supporting_evidence 后再 verify，"
                        "而不是继续调用 verify_answer。"
                    ),
                })
                return

    def _maybe_baseline_finish_nudge(self, messages: list[dict[str, Any]], turn_index: int) -> None:
        """Baseline 无 TaskState/Verify gate，模型常陷入无限 search/open。

        检索开销与 ESR 对齐（同一 BM25 + open_page），但 baseline 缺少把观察
        沉淀成"可提交答案"的结构化压力。这里只在已打开过至少一篇文档后，给出
        与 next_step_guidance 对等的确定性收敛提示，逼近回合上限时升级为强提示。
        """
        evidence_count = len(self.environment.store.list_evidence())
        if evidence_count == 0:
            return  # 尚无材料，继续检索合理
        remaining = self.max_turns - turn_index
        if remaining <= 1:
            # 强收敛：逼近回合上限，强制提交，避免 baseline 无限检索却不作答。
            note = (
                f"你的检索预算已耗尽，只有最后一步。请基于已读 Evidence 给出最终答案："
                '【必须立即】调用 finish(answer)，即使不确定也要给出你的最佳猜测，不要继续 search/open_page。'
            )
        elif remaining <= 3 or turn_index >= 8:
            note = (
                f"你已打开 {evidence_count} 篇文档。若已能依据其中信息回答问题，"
                '请调用 finish(answer) 提交；除非确有把握某篇未读文档会改变答案，否则停止继续 search。'
            )
        else:
            note = (
                f"已积累 {evidence_count} 篇 Evidence。若信息足够请调用 finish(answer) 收敛；"
                "仅在答案确实缺失关键事实时才继续 search/open_page。"
            )
        messages.append({"role": "user", "content": note})

    def _maybe_compact(self, messages: list[dict[str, Any]], turn_index: int) -> None:
        """本地 model 服务上下文有限（--max-model-len 32k）。

        当累积消息接近上限时，把对话压成
        [system, question, TaskState视图, 最近 recent_tail 轮]。
        已打开的 Evidence 全量正文仍保存在 EpisodeStore，模型可随时
        read_evidence(evidence_id) 重读，不丢信息。压缩后主动追加一条
        说明消息，避免模型因看不到旧观察而困惑。
        """
        budget = self.compact_message_chars
        if budget is None:
            return
        if sum(len(json.dumps(m, ensure_ascii=False)) for m in messages) <= budget:
            return
        head: list[dict[str, Any]] = [
            messages[0],
            messages[1],
            {
                "role": "user",
                "content": "上下文已压缩。早期工具观察已折叠；重要信息仍在 TaskState 视图与 Evidence 目录中。"
                "需要重温某篇已打开文档时用 read_evidence(evidence_id)，然后按 next_step_guidance 继续。",
            },
        ]
        tail = messages[-5:] if len(messages) > 5 else messages
        messages[:] = head + tail


_BASELINE_ANSWER_MARKERS = ("最终答案", "答案是", "答案：", "答案:", "answer:", "Answer:", "答案为", "答案为：")
_ANSWER_NOISE_PREFIXES = ("根据", "我需要", "让我", "我有", "让我尝试", "让我先", "根据系统", "我需要读取", "根据已有")


def _clean_baseline_answer(text: str) -> str:
    """把模型交给 finish/提取的文本清洗成最短的答案片段。

    Qwen3.5-4B 常把检索计划或推理文本当作答案。这里裁掉含
    "我需要/根据/让我" 的计划性句子、多余引号与行首噪声，保留最长一句
    看起来像专有名词/事实陈述的内容；找不到就取文本最后一句。
    """
    text = text.strip()
    if not text:
        return text
    # 去掉外层引号/书名号
    text = text.strip("\"'“”《》")
    # 拆分句子
    import re as _re

    parts = _re.split(r"[。！؟\n]+", text)
    parts = [p.strip(" '\"“”()（）：:，,").strip() for p in parts if p.strip()]
    if not parts:
        return text[:128]
    # 跳过计划性/操作性的句子
    real = [p for p in parts if not p.startswith(_ANSWER_NOISE_PREFIXES) and len(p) < 80]
    if real:
        return real[-1][:128]
    return parts[-1][:128]


def _extract_baseline_answer(messages: list[dict[str, Any]]) -> str | None:
    """从 assistant 文本里提取一份可提交的最佳猜测答案。

    baseline 模型常把答案写在普通文本里而不调用 finish。这里从最近的
    assistant 消息中，优先取"最终答案/答案/answer"标记后的文本；没有标记时
    退而取最近一条 assistant 主体文本，并做 [答案清洗]。
    """
    candidates: list[str] = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        matched = None
        for marker in _BASELINE_ANSWER_MARKERS:
            idx = content.find(marker)
            if idx != -1:
                tail = content[idx + len(marker):].strip()
                if tail:
                    matched = _clean_baseline_answer(tail)
                    break
        candidates.append(matched if matched is not None else _clean_baseline_answer(content))
    if not candidates:
        return None
    candidate = max(candidates, key=lambda c: len(c)) if any(
        c for c in candidates if c and not c.startswith(_ANSWER_NOISE_PREFIXES)
    ) else candidates[-1]
    return candidate[:512] if candidate else None
