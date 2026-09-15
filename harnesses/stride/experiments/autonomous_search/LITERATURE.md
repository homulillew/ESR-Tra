# Agent Search Harness 推理时优化：一手文献与最小实验建议

检索日期：2026-09-15。实际使用 web 搜索与 arXiv HTML 全文阅读；覆盖 2024–2026，重点核对 2026 年新文献。未调用 GLM，未读取私有答案文件，未修改产品代码。读取了 workflow_v1 的 RESULTS.md、README.md 以及 workflow.py/context.py。RESULTS.md 已含公开结果；本笔记不重述其中答案。以下“建议”是迁移假设，不是论文已经验证的本项目结论。

## 结论与当前实现的关系

最值得先试的是同一策略请求内的逐条件检查提示；第二步才是独立上下文中的一次候选验证调用；第三步是停滞时重建工作区并切换检索分支。三个机制分别可独立消融。不要一起改为完整多轨迹系统。

当前 workflow.ack 只在完全重复搜索时累计停滞，新查询字符串、新导航或新原文均能重置计数；因此它测量观测变化，不能判断题目条件是否得到满足。update_gap 记录明确标为未验证的模型判断且完全可选；增加字段不会自动带来行为。context.build 主要在容量不足时删除旧完整消息组，并恢复最近原文窗口；它没有主动消除错误候选的叙事影响。现有失败对应两个独立问题：导航没有转为原文，以及真实局部事实被当成候选满足所有条件。

## 核心一手文献

### FineVerify（2026-05-30；arXiv 2606.00660）

