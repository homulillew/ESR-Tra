# ESR: Evidence-State Research

## 当前入口：前向 Harness v2

本仓库包含 ESR-GRPO 的历史研究快照，以及从 bad case 归纳出的 **ESR forward harness v2**。
新一轮先验证前向推理，不修改 GRPO、reward、credit mask 或训练集划分。

**新推理统一使用 `esr_harness`，不要继续往历史驱动中叠补丁。**
`src/esr_grpo/`、`analysis-L/`、旧 `scripts/` 和 `results/` 保留用于历史复现，
不会被新版 import 或自动替换。旧方案中的“harness 完美／100% verifier 问题”等结论不作为新版的已证事实。

| 入口 | 用途 |
|---|---|
| [方案设计](docs/harness/DESIGN.md) | 当前唯一的前向协议与设计说明 |
| [运行与迁移](docs/harness/RUNBOOK.md) | CPU smoke、4B 在线推理、只读 replay |
| [验证记录与验收边界](docs/harness/VALIDATION.md) | bad-case 回归、已执行测试、尚未验证项 |
| `src/esr_harness/` | 新前向实现，不依赖旧 harness |
| `tests/harness_v2/` | 新协议的自动化回归和本地 HTTP 集成测试 |
| [历史 README](docs/archive/README_snapshot_20260907.md) | 旧快照原始索引，仅作历史材料 |

历史基线：`040710279e591162d793883cd64f8b1ae424a759`，已保留到
`archive/pre-harness-v2-20260907`。新旧 SQLite schema 不兼容，**不自动迁移旧账本**。

## 核心变化

1. **实际观察是不可变对象。** `open_page` 保存实际返回的片段、原文偏移和 hash；`read_evidence`
   原样重放；审核直接读取这些已存视图，不重新跑检索来猜当时看到了什么。
2. **状态紧凑且审核幂等。** 目标、必要条件、候选答案与 observation 引用分开；no-op update
   不刷新版本；相同审核输入命中缓存；gap 以稳定 claim ID 表示，不通过改写句子伪造修复。
3. **协议错误不是语义缺证。** JSON／服务／超窗故障不创建 gap；硬审核不放过 unknown／contradicted；
   软审核允许显式结束但不把它伪装成 supported；abstain 是独立终态。
4. **统一运行与预算。** 基线与 ESR 共用检索、观察及请求客户端；policy 与 audit 是独立新上下文；
   实际 tokenizer 做上下文检查，策略和审核共享生成预算；非法输出也受有限动作预算约束。

## 快速验证（不需要 GPU）

```bash
python -m pip install -e '.[test]'
python -m pytest -q tests/harness_v2
python -m esr_harness smoke --store /tmp/esr-v2-smoke.sqlite
python -m esr_harness replay /tmp/esr-v2-smoke.sqlite
```

smoke 是**合成协议测试**，不是 BC+ 成绩，也不代表 4B 的语义能力。
已有同名 smoke 账本时换新路径；不覆盖历史文件。

## 4B 单题推理示例

先确保已有 OpenAI-compatible 模型服务，以及原有 ECHO/BM25 服务。
`--tokenizer` 必须对应服务端实际 chat template；示例路径、模型别名、端口应替换为本机实际值。

```bash
python -m pip install -e '.[model]'
python -m esr_harness run \
  --dataset /path/to/bcplus.jsonl --qid 324 \
  --mode esr --audit-mode hard \
  --policy-url http://127.0.0.1:8005/v1 \
  --model Qwen3.5-4B --model-revision YOUR_PINNED_REVISION \
  --tokenizer /path/to/Qwen3.5-4B \
  --retrieval-url http://127.0.0.1:8000 --retrieval-revision YOUR_INDEX_REVISION \
  --max-actions 64 --max-context-tokens 32768 \
  --max-output-tokens 2048 --max-total-completion-tokens 24000 \
  --store runs/harness-v2/q324-hard.sqlite
```

policy 与 auditor 默认复用同一个 4B endpoint，但**不复用会话历史**。
审计模式必须显式选择，避免把门禁变化混成模型能力变化。
题目 loader 只取 question/query；gold answer 和 gold docid 不进入请求。
q324 等已分析题只用于开发回归，不应再作为未见测试题。

## 验证状态

本轮在 Python 3.13.5 下完成 **100 个新测试**、CPU 修复 smoke 和本地 HTTP 协议集成测试。
没有连接原训练机上的真实 Qwen3.5-4B／BM25 服务，没有重跑全量 BC+，没有执行训练。

机械协议通过回归测试，不等于语义审核永远正确。新版明确保留真实模型校准和预算对照验收；
`soft/off` 不可和 `hard` 混报 supported 精度。旧 `ExactMatchJudge` 是子串 smoke judge，
不在新推理入口中使用；正式 benchmark 判分仍需单独固定并校准。

**训练尚未迁移。** v2 日志是推理／调试数据，不包含可直接用于 RL 的精确采样 token/logprob/span
协议。不要将其无适配地交给旧 ECHO/verl credit router。
