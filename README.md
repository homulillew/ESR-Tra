# ESR: Evidence-State Research — forward harness 2.1

本分支实现低维护负担的4B研究工作区：**原始证据 → 局部finding → 当前focus.need → 下一项操作**。结束前独立审核，保留hard/soft/off的真实语义。

**当前入口是`esr_harness` 2.1。** 这是一版可测试的前向协议，不是已通过真实4B/BC+评测的最终模型。main和所有历史实验保持独立；训练算法、reward、credit router未改。

| 入口 | 用途 |
|---|---|
| [设计规范](docs/harness/DESIGN.md) | State、动作、gap、上下文、审核与终止 |
| [提示词分层](docs/harness/PROMPTS.md) | 按模式选择原则、工具契约和提示快照 |
| [服务器前向验证提示词](docs/harness/FORWARD_VALIDATION_PROMPT.md) | 交给服务器编程 agent，自动执行有界开发验证 |
| [运行和迁移](docs/harness/RUNBOOK.md) | CPU smoke、4B服务CLI、旧账本只读回放 |
| [验收记录](docs/harness/VALIDATION.md) | 已执行协议测试与未验证边界 |
| [前期分析与q324推演](docs/research/state_21/README.md) | 原分析、RFC、Schema与真实材料事后推演归档 |
| `src/esr_harness/` | 新前向实现；`state.py`纯delta，`context.py`工作卡 |
| `src/esr_harness/v2/` | 冻结旧实现，仅用于旧协议复现/回放 |
| `src/esr_grpo/`, `analysis-L/`, `results/` | 历史研究与训练代码，未自动迁移 |

## 主要变化

- 模型只更新变化部分；finding与引用成对，系统保留未改条件并分配ID。
- answer允许null，focus可先于答案存在；候选是猜测，不是默认检索前提。
- search关联当前缺口；固定索引的完全相同请求使用缓存，近似query不被关键词规则封禁。
- 实际曝光与工具返回分开记账；最新结果受保护，已引用证据重读不会被历史裁剪吞掉。
- 审核缓存不受focus或尝试摘要变化影响；同候选补证与换候选分开记录。
- 已识别反证保留来源，删除普通引用不能把冲突隐藏；unknown不是false。
- usage未知时保守占用请求上限；abstain/预算终态保留draft但不打捞成绩。

## 协议测试

```bash
python -m pip install -e '.[test]'
python -m pytest -q
python -m esr_harness smoke --store /tmp/esr21-smoke.sqlite
python -m esr_harness replay /tmp/esr21-smoke.sqlite
```

smoke与HTTP测试使用确定性fixture，不调用真实模型或BC+检索。旧测试通过versioned import继续运行，未将旧状态静默解释成新状态。新账本schema=3，旧schema=2只读分发，不自动迁移。

**训练仍未迁移。** 新日志保存真实请求文本、输出、decision/action/exposure及作用域，但不包含可直接用于RL的精确采样token、old logprob和segment mask。不要无适配交给旧ECHO/verl router。
