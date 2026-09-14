# STRIDE a2：有界恢复合同

本次基于 0.1.0a1 的反事实检查 P09/P10/P11/P20/P21 实现三项局部改动。它们分别对应外围便笺阻塞独立终答、协议修复缺少待修对象、完整结果组超容量。依据是合成机械场景，不是新的 BC+ 自然失败频率。版本为 `0.1.0a2`，新实验协议 `stride-search-2`，不训练参数、不增加 auditor 或总结模型。

## 非关键便笺错误

`nonblocking_notes=True` 时，只有 notes 的 `notes_capacity`、`notes_disabled`、`final_only`、`finish_slot_reserved` 可以不阻止同批后续 finish。同时必须满足：完整参数通过 schema，所有 anchors 属于决定生成时已交付的 evidence，没有此前的关键错误。FINAL 中 notes 仍不执行，错误与已发生费用仍记录；回执的 `blocks_finish=false` 表达明确合同。

错误参数、未知来源、超批量、未知工具、关键读取失败、服务/身份/截断/完整性错误不会因此放行。关键错误状态按 OR 累积，不会被随后非关键错误清除。finish 仍必须最后、独立校验准确答案和全部引用。它不能使用本响应刚 read 出来但尚未交付的证据。

对照：`nonblocking_notes=False`；CLI `--strict-note-failure`。这仅是当前代码的单变量消融，不等于完整旧 a1。

## 短期修复上下文

完整但没有工具调用的响应，以及可恢复的原生调用结构错误，产生短期 `uncommitted_response_not_evidence`。视图包含来源轮次、错误、可见输出 SHA256 与原长度，最多 1200 字符的头尾预览；省略明确标为 truncated。完整可见文本和原 provider 响应仍留档。

视图位于下一次请求的控制数据，不是 system 指令、证据、常驻草稿或正式答案，不制造悬空 assistant/tool 配对。它不复制 provider thinking/signature 块，不自动提取答案、补标点或提交。模型必须自行生成新的合法动作。

下一个完整响应到达即清除旧视图；新错误可建立新视图。容量不足时可省去预览，但保留 hash、长度和 `omitted_for_capacity`，不声称全文已被模型看到。最后一次只输出散文仍可能失败，不提供免费补发。

对照：`repair_context=False`；CLI `--no-repair-context`。

## 完整结果组的交付预检

工具执行首先记录 `action_execution`，表示实际提取，不是已经向模型承诺了成功回执。整批结束、正式 action_result 落账前，以同一个 provider.prepare 和容量计数器预演下一次完整输入：原题、全部 assistant 调用、逐项回执、控制数据、便笺及输出预留。

如果放不下，按序列化字节大小优先撤下最大的成功数据 payload，同大小优先后项。可撤下对象仅为 search/read/find/recall 结果；不是相关性判断，不是摘要。完整原结果保存为对象并写入 `result_withheld`，正式回执为 `result_capacity`，明确 `archived_not_delivered=true`，提示减少读取范围、top_k 或批次。

被撤下结果的 documents/evidence 不进入本组交付集合。后台快照、窗口、缓存、后端成本与行动槽保留，不伪装回滚。每个 native call 仍有回执，不删除整个最新组，不暗中缩短原文。未交付 eN 不可猜测引用；通过已收到的 dN 再请求相同范围，可复用快照，在后续真实交付后再引用。

如果连原题、assistant 参数及简短错误组都放不下，记录预检失败，下一请求仍明确 context_capacity。已终止或没有下一次模型/行动/输出预算时不进行无意义预检。该机制不能保证 provider tokenizer 准确、网络时限或未来所有请求均可容纳。

对照：`delivery_preflight=False`；CLI `--no-delivery-preflight`。关闭预检时也不能虚报已交付。

## 状态、计数与兼容

保持 A/H/N/B/Z（档案、交互、便笺、预算、阶段），只加短期修复视图；不恢复 claim 图、语义 verified state 或训练路由。新增事件中的对象引用接受完整性校验；删除修复或被撤下结果对象会被检测。旧 stride-search-1 账本可只读检查且保留原协议身份，不支持执行 resume。旧计划不能在新代码下隐式运行。

report 单列恢复事件和非阻断便笺失败数。它们不是修复成功率、任务进展或最终正确率。结果预检不调用模型或检索；缩小范围的实际重试仍需 policy 决定并计入预算。

## 实验与未解决问题

`examples/recovery_comparison.py` 生成六局同代码单变量脚本对照及实际请求/SQLite。脚本知道合成答案，只证明路径可达；不能据此估计真实模型净省多少请求。完整验收见 VALIDATION.md。

后续先做固定失败前缀的真实续程，再做同模型、索引、正文窗口、来源规则与总预算的自然配对。特别看 B 错/新方案对和 B 对/新方案错，不以提交率或合法引用代替准确率。

未解决：错误答案仍可引用合法原文；默认不从题目推断格式合同；recall 不检索未读搜索卡片，摘录仍为开头片段；find 仍严格字面匹配；便笺没有依赖撤销；无自动 resume、无语义 verifier、无真实 BC+ 成绩。本轮不把这些未证实机制一起加入系统。
