# ESR forward harness 2.1 — 收口的 State / Action 实现

**日期：2026-09-08。状态：前向协议实现；不等于通过真实 4B/BC+ 语义验收。**
本分支的规范以本文、可执行 `src/esr_harness/protocol.py` 与回归测试为准。此前 RFC 原文及 q324 推演见 [文档索引](../research/state_21/README.md)，它们保留历史的“未实现”等状态说明，不伪改成运行结果。

## 1. 核心闭环

研究：`Observation → local Finding delta → Focus.need → next action`。
认证：`current Answer + original Question + Requirements + raw Evidence → Audit → Submit / Repair`。

降低 4B 的非必要维护负担，不省略实体消歧、联合关系和证据理解本身。不增加 planner、知识图谱、独立控制模型、过程奖励或强模型在线依赖。训练算法与 `src/esr_grpo/` 不变。

## 2. 谁维护什么

Actor 只维护：

```json
{"target":"最终输出对象/关系位置","answer":null,
 "claims":[{"claim_id":"c0","requirement":"必要关系","finding":"","observation_ids":[]}],
 "focus":{"claim_id":"c0","need":"当前具体缺失关系"}}
```

Harness 管理 claim ID、研究版本、候选作用域、原文/视图、实际暴露、缓存、尝试记录、审核、冲突证据、预算与终态。没有 actor 可写的 supported、confidence、gap_resolved、reward。

原题不可修改。初始化用原题建立 c0/target/focus，不要求首次搜索前完整分解。answer=null 既允许尚未知答案，也允许暂挂候选。finding 是有来源的可修订解释，不是已认证事实。

每条 finding 保留对象、关系、时间、否定与单位。换候选不删除原文或 finding；工作卡将不同候选作用域写入的 finding 标为需要重新解释。相同条件分别找到不同满足对象，不等于同一个对象满足全题，最终审核仍检查联合绑定。

## 3. 六个动作的唯一契约

| 动作 | 2.1 规则 |
|---|---|
| search(query, focus?, anchor_refs?, top_k?) | 默认继承 focus，可同动作换焦点；锚点声明可为 question/candidate/已暴露 observation。查询仍是模型选择，不自动包含候选名。 |
| open_page(docid, search_action_id?, query? / offset?) | docid 必须属于成功 search hit；父ID省略时由系统解析。query/offset互斥。区分 retrieval_parent 与 purpose。 |
| read_evidence(observation_id / directory_cursor) | 精确恢复已知视图，或用 start/已发放游标读取有界档案目录；不重新检索。 |
| update_state(delta) | 只写变化。缺席字段保持不变，answer=null表示撤回。finding 与 observation_ids 必须成对。新claim省略ID，收到返回后才能使用。 |
| verify_answer() | 新上下文全题审核；允许 answer=null 的部分状态，但 target 必须 unknown。不是每读一页就强制审核。 |
| submit_answer(decision?, reason?) | 默认使用当前 answer，或显式 abstain；不接受第二份 answer 绕过。 |

Baseline 仍只有 search/open/read/finish；共享检索、视图与客户端，不获得 ESR 状态写入或审核功能。旧 answer_kind 已移为 submit decision，这是显式破坏性变更，不接收旧全量 claims 参数。

### Delta 与事务

update 的所有验证、引用/容量检查、写盘成功后才应用。未修改字段由系统保持。修改 target/既有 requirement、退役条件要求 revision_reason；不能退役最后一个条件。当前 focus 所指条件退役时，需改选已存在条件或显式置空。不能在同一请求中猜测新分配的claim ID。

search(focus=...) 有两阶段：合法且容量可用的焦点变更可以在外部检索失败时保留；非法参数、非法锚点不会半写状态。失败不得改 finding/answer 或创建 semantic gap。

## 4. 三个不同的“已读”

`stored != returned != delivered in a policy request != understood correctly`。

文档第一次打开即冻结。Observation 保存实际原文范围与内容hash。每次policy请求记录工作卡与可见ID；请求返回（包括无效JSON）后才授予已交付状态。网络失败记录unknown delivery。日志只能证明请求/响应关系，不证明理解。

非空 finding 只能引用本episode已交付的视图；无视图的新发现不能伪装成文档事实。程序直调execute的测试需显式记录 exposure；在线runner自动管理，不是新模型工具。

latest result 与 pending 分开：重读已引用视图仍受 latest 保护，但不强制再写一次 no-op update。有用观察进入 finding 即消费 pending；无关视图可 dismiss；不能同时引用和 dismiss 同一视图。dismiss 不删除原文或已记录反证。

## 5. Gap与尝试记忆

不增加一份可由actor清空的GapList。focus 是工作缺口；audit.unresolved_ids 是确定审核包下的缺口。切换/改写focus不代表解决。

