# 提示层：按能力选择，不累积个案禁令

2026-09-08。本轮不改变 State 2.1、ledger schema 3、hard/soft/off 的判定语义或训练算法。

## 单一职责

- `src/esr_harness/prompts.py`：共同研究原则、baseline/ESR 分支、hard/soft/off 结束规则、审核原则及两个动态提醒；策略版本 `research-2.1.1`，审核版本 `atomic-2.1.1`。
- `protocol.py`：工具参数与机械使用规则。模式化参数通过 `Config.tool_schema()` 同时用于展示和执行检查；baseline search 不暴露 ESR 的 focus/anchor_refs。
- `context.py`：渲染当前状态和实际尝试，不把历史日志改写成新的系统规则。baseline 不收到“写 finding / dismiss”的提醒。
- `runner.py` / `audit.py`：只组装适用内容和 schema，不再各自维护长主提示词。

| profile | state 操作 | verify_answer | 结束 |
|---|---|---|---|
| baseline | 无 | 无 | finish |
| ESR/off | 有 | 无，也无调用指令 | submit_answer，unverified |
| ESR/hard | 有 | 有 | 当前审核 supported 才可正常提交 |
| ESR/soft | 有 | 有 | 有效当前审核后可提交；保留真实 verdict |

ESR 各模式均可显式 abstain。审核允许基于明确前提做逻辑和算术推导，但不得用记忆事实或 gold 补缺失前提。个别赛事、人物、单位案例进入回归材料，不继续扩张在线禁令。

## 复现与检查

真实 system message = 模式化原则 + 同模式工具描述/schema，不仅是某一个字符串常量。`tests/harness_v21/fixtures/prompt_profiles.json` 固定四种实际 system message 及审核文本的 SHA256 快照；`test_prompt_profiles.py` 检查能力匹配、baseline 动态工作卡、引用原文不变及日志版本/hash。

CLI manifest 记录策略版本及完整 system hash；每个 decision 记录版本、system hash 和完整 messages hash；auditor identity 含精确审核文本 hash。修改提示词后开启新实验目录，不用旧 episode 的 resume 混跑。只读 replay 仍查看当时的实际记录。

```bash
python -m pytest -q tests/harness_v21/test_prompt_profiles.py
python -m pytest -q
```

完整文本见 prompts.py 和真实 decision.messages，system hash 覆盖拼接后的工具/schema。快照变化需人工审查文字差异，不能为了通过测试盲目刷新。测试通过证明接口一致性，不证明 4B 会遵循或准确率提升。

服务器端编程 agent 的实验任务见 [FORWARD_VALIDATION_PROMPT.md](FORWARD_VALIDATION_PROMPT.md)。那份文档是实验执行者提示，绝不能拼入被测 4B policy/auditor 的请求。
