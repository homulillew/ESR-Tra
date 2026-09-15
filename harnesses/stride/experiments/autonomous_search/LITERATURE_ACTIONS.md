# 原文交付与下一动作选择：证据和待检验机制

检索日期：2026-09-15。本文区分论文实测结果与本地可验证假设；不以标题或摘要相似性宣称复现。

[Is Grep All You Need? How Agent Harnesses Reshape Agentic Search](https://arxiv.org/html/2605.15184v1)，2026-05-14，在 116 道 LongMemEval-S 上比较内联结果和文件指针。GPT-5.4/Codex 的两种交付路径分别为 93.1% 和 55.2%，Chronos 下为 89.7% 和 87.1%；Haiku/Chronos 两者均为 83.6%。交付方式的作用依赖模型和框架。任务使用会话记忆与预处理时间事件，不能据此推出 BM25 自动读取首条结果能稳定改善难题。

[Fetch-then-Explore: Decoupling Selection from Extraction over a Persistent Workspace for Search Agents](https://arxiv.org/html/2608.02097v1)，2026-08-03，将网页选择与原文提取分开，并在每题工作目录保留选中文档。Qwen3.5-35B 的 BrowseComp 准确率中，Snippet-Only 为 27.5%，Open+Find 为 42.0%，Fetch-then-Explore 为 44.5%；移除 grep 后为 37.0%，移除 read 后为 39.5%。保留缓存但限制跨页检索的变体为 39.5%，低于 Open+Find。每题最多 300 轮、三次运行取最好；平均搜索、选择、提取次数分别为 58.3、5.4、6.7。这支持研究原文访问机制，也说明缓存或单次首页读取不足以解释完整收益。本文环境已经有原文缓存、find 和 read，不能把这些已有能力算作新贡献。

[Budget-Aware Tool-Use Enables Effective Agent Scaling](https://arxiv.org/html/2511.17006v1)，2025-11-21，研究在预算内安排规划、核验与重试。BrowseComp 早停消融中，完整方案为 18.7%，去规划为 17.0%，去核验为 15.4%，两者都去掉为 14.6%。完整系统有多个模块和更宽的工具预算，论文没有单独证明一次独立动作选择有效，更不能证明在这里省略一次助手散文会有效。

## 当前机制选择

公开失败轨迹表明，q774 在 R2/R3 已获得真实兄妹关系原文，仍围绕未证实候选搜索；q775 也存在读到冲突后继续追逐原候选的运行。因而“停滞时自动读首篇未读文档”只可能减少访问延迟，无法直接处理主要的候选与关系错误，本轮不实施它。

第五轮只测试一次性省略全部保留工具组的可见助手散文，包含首组与最新组。它以 [Agent-Omit](https://arxiv.org/html/2602.04284v1) 的位置干预和 [Buried in Textual Debt](https://arxiv.org/html/2608.22963v1) 的省略反例为依据，具体结果与限制见 LITERATURE_HISTORY.md。假设是暂时减少此前自述推测对一次新动作的影响；新模型响应仍使用现有执行器、原模型和预算。

这项实现没有独立规划器，也没有移除全部模型推理信息：notes、repair、工具参数、查询及提供方独立 reasoning 字段仍可能保留候选倾向。下一次普通请求还会继续原轨迹，旧推测可能重新影响模型。正确触发、实际省略或查询字符串改变都是过程检查；只有同题正确率和来源审阅结果才能支持保留该机制。
