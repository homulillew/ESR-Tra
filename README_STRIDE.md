# STRIDE a2：独立的读取优先搜索 Harness

新增方案在 [`harnesses/stride`](harnesses/stride/README.md)，独立安装、独立测试，不改写 `esr_harness`、`esr_harness_v3` 或 `esr_grpo`。

它以固定强模型的 BC+ 前向实验为目标，去掉 claim 清账、常驻候选草稿与默认 auditor，保留可恢复原文、原生工具回执、精确引用边界和预算内的显式终答。当前是协议实现与离线验收，不是已取得 BC+ 性能提升的系统。

方案推导见 [DESIGN](harnesses/stride/docs/DESIGN.md)，实验合同见 [EXPERIMENTS](harnesses/stride/docs/EXPERIMENTS.md)，真实执行边界见 [VALIDATION](harnesses/stride/docs/VALIDATION.md)。

本次包含独立新包与 a2 恢复改动。[RECOVERY_A2](harnesses/stride/docs/RECOVERY_A2.md) 说明外围便笺错误如何不连带阻止独立终答、如何呈现未提交输出，以及结果过大时如何明确拒绝交付并允许重试。没有伪造已读、自动补答案或增加模型调用。真实模型与 BC+ 仍为 NOT_RUN。
