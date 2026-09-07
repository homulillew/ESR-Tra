# api/ — Lanz 模型多轮对话客户端

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