[原文](https://arxiv.org/html/2606.00660v1)，[作者代码](https://github.com/XuZhao0/fineverify)。问题先拆成固定条件，同一条件集用于所有候选，分别输出 supported/not_found/contradicted；重复候选缓存验证，全支持时提前停止。主实验把未找到与矛盾都映射为 0，支持为 1；这并非硬性矛盾淘汰。

表 1：相同四条轨迹条件下，GPT-5-mini 平均 FineVerify 67.4、整体置信验证 64.7、答案合成 66.3；单轨迹 59.2。因此“+8.2”包含采样收益，不能归于提示。Gemini 对答案合成仅高 0.1。表 2 将 not_found 当支持，使 GPT-5-mini BrowseComp-Plus 从 60.5 降至 50.5。检索用 Qwen3-Embedding-8B，与本项目 FTS 不同。免训练，但验证会检索，不能称一次额外模型请求。本文支持逐条件设计，不证明零额外调用版有效。

### DeepVerifier（2026-01-22；v2 2026-04-29）

[原文](https://arxiv.org/html/2601.15808v2)，[作者代码](https://github.com/yxwan123/DeepVerifier)。将易错点分解为至多三条定向核查，再让可用工具的验证 Agent 检查，给策略反馈。闭源模型推理流程免训练；DV-8B 结果包含微调，不能移作纯提示证据。

表 2 的错误拒绝 F1：完整 73.17、去工具验证 25.00、去分解 61.54。表 3 GAIA-Web Claude 从 51.11 到四轮 63.33，十轮 62.22；GPT-4.1 十轮仅 +2.22。表 4 XBench 最好 +6、最终 +3，BrowseComp 最好 +5、最终 +4。论文明确记录正确改错，故轮数不宜无限加。成本段给出至多三子问题和早停，未给可迁移的精确 HTTP 次数；一次反馈轮不等于一次请求。

### IterResearch（2025-11-10；ICLR 2026）

[全文 v1](https://arxiv.org/html/2511.07327v1)，[会议原文](https://openreview.net/pdf/a4f890b689f29253281375eb210e18b793833afb.pdf)。算法 1 在一次模型决策里生成更新报告和动作，再用原问题、报告、最近动作结果重建输入。§4.5 单独测试免训练 prompting，BrowseComp 对 ReAct：o3 +12.7 个百分点、DeepSeek-V3.1 +19.2。主模型六基准 +14.5 与 2048 交互扩展包含训练，不应作为最小修改预期。

报告可同请求生成，理论上不额外增加决策请求，但报告输出、工具内部网页摘要请求仍须计费。论文使用能按目标摘要的 Visit，与本项目冻结原文窗口不同。仅清空历史可能同时删除排除理由，必须保留原文及其来源。它证明重建范式有潜力，未证明本项目 16 请求内一次重建收益。

### Asymmetric Verification（2025-10-07；ICLR 2026）

[原文](https://arxiv.org/html/2510.06135v1)。在 BrowseComp，GLM-4.5 随 1→32 条轨迹 Pass@K 由 16 到 67；多数票未能充分转化潜在正确答案。附录 D 的 Heavy 使用 8–32 条轨迹、部分设置每候选四次验证，并非低成本单请求。XBench 中求解与验证接近同样困难，作者部分设置不使用验证。此文支持将搜索与验证分开计费、先测验证能否区分候选；不支持只延长同一失败轨迹。

### 最新反证与训练边界

- [What Does Context Compression Cost an Agent?](https://arxiv.org/abs/2608.16370)，2026-08-17：受控 24 回合环境，在 5 倍压缩下各组成功率差异不显著，但重新检索普遍增加；GPT-5.5 检索 21.0→63.9。ALFWorld 未出现同样现象。需要同时记录重新读取、模型请求与成功率，不能只统计输入长度。此为预印本环境实验，不是搜索基准直接复现。
- [AgentFold](https://arxiv.org/abs/2510.24699)，2025-10-28：主动多尺度折叠主要结果依赖监督微调。可启发保留哪些对象，不能把 36.2 BrowseComp 归于可插拔推理提示。
- [Can Transformers Learn to Verify During Backtracking Search?](https://arxiv.org/abs/2605.22221)，2026-05-21：在 SAT 等任务诊断历史干扰，结构性注意力隔离是主要实验；作者仅把预训练模型推理时清空上下文列作可能迁移，不是已验证 web-agent 方法。
- [Cost-effective Agent Test-Time Scaling](https://research.google/pubs/cost-effective-agent-test-time-scaling/)，作者机构页标 2026，强调 token 与工具调用合并计费；该页缺少充分表格和具体发布日期，本轮不以它支持定量增益。

## 三个可实现机制及消融

### 1. 在动作决策内逐条件检查（第一轮建议）

只新增下节通用提示，保持工具、schema、检索器、预算、temperature、历史裁剪不变；不要求额外 gap 工具调用。模型在首次候选形成、证据改变候选判断、提交之前执行短检查。核心是未找到不等于支持、局部事实不等于完整身份关系、题干条件不能为了候选被静默改写。机械上无额外请求，但可增加输出 token 或占用后续搜索预算，须实测。

独立消融：基线 vs 仅提示；若有效，再去掉“原文支持检查”或“矛盾后换候选”部分区分收益来源，避免首轮多个实现一起改。预测失败：模型忽略提示；逐项凭记忆捏造支持；过度保守弃答；短题耗时增加。判定不能只看检查表是否出现，要看后续动作是否获取缺失原文或放弃有冲突候选。

### 2. 候选提交前一次独立证据核查

在第一次非弃答 finish 请求尚未提交时触发一次。新上下文只给原问题、候选、已交付原文（原 ref、窗口），不给策略长解释或私有答案；同模型输出逐条件 supported/unknown/contradicted 与逐字引文。代码可验证引文确在该窗口，但语义蕴含仍由模型判断。反馈交还策略完成一次修订；严格只一次，不能因拒绝不断重新核查。

这个已有证据版最小实现增加 1 次验证请求，加上至多 1 次策略修订请求（若总预算固定，从原策略预算预留）。它不是真正复现 FineVerify/DeepVerifier 的主动检索验证，可能只能拦错不能找对。后续若开放验证器检索，必须另设至多 2 次模型动作请求加 1 次最终核查，且计入同一总账。独立消融为基线 vs 仅核查；另用同一证据输入比整体判断和逐条件判断。预测失败：同模型错误相关、证据缺失引发误拒、正确答案被改错。单独统计错→对、对→错、错→弃答和核查费用。

### 3. 停滞时保留证据并重建一次工作区

候选持续不变且连续三轮没有新的候选条件获得原文支持时触发；若暂时不能可靠提取条件状态，只可称“连续三轮没有新原文”触发，不能称语义停滞检测。一次模型决策同时输出简短保存对象及下一动作：题目条件、每个已知候选、支持与反驳原文 ref/原句、未解决条件、未试过的检索入口。重建输入后优先从未满足条件或另一个候选出发，原证据档案不删。每题至多一次，保留现有总请求上限。

可同决策生成而增加 0 次专门摘要请求；另设摘要器则 +1。消融要比较“同样提示但保留全历史”与“相同信息但重建历史”，才能归因重建；另比较无分支指令。预测失败：排除理由被压掉，导致候选重入；压缩内容将猜测升级为事实；短预算下生成报告代替搜索。优先级低于机制 1/2。

## 第一轮唯一变量：完整提示草案

将以下块追加到策略系统提示，不改任何工具合同，也不增加模型调用。触发均由文本说明，首轮不引入新状态字段或硬拦截；因此它是行为提示试验，不能称执行器保证。

```text
Check candidates against the question's requirements before committing to them.

When you first identify a plausible candidate, briefly list the requirements that distinguish a correct candidate. Preserve the question's dates, entity roles, and relations. For each requirement, track whether delivered source text supports it, contradicts it, or leaves it unresolved. A search snippet is a lead for reading; it is not a substitute for source text. A true fact about a candidate supports only that fact.

After reading evidence that changes a candidate's status, update only the affected requirements. For a supported or contradicted requirement, identify the delivered evidence reference and the exact source phrase. If that phrase is absent from the referenced text, leave the requirement unresolved. Keep source statements separate from your inferences.

Use the most discriminating unresolved requirement to choose the next search or read action. When source evidence contradicts a required condition, set that candidate aside and investigate a different candidate or a different entry point into the question. A missing fact alone does not reject a candidate. Do not silently relax a condition to preserve a favored candidate. If two consecutive attempts about the same candidate provide no evidence for an unresolved requirement, choose a different locating clue or inspect a relevant unread source instead of paraphrasing the same query.

Before finish, check the candidate against all identifying requirements and check that each cited passage supports the claim attributed to it. Resolve known contradictions while research budget remains. If the available evidence is insufficient at the final boundary, use the existing abstention option. Keep these checks brief and perform them within the current decision; continue issuing useful tool actions under the existing tool and answer contracts.
```

上面“两个尝试”是待验证的通用启发式，不来自某一论文最佳参数。若要求更纯的第一轮归因，可以删除第四段前的循环脱困句，把首次唯一变量缩到条件核对；推荐如此冻结，之后单独测试停滞切换。

## 验证协议建议

开发题只用于筛选机制，不可用两题成功宣称泛化。第一轮以最小纯核对提示为唯一变量；短控制必须保留。候选配置须独立重跑，并在固定 12 题同配置对照验证。所有辅助核查、策略修订和后处理 judge 均占 1000 新请求预算，失败发送同样计数。每题除了最终正确与否，保存是否真实读到新条件证据、何时排除冲突候选、原文引句匹配、重复/近似重复检索、读取旧窗口次数、输入/输出/cache token、总请求与时延。post-hoc judge 不进入策略上下文；任何线上机制不能使用 gold。

检索局限：搜索结果不是穷尽目录，不能宣称找齐截至日期所有论文；本轮 2026 年最近直接相关且已核对的主实验证据为 FineVerify，8 月压缩论文作为负面成本证据。没有用二手论文笔记支撑结论。
