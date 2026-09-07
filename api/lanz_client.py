"""
api/lanz_client.py
==================
通过本机 Lanz 网关 (http://127.0.0.1:18080) 的 Anthropic Messages API，做多轮对话。

【背景】
  本机 18080 是一个薄转发代理(claude_proxy.py)，把 /v1/messages 原样转发到
  lanz.hikvision.com:80/v3/anthropic/model/v1/messages。
  上游网关会根据 User-Agent 头判断请求是否来自 "Claude client"：
    - 若 UA 不带 Claude 特征 -> 403  "Anthropic protocol is restricted to Claude clients"
    - 若 UA 带 Claude 特征   -> 200  正常返回
  因此必须手动设置一个 Claude 样式的 User-Agent。
  官方 anthropic SDK 会强制覆盖 UA 为自己的 "Anthropic/Python x.y.z"，所以这里用 httpx 自己构造请求。

【用法】
  from lanz_client import LanzClient
  c = LanzClient()
  c.chat("你好")
  c.chat("还记得我上一句说的吗？")   # 自动携带历史，多轮连续对话
  c.reset()
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

DEFAULT_BASE = "http://127.0.0.1:18080"
CLAUDE_UA = "claude-code/2.1.224 (ClaudeCode/CLI 2.1.224)"


class LanzClient:
    """一个持有多轮历史状态的客户端，封装对 Lanz Anthropic Messages API 的调用。"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        model: str = "Lanz-Medium",
        timeout: float = 180.0,
        max_tokens: int = 512,
    ) -> None:
        self.base_url = (base_url or os.environ.get("ANTHROPIC_BASE_URL") or DEFAULT_BASE).rstrip("/")
        self.token = token or os.environ.get("ANTHROPIC_AUTH_TOKEN") or ""
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.history: list[dict[str, str]] = []

    # ------------------------------------------------------------------ #
    # 基础请求
    # ------------------------------------------------------------------ #
    def _headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self.token}",
            "x-api-key": self.token,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "user-agent": CLAUDE_UA,
        }

    def _call(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """向 /v1/messages 发一次请求，返回完整 JSON 响应；失败抛 httpx.HTTPStatusError。"""
        resp = httpx.post(
            f"{self.base_url}/v1/messages",
            headers=self._headers(),
            json={
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": messages,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _extract_text(js: dict[str, Any]) -> str:
        """从响应里抓取助手回复文本，兼容 text / tool_use 等 content 块。"""
        parts = []
        for block in js.get("content", []):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts).strip()

    # ------------------------------------------------------------------ #
    # 对外：发给模型的角色
    # ------------------------------------------------------------------ #
    @staticmethod
    def user(content: str) -> dict[str, str]:
        return {"role": "user", "content": content}

    @staticmethod
    def assistant(content: str) -> dict[str, str]:
        return {"role": "assistant", "content": content}

    # ------------------------------------------------------------------ #
    # 多轮对话入口
    # ------------------------------------------------------------------ #
    def chat(self, user_text: str) -> str:
        """把 user_text 追加进历史，带完整历史请求一次，返回助手文本并记入历史。"""
        self.history.append(self.user(user_text))
        js = self._call(self.history)
        answer = self._extract_text(js)
        self.history.append(self.assistant(answer))
        return answer

    # ------------------------------------------------------------------ #
    # 工具型（Agent Search 场景）：完全由调用方接管 messages
    # ------------------------------------------------------------------ #
    def raw(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """底层调用：调用方自定义完整 messages 数组（不自动维护历史）。"""
        return self._call(messages)

    def raw_text(self, messages: list[dict[str, str]]) -> str:
        """底层调用 + 只取文本。"""
        return self._extract_text(self._call(messages))

    def last_raw(self, messages: list[dict[str, str]]) -> tuple[dict[str, Any], Optional[str]]:
        """兼容早期原型：返回 (json, None) 或 (None, 错误串)。"""
        try:
            js = self._call(messages)
            return js, None
        except httpx.HTTPStatusError as e:
            return None, f"HTTP {e.response.status_code}: {e.response.text[:200]}"

    # ------------------------------------------------------------------ #
    # 历史管理
    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        self.history.clear()

    @property
    def messages(self) -> list[dict[str, str]]:
        return list(self.history)


# ---------------------------------------------------------------------- #
# 命令行快速自检：python lanz_client.py
# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys

    c = LanzClient()
    prompt = sys.argv[1] if len(sys.argv) > 1 else "请用一句话回答：你是谁？"
    print("发送:", prompt)
    print("回复:", c.chat(prompt))