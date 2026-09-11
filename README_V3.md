# ESR v3：低编号负担研究工作区

本分支从 `main@6ee9c4a` 增加独立的 `esr_harness_v3`，不替换旧 v2 或 GRPO 训练代码。

三份主要文档分别是：

- [方案分析](docs/v3/ANALYSIS.md)：bad case、减负决策、有限论文吸收、与 v2 的差别。
- [完整方案与实现规范](docs/v3/DESIGN.md)：引用、状态、上下文、六工具、审核/提交、预算、日志和明确实现边界。
- [后续调试测试迭代 Prompt](docs/v3/ITERATION_PROMPT.md)：可交给后续编程 agent 的离线—固定前缀—自然任务—训练闭环。

[实际验证记录](docs/v3/VALIDATION.md) 不等于真实模型或 BC+ 效果报告。

```bash
python -m pip install -e '.[test]'
python -m pytest tests/harness_v3 -q
python -m esr_harness_v3 smoke --db /tmp/esr-v3-new.sqlite
python -m esr_harness_v3 replay --db /tmp/esr-v3-new.sqlite
python scripts/validate_v3.py --output /tmp/esr-v3-validation-new
```

重点实现：add/revise、统一 refs、请求快照冻结 this、已交付原文、历史恢复、局部依赖版本、修订边界、独立 checks 审核、精确答案包、直接提交、原生工具回执、预算、SQLite 回放和采样信息导出。

真实运行需 `run --allow-network`、显式请求上限、已配置服务和与服务端一致的本地 tokenizer。默认 smoke 和测试不使用 API 密钥，不调用真实模型。OpenAI-compatible HTTP 适配器已做本地 fixture 往返；真实供应商和 BC+ 仍需验收。

`esr-harness-v3 export --require-rl` 对缺失精确 token/logprob/span 的记录拒绝放行；本版没有实现或宣称完成 GRPO 优化器训练。不要用文本重分词伪造训练对齐。
