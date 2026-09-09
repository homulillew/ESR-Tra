# 研究核对记录

检索日期：2026-09-09。以下文献只供离线设计，不进入被测模型上下文。当前未进行训练或新增在线模型组件。

补充正文核对：读取了 [AgentFold 第 3 节](https://arxiv.org/html/2510.24699v1) 的上下文构成和训练说明。其模型学习如何更新摘要并保留最近一次完整交互；论文明确依赖训练数据生成和监督微调。不能把本轮无训练的引用反馈修复称为该方法的复现。

还读取了 [ToolMaze 第 3.5、4 节](https://arxiv.org/html/2606.05806v1) 对恢复率与恢复成本的定义及讨论。它将遇到错误后的恢复与最终任务成功分开，也统计无效尝试的代价。本轮据此分别报告协议恢复、正式提交准确率和全部调用，但不照搬需要已知最短恢复路径的指标：BC+ 本次没有这样的路径真值。上述为正文方法核对，未复现论文实验，也未读取其案例用于被测提示。

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

## 2026-09-09：由实际评分争议触发的补充核对

pilot 有一次提交包含参考名称及其所属地点的限定说明，judge 仅因附加信息判错。原分数保留，标为疑似误判，不能把它作为题目困难的证据。另一题遗漏原问题明确要求的引号，判错有直接依据。这两种情况必须分开。

以下均只核对作者的一手摘要和版本信息，未复现实验或完整审查正文，不将论文数值当作本项目的校准结果。

| 来源与日期 | 对应问题与最小做法 | 预测、消融及决定 |
|---|---|---|
| [Explaining Length Bias in LLM-Based Preference Evaluations](https://aclanthology.org/2025.findings-emnlp.358/)，EMNLP Findings，2025-11 | 偏好比较可能受长度影响；本例却是附加文字被罚，偏差方向与任务不同，不能直接套用。仅记录答复长度与争议。 | 固定语义的合成长度变体可检验敏感性，但不改变 BC+ 原评分。拒绝把长度校正胜率用于答案正确率；无新增在线调用。 |
| [How Long Reasoning Chains Influence LLMs' Judgment of Answer Factuality](https://arxiv.org/abs/2604.06756)，首次 2026-04-08，v2 2026-08-07 | 给 judge 更多推理不保证更准确，流畅解释可能影响判断。继续只给原问题、已提交答案和参考答案。 | 预测：加入内部轨迹可能改变判分且不稳定。拒绝用 policy 内部 finding/audit 说服 judge，不增加推理链审核组件。 |
| [Nine Judges, Two Effective Votes: Correlated Errors Undermine LLM Evaluation Panels](https://arxiv.org/abs/2605.29800)，v1 2026-05-28 | 多模型投票也可能共享错误，重复同一路由更不能假定独立。保留原分及离线争议说明。 | 不采用“重判直到通过”或未经校准的投票，避免额外成本。真正独立的复核仍是限制，不能由重复一致替代。 |
| [LLMs are Biased Evaluators But Not Biased for Fact-Centric Retrieval Augmented Generation](https://aclanthology.org/2025.findings-acl.1369/)，ACL Findings，2025-07，超过最近 12 个月 | 作为反证：该研究的事实型 RAG 设置未观察到显著自偏好，说明偏差依任务而定。 | 不能仅因 policy/judge 同路由就宣称本实验有确定方向的偏差；结论依实际争议和敏感性分析，保留相关误差风险。 |
