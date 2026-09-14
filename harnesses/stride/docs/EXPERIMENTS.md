# STRIDE a3 实验合同

当前版本 `0.1.0a3 / stride-search-3`。a2 的恢复机制与 a3 的 CPU/原文连续性机制都可以独立消融；没有真实模型或 BC+ 效果时，不允许把合成 fixture 结果写成性能结论。

## 1. 三层证据不能混用

1. **离线契约测试**：证明程序对构造输入如何执行；不证明模型会自然选择该动作。
2. **固定失败前缀续程**：证明一个机制改变了后续行为；不证明完整任务泛化。
3. **自然配对任务**：同模型、同索引、同预算、同来源规则下比较正式正确率和成本，才用于任务收益判断。

所有 fixture 明确标记为 synthetic，不进入论文准确率分母。

## 2. q26 之后的推荐实验顺序

不要一次打开所有新功能后再解释谁有效。推荐：

1. **检索能力说明 on/off**：CPU 索引、排名、cache、shelf 全固定，先测试模型知道真实 OR/BM25 能力是否减少低收益搜索。
2. **evidence shelf = 0 / 3**：能力说明保持相同，测试关键已交付原文跨裁剪可见性的收益与输入代价。
3. **recall_navigation on/off**：测试是否减少重新搜索已收到但未打开的卡片。
4. **centered_recall on/off**：只比较摘录位置，不改评分和来源规则。
5. `compiled_query_cache` 默认 off；另做工程成本消融，因为它可能少 CPU 后端执行，但不会少 policy 决定。
6. notes、FINAL、a2 recovery 的旧消融继续保留，不与 a3 新机制混成单一贡献。

已研究的 q26 属开发诊断，不能当未见确认样本。

## 3. make_plan 允许的差异

当前允许的 harness-only ablation：

- `notes_enabled`
- `reserve_finish`
- `context_mode`
- `max_batch`
- `max_queries_per_search`
- `nonblocking_notes`
- `repair_context`
- `delivery_preflight`
- `disclose_retriever`
- `compiled_query_cache`
- `evidence_shelf_size`
- `recall_navigation`
- `centered_recall`

model、retriever identity、counter、require_sources、答案字面合同和所有未声明预算保持一致。一次正式比较应只改变一个主要假设；工具宽度对照要同时处理 `max_batch` 与 `max_queries_per_search`，否则一个 search 内仍可隐藏多个查询。

## 4. 样本与标签隔离

`questions.jsonl` 每行只能有唯一 `id` 与 `question`。`answer/gold_docid/labels` 等字段直接拒绝。被测 policy 不得看到 gold、旧成功查询或旧 bad-case 人工分析。

开发任务用于定位机制，冻结后再用未参与设计的确认任务做正式评价。重复同一道题可以分析随机性，但不增加任务多样性，统计时按题分组。

## 5. 冻结身份与代码

开始前记录并冻结：

- 实际模型请求名、部署/版本标签、temperature/thinking 等生成配置；
- 实际返回模型标识；
- CPU 索引 `index_id`、metadata digest、SQLite runtime、适配器 capability digest；
- 完整 Config；
- counter identity；
- `source_hashes()` 和完整运行队列。

代码改变后生成新计划，不覆盖旧实验。名称相同不等于模型权重或索引字节完全相同，报告中保留这一限制。

## 6. 预算与失败

`run_plan` 只在显式的 `max_total_model_calls` 足以覆盖冻结队列最坏情况时启动。所有模型尝试计入预算；本 harness 没有默认 auditor/summary model。

基础设施、模型身份、完整性或 provider 错误停止后续队列；已运行记录保留，其他 slot 为 NOT_RUN。正常任务预算耗尽保留失败后可继续后续 slot。禁止自动补跑、换账号、换模型或跨日“恢复额度”。

后端调用、native tool、search 内 query、模型请求、input/output/cache tokens 和 wall time 分开统计，不把它们混成一个“工具轮数”。

## 7. 独立判分

运行时没有内置答案 oracle。`submitted`、合法 refs、`semantic_status=not_automatically_verified` 都不是 formal correct。

全部 rollout 结束后，外部 judge 或人工评测使用原题、正式答案和冻结的 benchmark 合同生成：

```json
{"slot":"0000","head":"exact-ledger-head","correct":true}
```

judgment 必须绑定已完成 submitted ledger head。未判分时 accuracy 为 null；NOT_RUN 不能当正确、错误或零成本成功。

## 8. 过程诊断

建议离线记录：

- 首次相关搜索命中；
- 首次必要原文实际交付；
- shelf 保留/驱逐；
- 首次明确候选；
- 正式 finish；
- query compiler equivalence 与结果集合重复；
- 重读同一 snapshot/range；
- notes 写入/noop/删除；
- recall 来源类型；
- 最终 refs 覆盖哪些原子断言。

“必要证据充分”是离线诊断标签，不应变成运行时 gold oracle。qrels 命中文档也不等于必要段落已经交付或支持最终关系。

## 9. 主指标

必须同时报告：

- 完整预登记分母的 formal accuracy；
- `B错→新方案对` 与 `B对→新方案错`；
- policy/model attempts；
- backend SQL/get_document；
- native actions 与 search 内 queries；
- input/output/cache tokens；
- wall time；
- 已知与 unknown usage。

在准确率相当区间比较成本前沿。只减少检索请求、只提高提交率、只让上下文更短或只减少非法调用，均不能替代联合目标。

## 10. 单题自然复测

对 q26 的一次性开发复测合同见 [CODEX_Q26_RETEST_PROMPT](CODEX_Q26_RETEST_PROMPT.md)。它要求版本门禁、持久预算、同一 CPU 索引、禁止把旧答案/查询注入 policy，以及完整私有轨迹封存。该单题只用于机制诊断，不用于声明 STRIDE 泛化优于 ESR。