search记录 purpose快照、query与参数、检索锚点声明、cache_source、新hit文档及未打开候选。阅读记录真实检索父关系和本次目的，exposure与action/decision关联。短attempt_note明确标为actor自报告，不作为外部事实。

attempt_note默认只关联当前条件且同候选作用域的最近一次尝试；歧义或旧作用域需显式attempt_id。这样“换候选后成功”不冒充“旧候选补证成功”。完整尝试在账本，工作卡只显示当前焦点最近两条。

重复控制不封禁语义相似query：年份、否定、别名、top-k/offset变化可能关键。固定确定性检索且index revision已声明时，完全相同query字节和参数命中缓存；不跨episode假设索引稳定。未声明revision或非确定性服务不启用缓存。缓存不算新证据，仍计实际生成/action成本。

“新hit文档为零”只是机械诊断，不是信息增益或候选为假。工作卡显示未读hit、已读视图和剩余关系，提示换原题线索或读不同区间，不强制top-1、不自动换答案、不按失败次数放行。

## 6. 审核与反证

审核只使用原题、target/answer、必要条件及待核finding、允许的已存原文视图。模型历史、focus、attempt_note、旧verdict理由不进入证据包。

每条输出 status/reason/need/quotes，target/coverage亦有status/reason/need。unknown/contradicted需具体need；supported不同时宣称缺口。引用逐字定位，只证明quote合法，不证明蕴含。空answer的target非unknown属于协议错误，不能静默改写通过。

后台保留有效审核中识别的冲突witness，按候选作用域和requirement关联。删除普通引用不能移除已知冲突原文；返回旧候选可恢复witness。审核包只加入来源，不把旧拒绝理由当新证据。系统不宣称发现了所有潜在反证，也不能阻止自然语言改写带来的所有语义规避。

fingerprint绑定实际审核包、视图hash与auditor配置，不绑定focus、attempt_note、操作版本和显示顺序。记录新冲突不得使产生它的当前审核立即失效。

修复事件只在同一候选/requirement作用域比较unknown/contradicted→supported。候选变化、条件修订、缓存重读分开记录，均不是自动RL信用。

hard：当前完整审核supported才可正常提交；soft：有效审核后可提交并保留真实unknown/contradicted；off：unverified。默认hard，CLI要求显式选择。abstain可结束并保存final_draft，但未提交草稿绝不计成绩。q324文档推演未证条件仍保留unknown。

## 7. 上下文与容量

workcard给出原题、全量条件短工作状态、当前focus、适用审核摘要、关键冲突指针、两条尝试、最新结果、pending正文、有限近期目录和预算。存储对象中的raw_parts/hash/delta不重复展开给policy。

最新结果与pending正文必须保留；recent history可减少到0。原文每份只显示一次；诊断reason/need可有标记地限长，完整审核留账本。search snippet是导航，可明确标记缩短，不作为证据引用。

open在冻结/返回视图前用真实客户端tokenizer的fits做容量准入；容量不足时在本次候选片段中减少窗口，不重新调用retriever；始终保留offset访问能力。选片段先按相关性使用预算，再按原文顺序展示。重复文本的远端chunk缺唯一offset时采用有标记回退。

update和read在提交前预检后继工作卡，失败不半写。pending数量有上限，满时返回可修复capacity错误。最小必要上下文仍放不下时明确context_overflow，不删除题目条件。此机制不是任意长任务的容量保证。

## 8. 预算、恢复和边界

policy与audit共用completion预算。每次请求先持久化最大用量预留；成功返回后结算实际usage；超时/崩溃/无usage按请求上限保守记账，不假装零成本。真实已测token和保守占用分别报告。audit保留128 token给后续policy结束决策；不是自动提交保证。

所有模型动作尝试含错误、缓存都计action。服务、协议、容量错误与语义gap分开。end保留final_draft、真实终因，不能打捞成绩。

新账本schema_version=3、implementation=2.1.0。v2代码冻结在esr_harness.v2；root replay按schema分发，只读、不迁移。2.1 live resume拒绝旧账本；旧实验驱动和esr_grpo训练代码保留原样。

精确prompt/response文本、purpose、decision/action/exposure已经记录；采样token、old logprob、真正RL segment mask尚未接入。provenance仍不是因果贡献，不能直接送入旧credit router。

## 9. 实现与验收

纯状态编辑在state.py；渲染在context.py；运行state machine在engine.py；模型I/O在client.py；审核在audit.py；原文/检索在views.py；单循环在runner.py。Schema可用`python -m esr_harness.schema docs/harness/schemas`导出。

见[VALIDATION.md](VALIDATION.md)和[RUNBOOK.md](RUNBOOK.md)。本分支收口的是可实现的协议、错误边界和复现方式，不是未经实验的4B正确率或完美verifier承诺。
