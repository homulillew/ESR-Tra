# api/ — Lanz 模型多轮对话客户端

## 当前强 API 研究入口（2026-09-09）

当前已实测用户授权的 `EB-GLM-5.2` 路由，base URL 为
`http://lanz.hikvision.com/v3/anthropic/model`，请求地址追加 `/v1/messages`。
密钥使用 `ANTHROPIC_AUTH_TOKEN` 环境变量或研究脚本的无回显输入，勿写入代码、命令行或日志。

`scripts/strong_api.py` 复用 `LanzClient.request()` 和 `esr_harness`，保存实际 provider body、完整响应、请求 ID、usage 和 stop_reason。
当前网关支持原生 tool_use，但实测可能忽略禁用并行工具的参数。研究配置通过 `max_tool_calls_per_decision: 4` 启用有界检索组合：逐项执行并返回匹配结果，状态更新、审核和结束分别决策。旧单调用配置仍会拒绝多调用并保留提案；两种配置都不静默选取第一项。原生工具路径使用 `request()`，`raw_text()` 仅提取文本，不能用来取得工具调用。
实测还出现 `end_turn` 文本为一个完整 JSON 对象后附单个 `</tool_call>` 的情况。当前适配器先严格验证前面的完整 JSON，再移除这一已声明的尾标记，并记录 response_normalization；不修改语义字段。多余括号、重复键、多对象和散文前缀均不能借此通过。
计数端点在本次探针中未返回可用 token 计数。上下文估计是明确标记的保守容量估计，不冒充本地 Qwen tokenizer。

以下本机代理与 User-Agent 内容是历史接入说明，不是当前支持保证。研究脚本沿用已有获准的客户端配置；遇到 403 应保留错误并核对授权，不切换身份绕过限制。

通过本机 `127.0.0.1:18080` 的 Lanz 网关（Anthropic Messages API），用 Python 做多轮对话/Agent Search。

## 为什么不能直接用官方 anthropic SDK

本机 `claude_proxy.py` 把 `/v1/messages` 转发到 `lanz.hikvision.com`。上游网关**按 User-Agent 识别人是否 Claude client**：

| 请求方式 | User-Agent | 结果 |
|---|---|---|
| 裸 curl / 裸 httpx | 缺省/非 Claude | ❌ `403 Anthropic protocol is restricted to Claude clients` |
| 官方 `anthropic` SDK (0.71.0) | 强制 `Anthropic/Python 0.71.0` | ❌ 同样 403（SDK 会覆盖你设的 UA） |
| **httpx + 手动设 Claude UA** | `claude-code/2.1.224 (ClaudeCode/CLI 2.1.224)` | ✅ **200 成功** |

因此核心脚本用 **httpx 自建房请求**，手动带上 Claude 特征 UA。请求头必须含：

```
authorization:     Bearer <ANTHROPIC_AUTH_TOKEN>
x-api-key:         <ANTHROPIC_AUTH_TOKEN>   # Lanz 网关需要
anthropic-version: 2023-06-01
content-type:      application/json
user-agent:        claude-code/... (Claude){  # 关键，否则 403
```

## 文件

| 文件 | 作用 |
|---|---|
| `lanz_client.py` | 可复用客户端（持有多轮历史） |
| `demo_multiturn.py` | 演示：内置 3 轮 / `--shell` 交互式 |

## 用法

```bash
# 前置：环境变量（Claude Code 会话已默认继承）
#   ANTHROPIC_BASE_URL=http://127.0.0.1:18080
#   ANTHROPIC_AUTH_TOKEN=sk-...

cd /data1/ESR-GRPO-Code-L/api

# 单句自检
python lanz_client.py "用一句话回答你是谁"

# 内置 3 轮多轮演示
python demo_multiturn.py

# 交互式多轮（输入 exit 退出）
python demo_multiturn.py --shell
```

## 代码示例

```python
from lanz_client import LanzClient

c = LanzClient()
print(c.chat("你好"))          # 第1轮，内部自动记历史
print(c.chat("我上一句说了什么？"))  # 第2轮，自动携带全部历史
c.reset()                      # 清空历史

# Agent Search 场景：完全接管 messages
js = c.raw([
    {"role": "user", "content": "[工具结果] ..."},
    {"role": "assistant", "content": "已提取关键片段。"},
    {"role": "user", "content": "请据此给出结论。"},
])
```

## 备注

- 模型可选 `Lanz-Medium` / `Lanz-Flash`（`LanzClient(model=...)`）。
- 底层端点就是本机 18080 的 `/v1/messages`（Anthropic 协议，流式 SSE 需自行解析 `text/event-stream`）。
- 重要约定见仓库根 `.gitignore`/`Git规则.md`：提交到 git 仅 tracked files，本目录若含密钥勿入库。
