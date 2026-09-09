# ESR Forward Harness v2：协议先收敛，语义能力再验证

版本：2.0.0，2026-09-07。本文件取代旧文档作为当前前向推理规范；不定义新训练算法。

## 1. 设计目标与边界

保留 ESR 的核心：**外部证据与模型判断分离，研究状态可恢复，动作与证据可追溯**。
删除按单题症状不断增长的分支式 guidance，不引入新的 controller、复杂知识图谱、过程 reward 或强模型在线依赖。
所有题共享同一个协议；代码没有 gold 名称、特定 qid、重复 N 次自动放行或关键词兜底 supported。

v2 的保证是机械可检查的不变量，而不是“4B 永远理解正确”。语义蕴含、题目分解、实体绑定、
检索召回、数值口径仍需要模型及实测校准。字符位置／quotation 检查不能证明蕴含。

## 2. 数据模型

### DocumentSnapshot

每个 episode 第一次打开某 docid 时保存完整原文及 hash，后续冻结此快照。
同一 docid 的再次打开可以选择不同片段，但不悄悄覆盖原文。固定语料更新后开启新 episode。

### ObservationView

```text
observation_id, docid, document_hash
spans: [start, end) in raw document
raw_parts, text, view_hash
source, fallback, query
created_by_action_id, search_action_id
```

`text` 是原样交给调用者的渲染，包含偏移标识；`raw_parts` 是原文片段。
引用原文检查只接受 raw_parts 内的非空子串，不接受界面 header。

视图构造优先使用现有 `/get_doc_chunks`。片段必须能逐字映射回 DocumentSnapshot；
服务缺失、异常或无法映射时，使用**显式标记**的本地字符分块／词项排序回退。
`open_page(offset=...)` 提供可达的全文窗口，避免“全文存了但尾部永远看不到”。
`view_chars` 是观察定义的安全上限，不是之后给 policy/audit 偷偷再截一次的上限。
实际渲染 hash、偏移、回退原因全部记录。

相同文档快照的相同片段复用 observation_id；不同 query 得到不同片段则产生新视图。
`read_evidence` 不调用 retriever、不重新排序、不要求先写 finding。

### ResearchState

```text
research_version
answer, answer_kind: answer | abstain
target
claims: [{claim_id, requirement, observation_ids}]
```

Claim 是题目的必要条件／目标关系，不是为每句话建图。工具一次原子替换小型 state，模型不能写审核状态。
目标或 requirement 集合发生变化必须提供 revision_reason。普通补引用／换候选不需要重建 requirement ID。
语义 payload 未变化的 update 保持 research_version 和审核 fingerprint。

没有强制为所有打开文档写 finding 的 coverage gate。新视图先处于 pending：
有用的进入 claim 引用，无关的通过 `dismiss_observation_ids` 明确归档。
未处理片段不会在上下文压缩中消失；ESR 在最终 audit/submit 前必须引用或明确 dismiss。
已引用的同一视图再次读取不创造新 pending 义务。

## 3. 单一工具契约

`protocol.SCHEMAS` 同时用于提示生成和运行时参数检查；没有第二份手写工具 schema。

| 工具 | 职责 |
|---|---|
| search(query, top_k?) | 只返回导航候选，不创建可引用证据 |
| open_page(docid, search_action_id, query?, offset?) | 必须引用本 episode 的真实 search hit；创建／复用实际视图 |
| read_evidence(observation_id) | 重放任意已返回视图，无目录前置条件 |
| update_state(...) | 原子更新紧凑状态，消费或 dismiss pending |
| verify_answer() | 独立上下文审核当前逻辑状态；重复输入用缓存 |
| submit_answer() | 根据实验门禁结束；不接受额外 answer 绕过状态 |

Baseline 只暴露 search/open_page/read_evidence/finish(answer)，`finish` 无法在 ESR 模式调用。
基线在下一动作时将上一个响应视为已消费，保留近期历史与可重读 archive；不要求不存在的 update_state。
`audit_mode=off` 不暴露无法调用的 verify 工具。
未知动作、未知参数、非法 ID、布尔值冒充整数等均记录为失败动作，不能逃逸预算。

## 4. 审核：语义反馈与机械门禁分离

审核输入只包含 Q、目标、当前答案、必要条件以及这些条件引用的**已存实际视图**。
不包含 gold、policy 历史、旧计划、旧 verifier rationale 或检索 snippet。
模型默认相同 4B，但每次审核是新的 messages；不会借用 policy session。

