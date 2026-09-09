# 研究核对记录

检索日期：2026-09-09。以下文献只供离线设计，不进入被测模型上下文。当前未进行训练或新增在线模型组件。

| 来源与版本 | 阅读范围、证据等级 | 当前问题、最小可借用机制 | 成本、预测、消融与决定 |
|---|---|---|---|
| [AgentFold: Long-Horizon Web Agents with Proactive Context Management](https://arxiv.org/abs/2510.24699)，首次/当前 arXiv v1 2025-10-28 | 摘要与版本页；原作者一手说明，未复核实验 | 整段历史压缩可能丢细节；需要保留可重读原文及桥接事实 | 本轮不引入学习式 folding。预测：保留原文访问只解决可恢复性，不能保证模型会主动恢复。后续需独立测试正文是否真正进入下一请求。不能把训练后收益归于无训练补丁。 |
| [MEM1: Learning to Synergize Memory and Reasoning for Efficient Long-Horizon Agents](https://arxiv.org/abs/2506.15841)，首次 2025-06-18，v2 2025-07-17 | 摘要与版本页；原论文，早于最近 12 个月，作为经典参照 | 紧凑记忆和推理需要协调；对应 finding 覆盖旧关系 | 不采用训练或在线额外总结器。预测：单纯缩短上下文不必提高准确率；需与完整历史 baseline 比较。 |
| [When Tools Fail: Benchmarking Dynamic Replanning and Anomaly Recovery in LLM Agents](https://arxiv.org/abs/2606.05806)，首次/当前 v1 2026-06-04 | 摘要与版本页；一手预印本，未复现实验 | 区分显式执行错误、隐式语义错误与恢复；对应真实 fixture 的格式重复失败 | 采用分类方法，不照搬新控制器。预测：原生工具接口减少外层 JSON 格式错，仍不能解决语义引用错误。消融：同一合成任务、相同 schema、仅改变传输表达；保留失败。 |
| [Robust Tool Use via Fission-GRPO: Learning to Recover from Execution Errors](https://arxiv.org/abs/2601.15625)，首次 2026-01-22，v2 2026-04-20 | 摘要与版本页；一手论文，页面标注 ACL 2026 | 错误后反复调用、难以解释反馈；对应完整提案在下一回合丢失 | 本轮仅保留提案和明确错误，不引入 Error Simulator、重采样训练或最终奖励调整。可证伪预测：固定有效前缀中，一个错误字段可在一次修复机会内更正。 |
| [When Should Multi-Round RAG Stop? Structured Stopping Judgments and Retrieval Reduction in Search-R1](https://arxiv.org/abs/2608.13237)，首次/当前 v1 2026-08-13 | 摘要与版本页；单篇新预印本，尚未独立验证 | 检索减少不等于总推理成本减少，也可能轻微损害准确率；对应 ESR 审核/停止 | 作为反证检查采用：独立报告工具、模型、token、正确完成时间。不引入额外停止 judge；若研究审核时机，必须单独消融并计全部费用。 |

本轮已确认的第一个真实断点：合成 Orin 任务的文本 JSON 模式在 a2 开始省略 arguments，12 动作中 9 个非法；a6 的候选和引用已正确提交，但后续无法完成审核。原始运行保留为失败，不能算 BC+ 成绩。原生工具探针返回 `stop_reason=tool_use`，这是网关当前支持该接口的直接证据，不是准确率改善证据。

评价协议核对：[BC+ 官方 evaluate_with_openai.py](https://raw.githubusercontent.com/texttron/BrowseComp-Plus/main/scripts_evaluation/evaluate_with_openai.py) 与 [官方 prompts.py](https://raw.githubusercontent.com/texttron/BrowseComp-Plus/main/search_agent/prompts.py)，读取 grader 模板及调用/解析实现。官方采用独立答案匹配判断；本轮不得用子串判断替代。若复用 policy 路由做离线 judge，明确模型相关误差，不宣称独立模型。

CPU 检索依据：[SQLite FTS5 文档](https://www.sqlite.org/fts5.html)；这是另建的 FTS5 BM25 索引，使用完整 BC+ corpus，不等同于下载的 Lucene BM25 索引。[Pyserini 当前文档](https://github.com/castorini/pyserini)要求 Java 21 并主要面向 Python 3.12，本机默认 Python 3.13 且无 Java。两臂统一采用新 CPU 检索器，不能与旧实验直接归因比较。
