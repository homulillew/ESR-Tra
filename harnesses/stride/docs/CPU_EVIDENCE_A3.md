# STRIDE a3：CPU 检索合同与原文连续性

## 目标与依据

版本 `0.1.0a3`，协议 `stride-search-3`，从已发布的 `badc82df`（a2）增量开发。本轮保持 CPU，没有引入 GPU、embedding、重排模型、总结器或 verifier；不修改旧 ESR，不把 CPU 硬件约束当成 bug。

依据是 ESR `ac8d1bb` 的单题公开报告：主要原文在第 6 轮取得，7–15 轮继续辅助检索；第 16 轮读错人物，第 18 轮裁剪后主线退出输入；第 28 轮才保存两条复合 finding，引用范围又不完整。[1] 这些是作者对本地完整轨迹的分析，不是本轮重放或正式判错。本轮没有取得私有 q26 全文、原始模型消息或生产语料。

CPU 与查询语义是两个维度。这里尊重已经使用的 CPU FTS5 OR/BM25 路线，补齐模型可见合同，而不是默认升级检索器或把 OR 改为 AND。新功能分开配置；合并发布不是一个可以归因的多变量效果实验。

## 1. 原生 CPU 接入与真实能力声明

新增 `SQLiteFTS5`，通过 `--sqlite-index` 读取已经建好的 `metadata/docs/search` 索引，与 `--retrieval-url` 互斥。不开新索引、不改写原库。连接使用只读 URI、query_only 和单局读事务，结束时关闭连接；多局 factory 的连接也在 finally 关闭。

查询仍为：`query.lower()` → `re.findall(r'\w+')` → 首次出现去重 → 各词加引号并 OR → `ORDER BY bm25(search),d.docid`。snippet 参数、top_k 和返回 score 保持旧 LocalIndex 规则。八组自造查询逐项比较 docid、排名、snippet、score；这是合成 SQL 等价检查，不是全库检索评测。

`"Mira Stone"` 和 `Mira Stone` 在此后端具有相同编译表达式；`site:target.example` 并不限制 URL，词可能参与普通匹配。增加词仍会影响 BM25 排名，并非所有改写都无效。工具声明会明确这些语义、固定语料范围以及 title 实际来自 URL。HTTP/未知适配器不会被强行标成 CPU OR；未声明的能力如实标为 unknown。

`disclose_retriever=True` 把适配器提供的能力数据放入每次控制视图；`False` 是同代码说明消融。能力来自部署代码，不从网页指令推断。当前视图也明确 `max_batch`、每次 search 查询数、来源要求。没有开启服务端 strict 或声称网关完全实现它。

## 2. 编译后查询诊断与可选缓存

每次 search 保存 `query_execution`：原始 query、top_k、编译结果、等价 key、实际缓存 key、缓存命中。CPU 适配器保存本地 SQL 参数；没有额外查询或模型调用。索引身份由声明标签、metadata hash、SQLite 运行版本和适配器能力指纹绑定，不冒充再次遍历生产语料得到的字节级证明。

默认 `compiled_query_cache=False`，维持原始 query 的缓存条件。显式开启时，仅复用编译表达式和 top_k 完全相同的结果，保留原 query。词序不排序，top_k 不合并，也不把同义词或不同人名当作等价；未知适配器退回原字符串。查询组的未缓存预算按不同实际 key 预检，防止相同编译表达式在同批被重复预留。

缓存减少的是 CPU 后端工作，不是生成重复查询的 policy 决定。`equivalent_query_repeats` 不等于无效搜索次数；失败的后端尝试也会留在诊断表里。

## 3. 有界原文保留区，不是 claim 状态或自动重要性判断

`evidence_shelf_size=3` 默认保留最近三个**不同、已确认交付窗口**的原文恢复资格。顺序来自显式 first-delivery order，不依赖字典序，也不被纯搜索或一次无关阅读整体替换。已有窗口重读不重排这条顺序。设为 0 可独立关闭；范围为 0–4。

构造上下文时，如果保留区窗口已经在选中的原生交互组中，不重复正文；如果旧交互组被裁剪，而窗口仍在保留区，直接呈现同一 eN、snapshot、start/end、hash、准确正文与文档标题。没有创建新证据身份、摘要或额外模型请求，也不要求先 notes。用户角色中的原文明确作为不可信 source data，不提升为系统指令。

只从 exposed 集合恢复：刚刚创建但尚未实际交付的窗口、被 a2 预检撤下的结果，不能借保留区变成可引用来源。最新完整回执组继续受保护。容量压力下先裁旧组、导航、便笺与修复预览，仍不足时整窗退出保留区，最早窗口优先，并记录 `shelf_evicted_for_capacity`；不截断原文、不隐瞒撤下。若最新完整组仍不容纳，继续使用 a2 的明确 result_capacity 恢复。

