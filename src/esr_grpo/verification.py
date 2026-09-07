"""答案验证接口。

在线 verify_answer 与 Benchmark Judge 分离。前者只决定 TaskState 是否需要继续
搜索；后者在 episode 结束后提供最终奖励。
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol, Sequence

from .models import Evidence, VerificationResult, VerificationStatus


class Verifier(Protocol):
    def verify(self, question: str, answer: str, evidence: Sequence[Evidence]) -> VerificationResult: ...


@dataclass
class KeywordVerifier:
    """测试用确定性验证器；正式实验不得把它当作 Benchmark Judge。"""

    required_terms: tuple[str, ...] = ()

    def verify(self, question: str, answer: str, evidence: Sequence[Evidence]) -> VerificationResult:
        combined = "\n".join(item.content for item in evidence).lower()
        missing = [term for term in self.required_terms if term.lower() not in combined]
        if not answer.strip():
            missing.insert(0, "当前答案为空")
        if missing:
            return VerificationResult(
                VerificationStatus.NEEDS_REVISION,
                tuple(f"缺少可核对信息：{item}" for item in missing),
                "规则验证未通过",
            )
        return VerificationResult(VerificationStatus.SUPPORTED, (), "规则验证通过")


@dataclass
class OpenAICompatibleVerifier:
    base_url: str
    model: str
    api_key_env: str = "ESR_VERIFIER_API_KEY"
    timeout_seconds: float = 120.0
    max_tokens: int = 1536
    # 校验与策略复用同一个模型（Qwen3.5-4B, --max-model-len 32768），Verify 是
    # 独立的新上下文，只喂 Question + Answer + Referenced Raw Evidence。32768 token
    # 足够容纳 supporting_evidence 引用的全部原文。这里仅作极端保险（单条 Evidence
    # 异常巨大时不至于 400），不为省上下文而丢弃任何一条被引用证据。
    evidence_char_budget: int = 480_000
    per_evidence_char_cap: int = 60_000
    # verify 是高频、确定性的状态审计：关闭模型的 thinking，让它直接输出干净 JSON，
    # 既加速又避免思考块污染解析。策略侧仍然开着思考，二者是不同上下文、不同配置。
    enable_thinking: bool = False

    def verify(self, question: str, answer: str, evidence: Sequence[Evidence]) -> VerificationResult:
        segments: list[str] = []
        total = 0
        for item in evidence:
            content = item.content
            if len(content) > self.per_evidence_char_cap:
                # 单条原文异常超长时，仅裁该条尾部并标注，避免断言丢失上下文。
                content = content[: self.per_evidence_char_cap]
            seg = f"[{item.evidence_id}] {item.source.title}\n{content}"
            if total + len(seg) > self.evidence_char_budget:
                # 被引用证据整体超出模型上下文预算：判为 needs_revision，提示证据过多，
                # 而不是静默丢弃 —— 否则验证会基于不完整证据下"通过"结论。
                return VerificationResult(
                    VerificationStatus.NEEDS_REVISION,
                    ("被引用的原始证据过长，超出校验上下文预算，请精简 supporting_evidence 后重新验证",),
                    "referenced evidence exceeds verify context budget",
                )
            segments.append(seg)
            total += len(seg)
        evidence_text = "\n\n".join(segments) if segments else "(无可用证据)"
        prompt = (
            "你是严谨的答案审计员，只输出一个 JSON 对象："
            '{"verification_status":"supported|needs_revision","gaps":["具体待解决问题"],'
            '"rationale":"简短理由"}。supported 时 gaps 必须为空。请勿输出 JSON 以外的任何内容。\n\n'
            "判断规则（按顺序）：\n"
            "1. 实体身份：答案应当给出一个『可指认的实体名』（人名/公司/作品/事物等），"
            "而不是一句搜索计划/过程描述。只要答案给出了一个实体名，且该名字能以任何形式"
            "（含拼写变体、简写、别称，归一化后）出现在提供的证据原文里——例如证据明确谈到某"
            "人物/作品/年份，而答案给出的名字与之匹配——即判满足『实体身份』，**不得**因答案未"
            "完整重述全名、未逐字复述题干身份线索、或把链上某一环当作目标等措辞问题而拒绝。\n"
            "2. 证据支撑：答案的核心实体/时间/关系是否被原始证据整体支持？判断时以证据全文为准，"
            "只要证据里实在地包含支持该答案的关键事实（人物名、作品名、年份、事件），即视为满足，"
            "**不要**强求题干里的每一个约束短语都逐字出现在证据里，也不要把『仅一个修饰性子句未字面出现』"
            "上升为不通过。\n"
            "3. 仅当答案是明确的搜索计划/过程描述或空/'暂无候选'（而非实体名）时，才判 needs_revision。\n\n"
            f"问题：{question}\n当前答案：{answer or '(空/暂无候选)'}\n\n原始证据：\n{evidence_text}"
        )
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": self.max_tokens,
        }
        if not self.enable_thinking:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        headers = {"Content-Type": "application/json"}
        api_key = os.getenv(self.api_key_env)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        result = self._post(url, body, headers)
        content = result["choices"][0]["message"]["content"].strip()

        def _try_parse(text: str) -> tuple[bool, VerificationResult] | None:
            """尝试把一个模型输出解析为 VerificationResult；None 表示可重试的 unparseable。"""
            try:
                parsed = json.loads(self._extract_json(text))
                status = VerificationStatus(parsed["verification_status"])
                gaps = tuple(str(item).strip() for item in parsed.get("gaps", []) if str(item).strip())
            except (ValueError, KeyError, json.JSONDecodeError, TypeError):
                return None
            if status is VerificationStatus.SUPPORTED and gaps:
                gaps = ()
                status = VerificationStatus.SUPPORTED
            if status is VerificationStatus.NEEDS_REVISION and not gaps:
                gaps = ("当前答案未通过校验，请修正 answer 与 supporting_evidence",)
            return (True, VerificationResult(status, gaps, str(parsed.get("rationale", ""))))

        parsed = _try_parse(content)
        if parsed is None:
            # unparseable 不做一票否决：4B 在格式上波动时，给一次『只输出干净 JSON』的重试，
            # 而不是直接把正确轨迹压成永久 needs_revision（q1089/391/83 实证这类误杀）。
            # 仍失败才收敛为 needs_revision（保守，不让 un-parseable 放行），且文案引导模型
            # 只需重发『干净 JSON』，不必重搜证据。
            retry_body = dict(body)
            retry_body["messages"] = [
                {
                    "role": "user",
                    "content": (
                        "你刚才的输出不是一个干净的 JSON 对象，无法解析。请重新输出**仅一个**"
                        '合法 JSON 对象，格式严格为 {"verification_status":"supported|needs_revision",'
                        '"gaps":["..."],"rationale":"..."}，不要包含任何 JSON 以外的文字、代码块、'
                        "思考或解释。基于同样的题目、答案和证据重新判定，不要改变判定立场。"
                    ),
                }
            ]
            retry_result = self._post(url, retry_body, headers)
            retry_content = retry_result["choices"][0]["message"]["content"].strip()
            parsed = _try_parse(retry_content)
        if parsed is None:
            # 两次都 unparseable：仍保守判 needs_revision（不阅读证据），但明确告知是格式问题，
            # 且不下任何『搜更多证据』的指令——模型只需重查干净 JSON 即可。
            return VerificationResult(
                VerificationStatus.NEEDS_REVISION,
                ("校验机输出无法解析为结构化 JSON，请重新调用校验、直接提供干净的 verification_status 判定。",
                 "当前 answer 与 supporting_evidence 无需修改，仅需让校验机输出干净 JSON。"),
                "verifier returned unparseable output after retry",
            )
        return parsed[1]

    def _post(self, url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        """发一次 chat/completions 请求，带指数退避重试。

        - 5xx / 超时 / 连接错误：瞬时可自愈（并发高负载下 vLLM 偶发 503/超时），
          自动重试最多 3 次（间隔 2s/4s），避免把"服务瞬时抖动"烧成模型 7 连重试
          （bad case 1044 实证：verifier 峰值负载下连续 HTTPError，模型按
          _verify_service_glitch 原地重试全失败而烧完轮次）。
        - HTTP 4xx 属请求本身问题（重试无用）：若带 chat_template_kwargs 被后端拒绝
          （非必需参数），去掉该参数重试一次；否则把响应体带进异常抛给上层。
        """
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(3):
            request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    pass
                if exc.code < 500:
                    # 4xx：请求本身问题，重试无用；若带非必需 chat_template_kwargs 去掉重试一次。
                    if exc.code in (400,) and "chat_template_kwargs" in body:
                        retry = dict(body)
                        retry.pop("chat_template_kwargs", None)
                        return self._post(url, retry, headers)
                    raise RuntimeError(f"verify chat/completions HTTP {exc.code}: {detail}") from exc
                last_error = RuntimeError(f"verify chat/completions HTTP {exc.code}: {detail}")
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last_error = RuntimeError(f"verify chat/completions 网络错误: {exc}")
            if attempt < 2:
                time.sleep(2 ** attempt * 2)  # 2s, 4s
        raise last_error if last_error else RuntimeError("verify chat/completions 重试耗尽")

    @staticmethod
    def _extract_json(content: str) -> str:
        """从模型输出里提取最终输出的严格 JSON 对象。

        verify 已通过 chat_template_kwargs 关闭 thinking（见 enable_thinking），
        正常应直接得到干净 JSON。但保留防御性解析：万一某轮仍混入思考文本或
        示例 JSON，用 json.JSONDecoder.raw_decode 依次扫描，收集所有能独立解析
        成完整 JSON 对象的片段，取【最后一个】作为最终输出。
        """
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        decoder = json.JSONDecoder()
        candidates: list[str] = []
        i = 0
        n = len(content)
        while i < n:
            if content[i] not in "[{":
                i += 1
                continue
            try:
                obj, end = decoder.raw_decode(content, i)
            except ValueError:
                i += 1
                continue
            if isinstance(obj, (dict, list)):
                candidates.append(content[i:end])
            i = end
        if not candidates:
            raise ValueError(f"verifier content contains no JSON object: {content[:200]!r}")
        return candidates[-1]
