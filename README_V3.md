# ESR v3：低编号负担研究工作区

本分支从 `main@6ee9c4a` 增加独立的 `esr_harness_v3`，不替换旧 v2 或 GRPO 训练代码。

三份主要文档分别是：

- [方案分析](docs/v3/ANALYSIS.md)：bad case、减负决策、有限论文吸收、与 v2 的差别。
- [完整方案与实现规范](docs/v3/DESIGN.md)：引用、状态、上下文、六工具、审核/提交、预算、日志和明确实现边界。
- [后续调试测试迭代 Prompt](docs/v3/ITERATION_PROMPT.md)：可交给后续编程 agent 的离线—固定前缀—自然任务—训练闭环。

[实际验证记录](docs/v3/VALIDATION.md) 不等于真实模型或 BC+ 效果报告。

2026-09-11 独立审查新增 42 项回归，当前 v2/v3 联合 **270 项通过**。本轮修复了审核反应额度、服务失败停止、原响应与执行动作一致性、部分 usage、恢复身份和训练导出边界；[审查报告](docs/v3/iterations/20260911T111515Z_f67a902.md) 保留首次失败与完整限制。真实模型和 BC+ 仍为 NOT_RUN。

```bash
python -m pip install -e '.[test]'
python -m pytest tests/harness_v3 -q
python -m esr_harness_v3 smoke --db runs/esr-v3-new.sqlite
python -m esr_harness_v3 replay --db runs/esr-v3-new.sqlite
python scripts/validate_v3.py --include-legacy --output runs/esr-v3-validation-new
python -m esr_harness_v3 cohort-fixture --output runs/esr-v3-cohort-new
```

重点实现：add/revise、统一 refs、请求快照冻结 this、已交付原文、历史恢复、局部依赖版本、修订边界、独立 checks 审核、精确答案包、直接提交、原生工具回执、预算、SQLite 回放和采样信息导出。

真实运行需 `run --allow-network`、显式请求上限、已配置服务和与服务端一致的本地 tokenizer。默认 smoke 和测试不使用 API 密钥，不调用真实模型。OpenAI-compatible HTTP 适配器已做本地 fixture 往返；真实供应商和 BC+ 仍需验收。

`esr-harness-v3 export --require-rl` 对缺失精确 token/logprob/span 的记录拒绝放行；本版没有实现或宣称完成 GRPO 优化器训练。不要用文本重分词伪造训练对齐。

所有输出使用新的路径。验收目录保留 SQLite、导出、stdout/stderr、JUnit、源码及产物哈希；`runs/` 默认不推远程。`cohort-fixture` 验证 this 开关与队列记录，`cohort-summary` 只读汇总，`prefix` 导出实际保存的请求；它们不提供 BC+ 判分，也不将 `this_off` 当作无 ESR baseline。
