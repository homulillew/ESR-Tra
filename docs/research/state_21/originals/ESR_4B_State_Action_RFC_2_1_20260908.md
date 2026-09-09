# ESR 4B State & Action Contract 2.1-RFC

**主题：从 bad case 出发，降低非必要决策负担，形成 finding—gap—action 的可恢复闭环**  
**日期：2026-09-08**  
**状态：正式化设计草案；未实现、未推送、未进行真实模型或 BC+ 实验。**  
**审查基线：`homulillew/ESR-Tra@6ee9c4a264cd80a50d8a15511c8ed80b39c763b6`。**

本 RFC 是本轮唯一建议的 state/action 规范。此前讨论过的独立 Task/Notes/Hypothesis 大对象、额外 planner、复杂图结构和过程奖励，不并入这次接口。伴随 JSON Schema 只验证语法，不验证证据蕴含、引用可见性、作用域或状态转移。

---

## 1. 总结：核心是降低非必要负担，而不是省掉任务本身的推理

State 的目标不是让提示最短，也不是让字段最少。目标是在保留决策必要事实、关系、反证和不确定性的前提下，减少模型反复恢复历史、复制未变字段、猜引用编号、从泛化反馈重建下一步任务的工作。

可将工作负担作概念性分解：

\[
W = W_{task}+W_{reconstruct}+W_{synchronize}+W_{choose}+W_{protocol}.
\]

这不是对模型内部“认知”的实测公式。它是接口设计的分析框架：任务所需的实体消歧和多跳判断依然存在；其余四类工作应尽量由显式工作记忆和确定性 harness 减轻。不能将更复杂的 schema、更多状态一致性约束和更频繁的审核误称为“降低负担”。

**三项共同目标：**

- 决策负担低：读当前工作卡，做局部修改，不重写全部状态。
- 认识边界清楚：原文、模型 finding、候选、审核结果互不冒充。
- 过程可恢复：能够还原每次决策实际接收了什么信息。

本设计不声称产生完整的 Markov 充分统计量、不声称保证 4B 解题成功、不声称 provenance 是因果贡献，也不引入新的 RL reward。

## 2. 证据基线：先分清历史现象和当前实现

### 2.1 4B 旧运行中能够直接定位的现象