这不是永久 pin，更不是“关键证据永不丢失”：超过三个窗口或预算不足时仍会退出。保留无关/错误原文可能增加 token 和锚定风险。该规则只是对“没有及时写笔记便完全丢失主线”的低成本候选，必须评估保留收益和上下文代价。没有实现依赖撤销或正确性评分。

## 4. 历史导航与可定位摘录

只在完整模型响应确认输入后，将该输入实际呈现的成功 search 回执纳入 navigation_history。回放同一组不会重复登记。仅存在 archive、未进入输入、或被容量预检撤下的命中，不纳入此目录。

`recall_navigation=True` 让 recall 搜索这些已收到但未必打开过的搜索卡片，返回原 dN、原 query、来源轮次及保存的 snippet。同一文档多个命中去重。它仍是导航，不能出现在 finish.refs；必须 read 才取得可引用 eN。该能力避免模型只能再次外部搜索，不能保证一定召回所有别名或隐含关系。

`centered_recall=True` 对 raw-window 导航和 search snippet 给出围绕字面命中位置的**原始子串**，同时返回局部 start/end 和坐标基准。它不把摘要当证据、不向窗口外扩展。评分仍是词面重叠，排序按得分、同分类型优先级（原文导航、搜索卡、便笺）、明确顺序；不是语义检索。命中仅在标题/query 中时正文摘录可能没有该词。

find 新增显式 `ignore_case`，默认 false 保持原严格字面行为；true 使用 Python Unicode 正则 IGNORECASE，不是分词器或完整 Unicode casefold 等价。匹配 start/end 始终相对于原字符串，不能在 lower/casefold 扩展后的文本上偷换偏移。没有匹配只能说明该字面查找没命中。

## 5. 引用与任务正确性的界限

不加入旧 ESR 的 pN 字符片段映射或复合 claim。每个 eN 与完整窗口正文相邻，finish 明确要求选择用于复合答案断言的全部原文窗口。跨窗主体、时间与金额仍需模型显式选择多个 refs；程序不自动补邻窗，更不按 q26 题号补事实或约束。

合法来源不代表支持答案。回归保留“第二任人物＋合法原文”仍可 submitted 且 semantic_status=not_automatically_verified 的负向示例，防止把结构测试解释成正确率。a3 不会因为补齐目录就修复关系推断错误，也不把 submitted 当 independent judge=true。

## 6. 控制与离线诊断

| 配置 | 默认 | 单变量对照 |
|---|---|---|
| disclose_retriever | true | --hide-retriever-capabilities |
| compiled_query_cache | false | --compiled-query-cache（显式开启） |
| evidence_shelf_size | 3 | --evidence-shelf-size 0 |
| recall_navigation | true | --no-recall-navigation |
| centered_recall | true | --prefix-recall-excerpts |

make_plan 允许这些差异，并继续冻结模型、索引、预算、来源与答案合同。a2 的三项恢复机制原样保留。a1/a2 账本仍可只读检查；旧计划不能在新协议下隐式执行。多项全部开启 vs a2 只能作整系统比较，不能归因给某一模块。

`stride-search diagnose --db EPISODE` 只读导出 query hash、编译等价统计、逐轮可见窗口/保留区和最终选择 refs，formal_correct 保持 null。默认不展示原查询或正文；`--include-text` 显式展示 query/compiled，结果应留私有。诊断不运行模型、不重查生产索引、不修改过去轨迹、不用金标文档当在线 oracle。

首项自然实验仍建议只比较 capability on/off，其余固定（尤其 compiled cache 保持 off）。之后比较 shelf=0/3，再分别比较历史目录、摘录方式。已研究 q26 属开发诊断，不做未见样本；每次重新生成后缀，保留所有失败与费用。没有授权则不启动真实模型请求。

## 7. 原始来源与可复核边界

[1] ESR q26 公开分析（单题、未正式判分；私有原文未取得）：https://github.com/homulillew/ESR-Tra/blob/ac8d1bb9a158efb4c442e7bd59d08d50ac5b5354/docs/v3/iterations/20260914_single_api_review.md

[2] CPU 查询原实现：https://github.com/homulillew/ESR-Tra/blob/ac8d1bb9a158efb4c442e7bd59d08d50ac5b5354/scripts/trace_single_v3.py

[3] a2 发布基底：https://github.com/homulillew/ESR-Tra/commit/badc82df9bfabc374ded7e8cf1b281815c46be88

本轮效果边界、首次失败与实跑统计见 VALIDATION_A3.md。不会由三项脚本反例通过推算真实 BC+ 准确率或净省请求比例。