输出包括 target、coverage 和逐 claim 的 supported / unknown / contradicted。
Target 检查答案类型与关系位置；Coverage 检查必要条件是否遗漏；Claim 检查实际证据。
`unknown` 是缺证，不等于 false；`contradicted` 需要冲突引用。
每个 claim 必须恰好出现一次。supported/contradicted 必须带合法、逐字可定位的 quote。
整体状态由 harness 聚合，不采信模型另写的 overall supported 字段。

审核 fingerprint 包含：Q、逻辑 state、被引用视图 ID/hash、审核客户端配置、prompt/schema 版本。
同 fingerprint 永不因 no-op update 而重复调用审核模型。缓存命中不产生新的语义判定。
改变候选、目标、必要条件或引用会失效；回到完全相同输入可复用原缓存。
research_version 是操作历史；fingerprint 才是审核适用性依据。

Gap 用稳定 claim ID 表示，另有 @target/@coverage。
旧 unknown 改写 reason 后仍是 unknown；删除 requirement 只记录 removed_claim_ids，不记 resolved。
只有同一 requirement 从 unknown/contradicted 变为 supported 才记录 resolved_claim_ids。
这只是可审阅的修复事件，**尚不是训练信用**。

## 5. 三种明确的提交条件

| 模式 | 条件 | 输出标签 |
|---|---|---|
| hard | 当前输入已审核，整体 supported，无未处理视图 | supported |
| soft | 当前输入已有有效审核，无未处理视图；不要求支持 | 保留 supported/unknown/contradicted |
| off | 当前 state 有答案及 requirements，无未处理视图 | unverified |

构造器默认 hard；在线 CLI 要求显式选择，防止默认变化污染实验。
软审核不是“把拒绝改通过”。它只改变能否结束，不改变真实性标签，也不给结果奖励。
任何模式下，显式 `answer_kind=abstain, answer=""` 可结束为 abstained，绝不变为 supported。
模型把拒答错标成 answer 的语义错误不能靠类型系统完全消除；hard 模式还依赖 target audit。

## 6. 错误、预算与停滞

JSON/参数错误、服务错误、审核协议错误、超窗与正常 semantic unknown 分开记录。
审核格式修复最多两次，保留完整原始输入；不在空上下文中请求“再次判定”。
HTTP 服务重试有固定上限；400 不通过删参数或改变 thinking 配置偷偷重试。
基础设施错误不会修改 state、审核 cache 或 gap。

所有策略动作尝试（含错误、缓存操作）受 max_actions 限制，最后一个预算动作仍可合法提交。
生成预算覆盖 policy 与 audit；服务 usage 缺失明确记 unknown，不能假装拥有完整成本数据。
实际 tokenizer + chat template 做上下文检查；无 tokenizer 的 CPU stub 仅用于测试。
近期完整交互可以移出活动上下文，但 state 与 pending 视图不能被静默删除；放不下则明确失败。

停滞信号依据同文档快照新增可见字符区间的并集，不因 duplicate open 或换 query 措辞归零。
这是**原文视图新颖性，不是语义信息增益**，不当 reward，也不强制打开 top-1 或自动换答案。

## 7. 账本与可复现性

SQLite 使用不可更新／删除触发器和 hash-chain 记录 header、每个动作、delta、错误和模型请求／响应／usage。
先生成 transition，持久化成功后才应用到内存；磁盘失败不制造未入账状态。
一个 episode 只允许一个 writer；检测到竞争 writer 拒绝继续，不合并不一致的状态。
Replay 以 SQLite mode=ro 打开，校验链条，绝不调用检索或模型，也不创建／迁移旧表。
触发器和 hash-chain 用于发现意外改写，并不是抵抗可任意重写整库攻击者的外部签名证明。

Header 固定 question、config、model/tokenizer 声明、index revision、代码 revision 和数据文件 hash。
Resume 不允许换问题／配置。服务实际载入的权重 hash 需要部署端另行核实；客户端声明不是远程证明。
凭据只从环境变量读入请求 header，不写入配置文件或日志。

## 8. 模块边界及暂不实现项

```text
protocol.py       schema / Config / typed failures
views.py          retrieval adapter / exact views / local fallback
ledger.py         durable append-only journal
engine.py         deterministic state transitions
client.py         tokenizer / bounded generation / usage
 audit.py         fresh atomic audit / quote validation
runner.py         single policy loop / bounded context / read-only replay
cli.py, demo.py   deployment entry and explicitly synthetic smoke
```

不修改 `esr_grpo.credit`、ECHO/verl integration、原奖励函数。
不实施自动数据合成、SFT、在线更强裁判依赖、复杂 planner、语义反证发现器或确定性算术工具。
本次先让语义失败不会被 harness 伪造、吞掉或放大；随后用真实 4B 校准这些语义能力。