[4B 历史 bad-case 分析](https://github.com/homulillew/ESR-Tra/blob/6ee9c4a264cd80a50d8a15511c8ed80b39c763b6/analysis-L/BADCASE_ESR_100.md)记录：

- q23：审核后围绕电影、年份、警察腐败等近似词继续检索，剩余关系没有明确推进。
- q170：旧协议下反复尝试不合法的 read。
- q311：找到相近对象，却未完成目标实体的正确绑定。
- q776：返回相关人物，而非题目所要的目标对象。
- q581/q607：单位和书写形式影响旧判分；不是 state 本身的语义缺陷。

旧统计中“78 条审核后卡住”是一组现象，不是“78 条都仅由 state 导致”的因果结论。更不能以新 schema 修订推断已缓解了多少真实 4B case。

### 2.2 32B 旧运行提供的补充机制

[32B 检索不收敛分析](https://github.com/homulillew/ESR-Tra/blob/6ee9c4a264cd80a50d8a15511c8ed80b39c763b6/results/local32b100_retrieval_nonconvergence.md)记录 q161/q1201/q199 的错误候选锁定与重复查法。它们用于检验设计能否表达“路线无进展、候选仍待检验”，不混称为 4B 新证据。历史分析本身有 100/101 等会计口径不一致，不据此重新报告精确总体比例。

### 2.3 v2 已修复与仍未补齐的部分

[当前 engine](https://github.com/homulillew/ESR-Tra/blob/6ee9c4a264cd80a50d8a15511c8ed80b39c763b6/src/esr_harness/engine.py)已经实现不可变视图重读、no-op 保版本、审核缓存、稳定 claim ID 和模式门禁。

[当前 schema](https://github.com/homulillew/ESR-Tra/blob/6ee9c4a264cd80a50d8a15511c8ed80b39c763b6/src/esr_harness/protocol.py)的 claim 仍只有 requirement 和 observation IDs；update 是全量小状态替换；search 没有研究 focus 关联；正式审核需要非空答案。

[当前 runner](https://github.com/homulillew/ESR-Tra/blob/6ee9c4a264cd80a50d8a15511c8ed80b39c763b6/src/esr_harness/runner.py)通过降低 recent 数量适配上下文，尚未建立独立的最新结果交付契约。

## 3. 从错误到设计约束

| 错误机制 | state 缺少的区别 | 本 RFC 的处理 |
|---|---|---|
| 同候选反复搜 | 候选假设与已知事实；失败路线与失败候选 | answer 可撤回；来源化 finding；按 focus 组织尝试摘要 |
| 换近义词却没推进 | 题目总要求与当前未知关系 | focus.need 只写当前一个证据问题 |
| 找到链上错误人物 | 条件成立与对象绑定一致 | target 明确输出位置；finding 显式命名人物/赛事/年份关系 |
| 单项各自匹配 | 各自存在满足对象与同一对象联合满足 | 全量审核检查共享对象和目标绑定 |
| 遗忘已有进展 | requirement 与 finding | 保留短 finding，不每轮从原文重建 |
| 反证被归档后遗忘 | dismiss 与证据失效 | 已识别冲突由后台保留证据证书 |
| 协议循环 | 知识缺口与工具/引用故障 | 错误分类；精确引用；可恢复阅读；不制造假 gap |
| 搜不到就答不存在 | 局部搜索无结果、候选错误、决定不答 | attempt_note、audit verdict、submit decision 三处分开 |
| 单位/标签问题 | 事实推理与最终判分 | 不用 state 规则迎合错误标签；独立判分治理 |

`Finding` 不能保证正确；`focus` 不能保证选对；它们让错误局部化、可读、可修正。任何“已缓解”的说法都需要后续真实运行证据。

## 4. 系统分层与形式化

整体运行状态表示为：

\[
X_t=(Q,D_t,O_t,S_t,R_t,B_t).
\]

- `Q`：不可修改的原始问题。
- `D`：文档快照；储存不等于展示。
- `O`：按实际原文片段定义的不可变观察。
- `S`：模型可编辑的紧凑研究工作区。
- `R`：动作、检索请求、曝光、尝试、审核、作用域及终止日志。
- `B`：动作和生成预算。

模型输入由确定性编译器产生：

\[
C_t=K(X_t),\quad y_t\sim\pi_\theta(\cdot\mid C_t),\quad
 a_t=Parse(y_t).
\]

语义修改由模型提出，但执行规则、引用校验、预算、缓存、版本、持久化和回放由 harness 负责。`K` 不调用更强模型生成隐藏答案或语义裁决。

持久存储、活动上下文、训练采样快照是不同层：

\[
\text{stored}\ne\text{returned}\ne\text{exposed to model}\ne\text{interpreted correctly}.
\]

最终一项不能由日志证明；前三项应该由事件关联区分。

## 5. 唯一模型可编辑状态

```json
{
  "target": "最终返回的对象、值或关系位置",
  "answer": null,
  "claims": [
    {
      "claim_id": "c0",
      "requirement": "原题中的一个必要条件或关系",
      "finding": "",
      "observation_ids": []
    }
  ],
  "focus": {
    "claim_id": "c0",
    "need": "现在还需要回答的一个具体证据问题"
  }
}
```

### 5.1 target

表达原题最终输出对象与关系位置，不保存置信度和暂时计划。默认直接使用原问题，不强制第一次搜索前做完多跳分解。后续修订须有理由，原问题始终保留。

例如“返回赛事两年前的冠军，不是用于定位赛事的起点人物”。这些角色可以用短自然语言明确，不要求维护符号执行器或知识图谱。

### 5.2 answer

`string | null`。字符串是当前候选，不是事实认证；`null` 表示尚未提出或已暂挂候选。字段缺席于 delta 表示不修改，显式 null 表示撤回。为避免两份同义数据，不另设 candidate.value。

只因两次检索未找到关系，不得由 harness 自动判候选错误。候选变化保留原文、finding 历史、搜索缓存和查法历史，失效的是适用性不再相同的审核。

本 RFC 将 `answer_kind` 从语义工作状态移到最终 `submit_answer(decision=...)`：不答是动作，不是世界知识。属于明确的接口迁移，不能让旧客户端静默混用。

### 5.3 claims

一个 claim 项包含两个不同内容：

- `requirement`：必须建立的条件。
- `finding`：对已观察材料的当前、可修订解释。

`observation_ids` 是 finding 的原文来源，不是“我认为支持”的自评分。

规范要求：

1. 非空 finding 必须带至少一个本 episode 中已实际暴露的视图引用。
2. finding 尽量显式写实体与时间，不写无作用域的“他”“上一个答案”。
3. finding 可以记录组合推导，必须能够恢复其原始输入；引用存在不证明推导正确。
4. 原题要求写在 requirement 或 need，不凭空伪装成文档事实。
5. 数字笔记保留数量、单位、日期口径；不能仅保存失去输入的计算结果。
6. 引用可以包含支持、削弱或冲突材料；最终语义标签由审核给出。
7. 新候选不会删除旧 finding；旧 finding 默认不是新候选的证据结论，渲染应保留实体名与写入作用域。

同一文档可以支持多项 finding；本 RFC 不另加庞大 Note ID 图，也不强制每篇文档写笔记。找到了桥接关系即可记录，不必等到最终答案已知。

### 5.4 focus

只保留 `claim_id + need`。一次展开一个主要研究问题；其他条件仍有完整短总览。获取的材料允许推进多项条件，不因 focus 而禁止偶然发现。

`need` 是“当前缺少的关系或变量”，不是 search query、长计划或审核拒绝理由的复制。它也不一定需要 search：已有材料不足显示时应 open；已展示但未理解时应 read；已有事实只差组合时应 update。

焦点变化不代表 gap 已解决，不改变审核真值，不应该使答案审核无谓重跑。

### 5.5 渐进初始化

harness 创建一个 bootstrap claim `c0`，requirement 和初始 need 为原问题；answer 为 null。模型可先围绕原题一条显式线索检索，再将 c0 细化、补充 c1 等条件。

不要求强模型或一次完整规划先把问题拆“正确”。完整条件覆盖在最终审核时回看原题；题目分解错误必须可修订。

## 6. 后台派生状态与唯一写入者

| 数据 | 唯一管理者 | 模型看到什么 |
|---|---|---|
| claim ID、版本、候选作用域、内容 hash | harness | 短 ID 与必要 stale 提示 |
| 文档、观察与原文区间 | retrieval/view 层 | 单份可引用正文与来源 |
| pending、latest_result、exposure receipts | runner/harness | 待处理列表、最新结果 |
| 检索缓存、返回/已读集合、查询参数 | harness | 当前路线的摘要与未读候选 |
| 尝试报告 | 动作事实由 harness；简短解释由 actor 声明 | 当前焦点最近的少量尝试 |
| audit verdict | auditor 生成，harness 校验/聚合 | 当前有效 verdict 与具体 need |
| 已识别冲突证书 | harness 从有效审核存取 | 候选与条件相关的反证提示 |
| final judge/reward | 离线独立评测 | 不注入在线模型上下文 |

没有 actor 可写的 `supported`、`gap_resolved`、`credit`、`confidence` 或全量候选黑名单。

## 7. Gap 的定义、身份与寿命

### 7.1 工作缺口与审核缺口分开

工作缺口在没有候选、没有审核时就能存在：由 requirement、finding 和当前 need 表达。

审核缺口来自一个确定输入包的 verdict。`supported/unknown/contradicted` 适用于该输入版本，不是永久真理。

`focus` 指向当前工作缺口；不维护另一份平行 GapList。模型可以切换 focus，但不能由此清空审核未解决项。

### 7.2 身份

后台 gap key 可保守定义为：

\[
G=H(\text{claim lineage},\text{requirement content revision},
\text{target/answer scope}).
\]

`need` 的改写不新建一个“未尝试过”的 gap；focus 文案不是重置计数的通道。候选改变产生不同审核作用域，但全局检索缓存与条件线索的尝试索引仍保留。精确相同的审核内容可复用旧缓存，操作版本变化不强制重审。

### 7.3 什么才算修复

- `working_update`：actor 修改 finding，尚未审核。
- `evidence_repair`：同一候选/条件作用域下，旧有效 unknown/contradicted 在新有效审核中变为 supported。
- `candidate_revision`：候选被替换或暂挂；不能记成原候选被证实。
- `requirement_revision`：题目分解修改、增补或退役；不能记成旧缺口解决。
- `cached_audit`：读取相同结果，不生成新修复事件。

以上是事件含义，不是奖励定义。完整因果贡献仍未被证明。

## 8. 模型动作契约：仍然只有六个工具

### 8.1 `search(query, focus?, anchor_refs?, top_k?)`

**目的：**为当前未知关系取得导航候选。

- 默认继承当前 focus；允许在这次 search 中同时更新 focus，避免仅为换焦点增加一轮 state 写入。
- `anchor_refs` 为可选来源声明：`question`、`candidate`、已暴露 observation ID。未填写记为 unspecified，不自动假定来自原题；填写也不证明 query 语义正确。
- 不要求模型复制 gap hash、候选版本或完整检索历史。后台冻结本动作的 purpose scope。
- 若 focus 更新合法但检索失败，focus 仍可作为独立已记录的合法元数据编辑保留；没有新事实、没有新证据、没有新语义 gap。该组合动作的两个阶段必须分别记账。
- 返回 search action ID、hits、缓存来源、尚未打开候选和结果新颖性。search snippet 只用于导航。

`focus` 更新与检索分阶段记录是本工具的明确例外；`update_state` 仍全量事务性。工具错误不得隐式改变 finding、answer 或审核。

### 8.2 `open_page(docid, search_action_id?, query? | offset?)`

**目的：**获得某篇已检索文档的新的、实际可见片段。

- docid 必须在本 episode 的真实成功 search hits 中出现。
- `search_action_id` 可省略，由 harness 解析为最近一次实际返回该 docid 的 search；显式提供时必须校验。不省略 provenance，只省模型复制字段。
- `query` 与 `offset` 互斥，避免排序窗口和原文窗口语义冲突。
- 在持久化 view 前做容量准入；依据本轮剩余观察空间确定窗口，返回后不再偷偷裁短。
- 记录两个关系：`retrieval_parent`（文档从哪里来）与 `purpose_gap`（这次阅读为了解什么）。读旧搜索结果服务新 gap 时，两者不能混用。
- 相同片段可以复用 immutable view；本次曝光/阅读动作仍独立记录。

### 8.3 `read_evidence(observation_id)`

原样恢复曾展示的视图；不要求在 claim 登记，不重新检索。仅因没有新增原文字节，不能判本次重读毫无价值。

为使有界目录中的旧材料仍可到达，同一工具提供一个低频目录模式：`read_evidence(directory_cursor="start" | issued_cursor)`；它只返回已知视图的索引页，不把未展示文档全文变成已知证据。两个模式互斥。

### 8.4 `update_state(...)`

只写 delta，缺席字段保持不变，answer 显式 null 表示撤回候选。

```text
update_state(
    target?,
    answer?,
    claim_updates?,
    retire_claim_ids?,
    focus?,
    dismiss_observation_ids?,
    attempt_note?,
    revision_reason?
)
```

规范：

- 已有 claim 用 claim_id 定位；新项省略 claim_id，必须给 requirement，由系统分配 ID 并在响应中返回。
- 新 ID 只能在收到响应后的动作使用；同一事务不发明临时引用语法。
- 修改 finding 与其 observation_ids 成对提交，防止新解释悄悄沿用错误来源。
- 未改变字段由系统保持，不重新生成。
- 对任务含义、既有 requirement 的修改和 claim 退役要求 revision_reason；新增条件本身不需要重复已有全部项。
- 被退役的条件及其旧冲突保留在历史中；退役不等于解决，最终 coverage 仍检查原题。
- 不能退役最后一个条件；退役当前 focus 的条件时，应选择另一个已存在条件作为 focus，或显式将 focus 置空。后一种情况下，下次研究动作需先声明新 focus。
- 有用观察被写入带来源 finding 即可处理 pending；无关观察显式 dismiss。不能同时引用并 dismiss 同一个视图。
- attempt_note 是本次查法的简短自报告，由 harness 关联当前活动尝试；不是 verified fact，不进入证据证明链。若没有活动尝试，则要求明确关联已有尝试，而不随意挂到其他 gap。
- 全部校验、容量预检和持久化成功后才应用 delta；失败不半写状态。

### 8.5 `verify_answer()`

允许部分研究状态：answer 为 null 时仍可审核已有关系，但目标不完整、不能最终通过。无需每次读取后调用；局部研究默认靠 actor 的 update，审核用于重大争议、候选基本形成或准备结束时。

输入为一个冻结包：原题、target、候选、全部必要条件、待检查 finding、其引用的实际视图，以及适用的既有冲突证书。finding 被标记为待核解释，不当外部证据。

输出保持 target、coverage、每个 claim 的 status/reason/quotes，并对 unknown/contradicted 提供简短 missing relation。完整性、绑定一致性和实体消歧仍是模型语义任务。

- supported：在本审核作用域内被证据支持。
- unknown：缺证、目标尚未绑定，或相互冲突来源尚无法裁定；不是 false。
- contradicted：有适用于当前假设的明确冲突证据。
- quote 必须逐字定位到允许的已观察原文；quote 合法不证明自然语言蕴含。
- 已知冲突来源允许被审阅，即使 actor 后来移除了普通引用；系统不能宣称检查了所有未被引用的历史材料。
- 输出协议错误、超时和超窗都不创建语义 gap。

审核 fingerprint 只绑定实际输入和审核器语义配置，不包括 focus.need、attempt_note、display order、remaining budget 等研究控制元数据。finding 若作为待检解释进入审核包，它的修改应失效对应缓存。

### 8.6 `submit_answer(decision="answer" | "abstain", reason?)`

不接受额外 answer 参数，避免“审核 B，最后提交 A”。

- `answer`：使用当前工作区答案。
- `abstain`：显式选择不提交答案，不修改 finding 或候选历史；保存 final_draft 用于诊断，但不算作答。

模式保留：

| 模式 | 正常提交前提 | evidence_status |
|---|---|---|
| hard | 当前完整审核 supported，目标有值，相关观察已处理 | supported |
| soft | 当前有效完整审核已完成，目标有值，相关观察已处理 | 保留实际 verdict |
| off | 当前有候选与任务条件，相关观察已处理 | unverified |

hard 不是“绝对正确”，soft 不是“强制放行”。本 RFC 不偷偷改变既有默认实验模式。基础设施失败也不能自动改判 supported。abstain 不要求先通过语义审核。

## 9. Gap 驱动搜索的尝试闭环

### 9.1 SearchAttempt

后台从实际事件构造：

```text
attempt_id
purpose_gap / target-answer scope / focus.need snapshot
query + retrieval parameters + optional anchor_refs declaration
returned_docids / cache_source
opened_views / actual_exposure
actor_attempt_note
unconsumed_candidates / new_raw_spans
```

当前活动工作卡只显示一两条相关尝试摘要。完整历史保留于账本。单条路线可读多份材料，不要求 search→open→update 的死板三拍节奏；搜索发现新桥接点后可立即继续搜索，只要未处理观察仍保留、容量允许。

### 9.2 结果必须分层

机械事实：完全相同请求、命中集重叠、还有未读候选、实际新增原文区间、服务错误。

模型解释：补上了哪条关系、在已读材料中仍缺什么、是否存在冲突。

模型解释是有边界的自报告。`no evidence in these viewed passages` 不能升级为 `no such fact exists`。

### 9.3 三类不同的下一步

1. **事实有进展：**更新 finding，再转向由新事实确定的下一条 need。
2. **查法没补上关系：**利用缓存未读候选，改用原题另一线索、新的已证实桥接点，或暂挂候选。
3. **已有真实冲突：**核对语境/同名实体/来源，必要时换候选，并保留反证。

第四类是基础设施失败，仅重试或结束，不进入语义失败计数。

### 9.4 完全重复请求

缓存键覆盖实际 query 字节（只使用检索端确实同样采用的规范化）、index/corpus revision、retriever/config、top-k、filters 及必要 seed。固定确定性检索下复用成功结果；未知索引变化和随机服务不得当成完全相同。

缓存结果必须可操作：显示尚未读的 hits 和旧视图，而不只是返回 `duplicate=true`。缓存命中仍消耗实际生成和 action 预算，不作为新证据或正信用。

### 9.5 近似关键词

不使用 query embedding 相似度作硬禁止。年份、否定、before/after、别名、top-k、offset 的细小变化可能至关重要。

命中池相同也不等于无价值：未读文档、未读片段、不同关系抽取仍可能推进。停滞提示须描述可观察事实，而非宣称语义信息增益为零。

不设置“失败 N 次自动通过”或“失败 N 次候选为假”。可配置少量完整尝试之后呈现更强的改向提示，但阈值是工程假设。模型仍可能不听提示；硬保证只是预算有限、相同成功请求不重复消耗外部服务、每次动作有记录，并不保证选出正确下一动作。

### 9.6 防止状态改写洗掉历史

focus.need 改写、候选来回切换、claim 重新命名，都不删除检索缓存和原题线索的已尝试索引。仅改措辞不计为修复或新知识。必要条件修订有独立事件；条件确实改错时仍允许改回，不能因 anti-loop 规则永久锁死。

## 10. 上下文编译与交付

```text
原题与工具规则
目标与完整的必要条件短总览
当前候选及必要 stale 提示
当前 focus.need
相关 findings 与关键反证
当前路线的一两条尝试摘要
最新工具结果（受保护）
少量近期动作、未读候选入口、剩余预算
```

### 10.1 工作卡不是存储对象直接序列化

模型只看一份正文；raw_parts、hash、全量 action delta、重复结果从活动 prompt 中移除，仍保留在账本。已显示 observation 在近期动作里只用 ID 引用。

### 10.2 latest result 与 pending 是两个契约

- latest：必须进入下一次实际策略请求。
- pending：尚未被 finding 吸收或明确 dismiss。

已引用视图的重读仍要受到 latest 保护，但不必强制再生成一次 no-op update。最新 search hits 和错误反馈也受保护。

请求和响应记录 exposure receipt。返回了无效 JSON 也不等于模型没接收上下文；网络失败则不能假定接收成功。记录已知和未知阶段，不把“接收”解释成“理解”。

### 10.3 容量准入

\[
B_{fixed}+B_{state}+B_{working\ evidence}+B_{latest}+B_{history}+B_{output}\le B_{context}.
\]

先用实际 tokenizer 检查，再定义本次将要展示的窗口，随后冻结 observation。不能先声称完整展示，再截去关键尾部。

pending 已满时返回可处理的容量反馈，允许 update/dismiss/read，而不是继续塞入大视图。连最小必要状态都无法容纳时，明确终止或报告容量限制，不删除题目条件冒充可容纳。

### 10.4 信任边界

原题、harness 指令、检索文本、finding 与审核理由保持来源标记。工具内容不升级成系统指令；finding 与旧审核也不变成新外部证据。摘要丢失否定或作用域时可以通过原文恢复，不能假定结构化文本天然正确。

## 11. 候选与审核作用域

后台记录 candidate scope，保守由 target/answer 内容标识；操作 epoch 单独用于追踪变化，不参与所有缓存失效。

候选变化：

- 保留来源化 finding 与实际证据；不把它们自动认证为新候选的支持。
- 当前审核失效，除非完整审核包内容完全相同且已有有效缓存。
- 已知冲突证书保留旧候选/条件/原文的精确作用域。
- 回到旧候选时恢复旧反证提示，但允许用新材料反驳旧判断。
- focus 可以切换到原题线索发现阶段，answer 置 null；并非必须立即想出另一个答案。

全量任务审计必须检查联合绑定。局部条件各自存在满足对象不推出同一个对象满足全部条件：

\[
\bigwedge_j\exists x_j\,\phi_j(x_j)\not\Rightarrow
\exists x\,\bigwedge_j\phi_j(x).
\]

本系统不实现完整符号证明器；以上是状态表达与审核要求，不是确定性蕴含保证。

## 12. 完整示例（虚构，不是 BC+ 新轨迹）

问题：**Mira 夺冠的赛事在其夺冠前两年的冠军是谁？**

1. `search("Mira championship winner year")`。初始 need 是找到赛事和年份，answer=null。
2. `open_page(d1)` 返回 o1：`Mira won the Lake Cup in 2010.`
3. `update_state` 将 c0 细化为赛事年份定位，写入 finding/o1，新增 c1：确定同一赛事 Y-2 年的冠军。新 ID 在响应中可见。
4. `search("Lake Cup 2008 champion", focus={c1, ...})`。赛事和年份来自已获得的材料与原题关系，不是 gold 注入。
5. `open_page(d2)` 返回 o2：`The Lake Cup 2008 champion was Taylor.`
6. `update_state` 写入 c1 finding，引用 o1/o2，answer=Taylor，focus=null。
7. `verify_answer()` 审核 c0/c1 的联合绑定、coverage、target。
8. `submit_answer()` 提交当前候选，不再接受另一个 answer 参数。

若第4步只反复命中旧网页，返回缓存与未读候选；不会因重复命中将 c1 标为解决。若已读到 Taylor 但没提取正确，优先 read/update；不要求为了显示进展继续找新网页。

## 13. 对 4B 旧 case 的预期作用与边界

| case/类别 | 设计预期 | 仍然需要模型能力的部分 |
|---|---|---|
| q23 类近义词重搜 | 明确当前一条 missing relation；保存已试路线及其有限结果 | 选对关系、产生合适查询 |
| q170 类协议循环 | 已知 observation 任意重读、latest 保护、局部 update | 读懂证据并正确抽取 |
| q311/q776 类目标错位 | target 与 finding 写明对象关系；最终联合审核 | 实体消歧与语义判断 |
| 32B q161/q1201 类固定候选 | 假设不默认进入每个 query；可撤回候选、改从原题线索发现 | 发现正确新方向 |
| 支持材料和反证混杂 | 冲突证书不因 dismiss/删除链接消失 | 判断来源与语境、避免误拒 |
| 单位/舍入/标签争议 | 保留输入数值、口径、明确争议 | 正确解释题目；独立判分复核 |

不能把表格中的“预期作用”描述为已获得的真实 4B 缓解率。

## 14. 可检查的不变量

1. `Q` 不可修改；修改 target 不能删掉原问题。
2. 未知或跨 episode 的 observation ID 不可进入 finding。
3. 原文快照与已定义视图不可更改。
4. 工具返回和模型曝光有独立关联，不把前者当后者。
5. finding 是可修订解释，不是 actor 可写的认证事实。
6. 同一状态 no-op 不产生新的审核语义输入。
7. focus、attempt_note 的变化不单独使答案审核重跑。
8. 删除/改写条件不记录为 gap resolved。
9. 候选转换不记录为原候选补证成功。
10. 相同输入缓存命中不产生新证据或新修复。
11. 服务/JSON/上下文故障不创建 semantic gap。
12. 关键反证不因普通 dismiss 或删除引用变成不存在。
13. submit 的答案只能来自当前 state；abstain 不伪装成 supported。
14. 正常动作与错误/缓存尝试都受有限预算；未知 usage 不记作零成本。
15. 无论终态如何，保留 final_draft 和真实 terminal reason；草稿不计作提交。
16. Schema 能检查格式；原文引用一致性要运行时检查；蕴含仍需语义审核。三个层级不能混报。

## 15. 验收规范（定义，不是已经执行的 harness 测试）

| 测试 | 预期 |
|---|---|
| 仅更新 c2 finding | c1/c3/target 不变；不要求重新复制 |
| finding 改写但没有成对来源字段 | 协议拒绝；无半写状态 |
| 新 claim 省略 ID | 系统分配 ID；禁止同事务引用未返回的新 ID |
| answer=null 的部分审核 | 可得到局部支持；整体不可 hard submit |
| 重读已引用视图＋历史窗口为0 | 本次原文仍进入下一次策略请求 |
| 同请求跨 focus 重复 | 复用检索结果，保留两次意图记录和同一来源 |
| 同 query 不同 top-k/index/filter | 不误认为相同请求 |
| 2008→2010 或 before→after | 不被近义词封禁 |
| 同文档新 offset | 可产生新 view，不混成 duplicate |
| 未读候选仍存在 | 显示入口，不强制必须读每个低相关 hit |
| 两次未找到关系 | route 无进展，不自动 contradicted |
| 候选A换成B后通过条件 | candidate_revision，不是A的 evidence_repair |
| gap reason 改写 | 稳定身份不变，不伪造解决 |
| 旧审核误判＋新证据 | 新输入允许重新审核，不永久冻结错误 |
| 文档里出现恶意指令 | 不升级信任身份；不当 harness 命令 |
| 语法合法但错误 quotation | 运行时审核协议拒绝 |
| 最后预算动作合法提交 | 能提交；不差一截断 |
| 生成预算不足或未知服务成本 | 明确预算/infra 状态，不默认免费继续 |

## 16. 对训练的接口承诺，暂不改训练算法

工作 state 的 update、focus 选择、查询、阅读选择都是 policy 行为。若它们由模型生成，不能在未来 RL 中全当成免费环境文本。

后续 sampler 需要：原始 prompt tokens、自产 response tokens、behavior revision/logprobs、reasoning/tool-call 边界、role、decision_id、exposure IDs、执行结果。不能用最终 finding/证据重建早期 prompt。

同一自产 token 只在其原生成位置计算一次损失；后续作为 prompt 的重放不再计作新生成。检索正文、确定性摘要元数据与缓存记录不是 policy 输出。

provenance 可以记录：`purpose gap → search/open/read → exposed view → finding update → candidate revision / scoped audit`。这仍是依赖代理，不是因果奖励。此阶段不奖励“新文档数”“gap 变少”或“创建/消除 gap”。

## 17. 迁移范围

| 现有模块 | 变更 |
|---|---|
| protocol.py | finding/focus、局部 delta、submit decision、可省的机械父ID、read目录模式 |
| engine.py | update事务、动态初始化、scope、尝试关联、partial audit前置条件 |
| runner/context | 工作卡渲染、latest-result保护、曝光记录、容量准入 |
| retrieval/views | 完全请求缓存；先按相关性选片段再按原文顺序展示 |
| audit.py | finding为待核解释、联合绑定、具体need、已知冲突包 |
| ledger | decision/exposure/attempt关联与版本说明 |
| legacy训练 | 不直接接入；保留，等待单独迁移 |

不覆盖历史 SQLite，不把既有来源和历史运行改成新协议，不在本轮推送代码。接口破坏性变化必须明确版本化，而不是在旧 schema 内偷偷改变空值、abstain 或引用语义。

## 18. 本轮实际完成与证据限制

- 读取并固定当前仓库 revision，核对 4B 旧 bad case、32B 旧重复路线、v2 schema、engine 和 runner。
- 生成本 RFC、用户状态/动作 JSON Schema、虚构示例。
- 对伴随 Schema 执行了 13 个正动作示例、2 个正状态示例、8 个反动作示例的语法验证。
- 没有执行新 harness 状态转移测试，没有连接 4B/检索服务，没有运行 BC+ 或训练。
- 本轮一般网页检索接口两次失败，不据此补写“最新论文已验证”的结论。另通过原作者公开仓库核对 [IRCoT](https://github.com/StonyBrookNLP/ircot)，只使用其“检索与中间推理交替”的方法线索，不搬用跨模型 benchmark 数字。

## 19. 设计结论

**State 的核心不是让 4B 维护一个更复杂的世界模型，而是把它反复需要的信息保存在正确的位置，把确定性维护任务移出模型。**

研究默认闭环：

\[
\boxed{Observe\rightarrow Local\ Finding\ Update\rightarrow Focus\rightarrow Next\ Action}
\]

结束前再运行认证闭环：

\[
\boxed{Current\ Candidate+Requirements+Raw\ Evidence\rightarrow Audit\rightarrow Submit/Repair}
\]

两条闭环共享证据和工作状态，但不把每次局部理解都变成一次全题审核。

**降低负担的判据是：未变字段无需重写，已知关系无需重建，机械 ID 无需反复复制，失败路线不会被遗忘；而不是字段总数更少、返回文字更短、审核通过率更高。**
