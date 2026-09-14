# STRIDE 设计：从研究行动到明确提交

当前版本 `0.1.0a3`，协议 `stride-search-3`。a2 的恢复合同见 [RECOVERY_A2](RECOVERY_A2.md)；q26 bad case 驱动的 CPU/原文连续性迭代见 [CPU_EVIDENCE_A3](CPU_EVIDENCE_A3.md)；实验控制和实际验证见 [EXPERIMENTS](EXPERIMENTS.md)、[VALIDATION_A3](VALIDATION_A3.md)。

STRIDE 是固定强模型、固定文本语料场景下的前向 harness。它不训练参数，不加入默认 auditor，不声称当前已经提高 BC+ 准确率或降低工具轮数。

## 1. 设计目标

历史 ESR 暴露了多类不同问题：无关状态管理阻止提交、finding 与最终 answer 分离、最后一轮只保存草稿、多调用边界、正确反馈没有落实；q26 又说明另一类问题来自搜索后端语义、关键原文跨裁剪消失以及最终引用覆盖不足。

因此 STRIDE 的中心对象不是“完整 verified claim graph”，而是**实际行动与已经交付的观察**：

- 程序保证对象身份、不可变原文、请求/回执配对、预算和可恢复档案；
- 模型负责选择查询、解释材料、可选便笺和明确 finish；
- 合法来源只表示有资格引用，不等于来源蕴含答案；
- 没有默认 claim 清账、常驻 draft、强制审核或自动答案修正。

## 2. 状态与工具

运行状态可写作 `S=(A,H,N,B,Z)`：

- `A`：文档导航、冻结快照、eN 原文窗口、已交付集合；
- `H`：完整原生 assistant/tool 交互组和当前工作视图；
- `N`：小型可选 notes；
- `B`：模型、行动、后端、输出和时间预算；
- `Z`：RESEARCH、FINAL 或终态。

工具为 `search/read/find/recall/notes/finish`。最短正常路径可以是 `search → read → finish`；notes、find、recall 都不是必经步骤。

只有实际进入请求并获得完整响应确认的 eN 才是可引用 raw evidence。search/find/recall 的 snippet/位置只是导航；后台已经有全文不等于模型已经读过。

## 3. CPU 检索合同

`SQLiteFTS5` 直接读取已有 CPU FTS5 索引，不构建新库、不需要 GPU。当前规则与 q26 的 LocalIndex 对齐：小写、正则提词、首次出现去重、各词 OR、`bm25(search)`、docid 同分排序。

这意味着：

- 引号不形成姓名短语过滤；
- `site:` 不形成 URL 域过滤；
- AND/OR 文本不会变成布尔操作；
- 增加词仍可能改变 BM25 排名，因此不能把所有改写自动视为无效；
- capability 会显式放入控制视图，避免模型把本地 CPU 索引误当作网页搜索引擎。

每次 search 记录原始 query、编译表达式、equivalence key 和 cache 状态。编译后精确缓存默认关闭；开启后只减少相同实际表达式的 CPU 工作，不减少产生重复 query 的模型决定。

## 4. 上下文与有界原文保留

默认 rolling 模式保留原生交互；容量不足时退出旧完整组，不调用摘要模型。

a3 增加 `evidence_shelf_size=3`：最近三个不同且**已经确认交付**的原文窗口，在旧原生组退出后仍可以原样重新呈现。它复用相同 eN/snapshot/start/end/hash，不创建新证据身份，也不需要 notes。

边界：

- 未交付或被容量预检撤下的窗口不能进入 shelf；
- 如果当前组已经包含该原文，不重复；
- shelf 不是重要性模型，错误或无关原文也可能被保留；
- 超出数量或容量时整窗退出并记录，不暗中截断；
- 它只缓解“没有及时写状态就立即丢主线”的问题，不提供依赖失效、真伪判断或永久记忆。

## 5. 历史导航与定位

`recall_navigation=True` 可检索此前实际交付过的 search 卡片，以及已交付 eN 和 note 历史。搜索卡片仍然只是 navigation，不能直接用于 `finish.refs`；必须 `read` 得到 raw evidence。

`centered_recall=True` 返回围绕字面命中位置的原始子串和偏移，不生成摘要。`find(ignore_case=true)` 提供大小写不敏感的字面查找，同时保持原字符串偏移；它仍不是实体解析、别名搜索或语义检索。

## 6. a2 恢复合同继续生效

- 非关键、schema 合法且 anchors 已交付的少数 notes 可用性错误，不再自动连带阻止独立合法 finish；关键读取/来源/服务错误仍阻断。
- 完整但没有合法动作的输出，可在下一次请求以有界 `uncommitted_response_not_evidence` 呈现；不自动提取或提交答案。
- 完整工具结果若会使下一合法请求超容量，可明确撤下整个数据 payload，记录 `result_capacity`，后台档案保留但不形成交付或引用资格。

这些机制都没有额外模型调用，也都有可关闭的单变量开关。

## 7. FINAL、预算与精确答案

最后一次模型机会、最后一个行动槽或输出预算只够一个最大响应时，可进入 FINAL，只暴露 finish。模型必须显式提交准确字符串和已交付 refs，或 abstain。

程序不从问题/gold 推断引号或单位，不捞草稿、不自动补字符。FINAL 机会不等于正确提交；如果模型输出散文、错误来源或错误格式，仍可失败。

## 8. 存储与供应商边界

SQLite 使用内容寻址对象和追加事件，保存实际请求、provider 原响应、后端结果、action execution/result、原文窗口和终态。只读 replay 检查事件链、对象 hash、索引和证据身份；哈希链不是抗恶意全库重写的密码学签名。

OpenAI-compatible 与 Anthropic 适配保留原生工具 ID 和回执；截断、模型身份变化、网络/鉴权错误不自动重试或切换 provider。ByteCounter 使用 UTF-8 bytes，不冒充服务端 token 计数；实际部署必须校准。

## 9. 可反驳的研究假设

- H1：减少 claim/draft/audit 手续，可减少“证据已足够但尚未正式提交”的额外决定。
- H2：真实检索能力说明能减少把本地 OR 索引当网页 search engine 使用造成的低收益查询。
- H3：有界原文 shelf 能降低关键原文因一次后续错误阅读而退出上下文的概率，但会增加输入并可能保留错误材料。
- H4：历史导航和命中位置摘录可减少重新搜索／重新定位，但它们仍是词面工具。

任何机制只有在同模型、同索引、同预算的自然配对中改善正式正确率—成本前沿，才算任务收益。提交率、合法 refs、缓存命中或中间状态变化都不能替代最终正确率。
