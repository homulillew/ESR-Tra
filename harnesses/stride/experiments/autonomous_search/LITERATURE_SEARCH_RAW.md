# 搜索时交付原文窗口：文献证据与限制

核查截止 2026-09-15。以下三篇原论文研究搜索结果、全文读取和证据组织，可作为研究背景；它们没有直接证明，在相同 CPU、索引和完整请求预算下，自动附加少量原文窗口能够提高正确率。模型主动读取、持久保存页面、检索粒度变化及额外摘要模型的收益，均不能归因于自动打开结果。

## A-RAG：匹配句与全文读取

[A-RAG: Scaling Agentic Retrieval-Augmented Generation via Hierarchical Retrieval Interfaces](https://arxiv.org/html/2602.03442v1)，2026-02-03，§3、表 1–3。

搜索返回匹配句及所属文本块 ID，模型另行决定是否读取完整文本块。GPT-5-mini 的完整系统与移除 Chunk Read 相比，MuSiQue 的模型判分准确率为 74.1% 对 73.6%，HotpotQA 为 94.5% 对 93.6%；但 MuSiQue 的答案包含匹配率为 65.3% 对 67.0%，Med 准确率为 93.1% 对 93.3%。读取全文并非在所有指标上都有收益。

完整系统与仅有向量搜索工具的版本相比，MuSiQue 检索文本 token 为 5,663 对 56,360，准确率为 74.1% 对 66.2%。该对照同时改变检索工具、粒度及信息交付方式，不能隔离原文窗口的贡献。方法使用句向量和关键词分层索引；检索 token 也不等于累计 API 输入 token。论文没有提供相同 CPU 和全部后端成本下的自动打开对照。

## Fetch-then-Explore：持久页面与按需窗口

[Fetch-then-Explore: Decoupling Selection from Extraction over a Persistent Workspace for Search Agents](https://arxiv.org/html/2608.02097v1)，2026-08-03，§4.1、表 2、5。

Fetch-then-Explore（FtE，先保存页面、再按需提取证据）固定搜索后端与推理框架：fetch 保存全文，仅返回元数据；grep/read 再交付带行号的原文窗口，不使用辅助摘要模型。Qwen3.5-35B-A3B 在 BrowseComp 上的准确率为 FtE 44.5%、Open+Find 42.0%、Visit-Snippet 30.5%。保留工作区、移除 read 后降至 39.5%，移除 grep 后降至 37.0%。

共同上限为每题 300 轮，实际成本不同：FtE 平均搜索/页面选择/提取调用为 58.3/5.4/6.7，Open+Find 为 58.1/5.0/1.0。负结果是 WideSearch 上 FtE 的行级 F1 为 34.3，低于使用额外摘要模型的 Visit-Summary 的 35.5。论文报告工具调用数，但没有建立相同总 token、CPU 成本的优势；持久存储与按需访问也不同于搜索时自动附正文。

## Similar Accuracy, Unequal Evidence：可见证据不同，准确率接近

[Similar Accuracy, Unequal Evidence: Search APIs as Decision Surfaces for Tool-Using Agents](https://arxiv.org/html/2607.10198v2)，2026-09-13 修订版，表 2、附录 D；[版本记录](https://arxiv.org/abs/2607.10198)。

固定 GPT-5.4、10 轮上限、每次至多十个结果及共享页面抓取后端，比较 Brave、Tavily、Firecrawl。100 题正确数分别为 25、25、26；平均搜索调用为 2.29/2.74/2.51，抓取调用为 1.02/1.30/1.28，报告的每题 token 为 59,627/54,156/57,979。可见证据和调用模式存在差异，准确率接近；这不构成统计等价证明。

实验明确只在模型选择 fetch 后交付页面正文，没有自动打开。更换供应商同时改变覆盖、排名与摘要文字，不能隔离响应格式。额外 Kimi 模型用于离线证据标注，不是零成本在线核验；事后 oracle 的互补性也不是已测可部署策略。

## 对实验结论的约束

这些论文支持分别测量证据覆盖、实际读取和最终回答，尚不支持预先断言自动原文窗口有效。确定性读取即使不增加模型请求，也会增加后端工作和上下文负担。比较时需同时报告实际模型请求、后端尝试、交付原文量及累计输入 token；共同预算上限不能替代实际成本比较。
