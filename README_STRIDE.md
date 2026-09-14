# STRIDE a3：CPU 检索与原文连续性

新增方案在 [`harnesses/stride`](harnesses/stride/README.md)，独立安装、独立测试，不改写 `esr_harness`、`esr_harness_v3` 或 `esr_grpo`。

它以固定强模型的 BC+ 前向实验为目标，去掉 claim 清账、常驻候选草稿与默认 auditor，保留可恢复原文、原生工具回执、精确引用边界和预算内的显式终答。当前是协议实现与离线验收，不是已取得 BC+ 性能提升的系统。

方案推导见 [DESIGN](harnesses/stride/docs/DESIGN.md)，实验合同见 [EXPERIMENTS](harnesses/stride/docs/EXPERIMENTS.md)，a2 恢复合同见 [RECOVERY_A2](harnesses/stride/docs/RECOVERY_A2.md)。

最新 a3 迭代基于已发布 a2：保持 CPU SQLite FTS5 OR/BM25，不引入 GPU、embedding、reranker 或额外模型；补齐检索器能力声明、编译查询诊断、有界已交付原文保留、历史搜索卡片恢复和命中位置摘录。详细设计见 [CPU_EVIDENCE_A3](harnesses/stride/docs/CPU_EVIDENCE_A3.md)，验证见 [VALIDATION_A3](harnesses/stride/docs/VALIDATION_A3.md)。

这些机制不会自动判断来源是否支持答案，也不会把 submitted 当作 formal correct。真实 q26、BC+、judge 与训练仍需独立授权和实验；已知开发题不能作为未见泛化结果。
