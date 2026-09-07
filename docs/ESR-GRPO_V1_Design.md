# ESR-GRPO：面向长程 Agent Search 的可验证研究状态与动作级信用分配

## 1. 方法概述

ESR-GRPO 面向长程 Agent Search 中两个相互关联的问题：

1. **研究状态不稳定**：Agent 在长搜索过程中会持续产生搜索结果、页面内容、中间推断、候选答案和下一步计划。如果这些信息只保存在不断改写的自然语言上下文中，一次局部理解错误可能被压缩进后续状态，并持续污染之后的搜索。
2. **结果奖励难以归因**：Agentic RL 通常只获得最终结果奖励。传统 GRPO 会将同一条 rollout 的轨迹级 advantage 广播给大量生成 token，因此成功轨迹中的无关动作可能被错误奖励，失败轨迹中的正确中间动作也可能被错误处罚。

ESR-GRPO 的核心思想是：

> **前向使用可恢复、可验证的 Claim–Evidence Research State 管理“当前研究知道了什么”；反向沿同一套 Claim–Evidence provenance 回溯“最终成功应该奖励哪些动作”。**

整个方法不增加独立 Reward Model、Critic 或冻结 Verifier。训练仍只使用 Benchmark 的最终结果奖励。

---

## 2. 设计目标

ESR-GRPO V1 主要解决以下问题：

- 将模型实际读取过的原始证据与模型当前判断分离；
- 显式记录“哪个 Claim 被哪些 Evidence 支持或反驳”；
- 在提交答案前重新基于 Raw Evidence 检查当前 Claim；
- 维护明确的 Gap，使未解决条件能够进入后续搜索；
- 在 Context 过长时安全移除已经被状态吸收的旧对话，同时保留可恢复的 Raw Evidence；
- 在 GRPO 中只把正 advantage 分配给最终成功轨迹中有高置信度贡献证据的动作。

ESR-GRPO V1 **不试图**：

- 解决 Retriever 根本召回不到关键文档的问题；
- 构建复杂知识图谱、候选图或 Claim dependency graph；
- 强制模型执行反证搜索或 Candidate Pivot；
- 使用额外的 Judge/Verifier 给中间步骤打过程分；
- 判断失败轨迹中究竟哪一个语义动作一定错误；
- 对失败轨迹进行语义负信用分配。

---

# 3. 系统状态设计

ESR-GRPO 将持久状态和当前模型上下文严格分开。

系统长期维护：

1. `RawEvidenceStore`
2. `TaskState`
3. `RecentTrajectory`
4. `FullTrajectoryLog`
5. `ProvenanceLog`

其中：

$$
\text{Persistent Storage} \neq \text{Active Context}
$$

结构化 TaskState 是系统的长期状态，不等于每一轮直接发送给模型的 Prompt。

---

## 3.1 RawEvidenceStore

只有模型**真正打开或读取**的页面才进入 RawEvidenceStore。仅出现在 Search Result 中的 snippet 不算 Raw Evidence。

```text
Evidence(
    evidence_id,
    source,
    content
)
```

约束：

- `evidence_id` 由 Harness 分配，在一条 rollout 内唯一；
- `source` 保存 docid、URL 或其它来源标识；
- `content` 保存实际返回给模型的原始页面内容；
- Evidence 创建以后不可被模型修改；
- 后续可以通过 `read_evidence(evidence_id)` 重新读取原文。

因此：

$$
\text{RawEvidence} \neq \text{Finding} \neq \text{Claim}
$$

Raw Evidence 是可恢复的外部观察；Finding 是导航索引；Claim 是模型当前需要证明或反驳的任务命题。

---

## 3.2 Evidence Directory

TaskState 中维护一个轻量的 Evidence Directory：

```text
EvidenceDirectoryEntry(
    evidence_id,
    finding
)
```

`finding` 的作用是回答：

> 这份 Evidence 大概包含什么与当前任务相关的信息？

它不是第二份 Evidence，也不是“已经验证的事实表”。

例如 Raw Evidence 为：

```text
Alice attended Amherst.
Bob was a relative of Alice.
Alice joined Z in 2017.
```

一个合适的 finding 是：

```text
页面说明 Alice 就读于 Amherst，称 Bob 与 Alice 存在亲属关系，并说明 Alice 于 2017 年加入 Z。
```

不合适的 finding 是：

```text
Bob 是 Alice 的父亲。
```

因为后者加入了原文没有明确支持的推断。

### Finding 的原则

- 由同一个 Research Policy 在 `update_state()` 中生成；
- 只描述 Evidence 明确包含的任务相关信息；
- 保留否定、限定词、日期和实体关系；
- 不写“这证明候选 X 正确”一类结论；
- 允许后续重新读取原文后修正；
- Verify 不依赖 finding 判断 Claim 是否成立，而是直接读取 Raw Evidence。

核心原则是：

> **Finding 用于检索和导航；Raw Evidence 用于验证。**

---

# 4. Claim-level TaskState

ESR-GRPO 不再只维护“最终答案 + 一个扁平 Evidence 列表”，而是显式维护 Claim。

最小 Claim 结构为：

```text
Claim(
    claim_id,
    statement,
    status,
    supporting_evidence_ids,
    contradicting_evidence_ids
)
```

其中：

```text
status ∈ {
    unresolved,
    supported,
    contradicted,
    conflict
}
```

TaskState 可以表示为：

```text
TaskState(
    answer,
    claims,
    evidence_directory,
    gaps,
    verification_status
)
```

其中：

- `answer`：当前候选答案或当前回答；
- `claims`：当前答案所依赖的具体主张；
- `evidence_directory`：已经读取的 Evidence 的轻量索引；
- `gaps`：当前尚未解决的问题；
- `verification_status`：最近一次 Verify 的结果，主要由 Harness 管理。

例如：

```text
Answer:
Alice

Claims:
C1 [supported]
Alice attended Amherst.
supporting_evidence_ids = [E1]

C2 [unresolved]
Bob is Alice's father.
supporting_evidence_ids = []

C3 [supported]
Alice joined Z after 2015.
supporting_evidence_ids = [E1]

Gaps:
G1: C2 still needs direct father evidence.
```

Claim-level State 的目标是明确表示：

$$
\text{Answer}
\rightarrow
\text{Claim}
\rightarrow
\text{Evidence}
$$

而不是：

$$
\text{Answer}
\rightarrow
\text{Flat Evidence List}
$$

---

# 5. Gap

Gap 表示当前真正阻碍答案成立的未解决问题。

最小结构：

```text
Gap(
    gap_id,
    claim_id,
    description
)
```

模型看到的 Gap 可以保持简单。Harness 在后台额外保存：

```text
created_by_verify_action_id
created_research_version
resolved_by_verify_action_id
```

### 权限约束

- `update_state()` 可以更新 Answer、Claim、Claim–Evidence 关系和 Finding；
- `update_state()` **不能清除 Gap**；
- Gap 只能由 `verify_claims()` 创建、保留或清除。

这样可以避免模型在普通 Research 阶段仅凭“感觉已经解决”就删除未解决问题。

---

# 6. State 版本管理

Harness 维护：

```text
state_version
research_version
verified_research_version
```

规则：

- 每次 TaskState 发生改变，`state_version += 1`；
- 每次 `update_state()` 成功执行，`research_version += 1`；
- 每次 `verify_claims()` 完成后，记录：

```text
verified_research_version = research_version
```

Submit 的必要条件为：

$$
\text{verified\_research\_version}
=
\text{research\_version}
$$

同时要求：

$$
\text{verification\_status} = \text{passed}
$$

以及：

$$
\text{gaps} = \varnothing
$$

这意味着：如果 Verify 之后又发生任何 Research Update，之前的 Verify 自动失效，必须重新验证后才能提交。

---

# 7. 两种模型 View

V1 只保留两种主要 View：

1. `ResearchView`
2. `VerifyView`

不增加 SearchView、UpdateView、SubmitView 等更多上下文模式。

---

## 7.1 ResearchView

ResearchView 用于普通 Search / Open / Read / Update。

建议只渲染：

- 原始 Question；
- 当前 Answer / Candidate；
- Claims 及其状态；
- 每个 Claim 当前关联的 Evidence ID；
- 当前 Gaps；
- Evidence Directory 中的 finding；
- RecentTrajectory。

正常研究上下文为：

$$
C_t^{research}
=
Q
\oplus
RenderResearch(S_t)
\oplus
H_t^{recent}
$$

ResearchView 不渲染：

- Action ID；
- 完整 provenance；
- 历史 State version；
- Trainer metadata；
- 全部 Raw Evidence；
- 长验证推理；
- 历史完整对话。

---

## 7.2 VerifyView

Verify 使用同一个 Policy，但使用新的、尽量干净的上下文。

建议：

$$
C^{verify}
=
Q
\oplus
Answer
\oplus
Claims
\oplus
ReferencedRawEvidence
$$

VerifyView 有意不包含：

- 对应 Evidence Directory finding；
- 长 Search history；
- 旧 Candidate 形成过程；
- 旧计划；
- 旧 confidence；
- 旧 Verify reasoning。

目标是降低旧 State 对重新判断的锚定。

---

# 8. Policy Actions

ESR-GRPO 在已有 `search()` 和 `open_page()` 之外增加三个核心研究动作和一个提交动作：

```text
read_evidence(evidence_id)
update_state(...)
verify_claims()
submit_answer(answer)
```

其中 Context Compression 由 Harness 自动触发，不是 Policy Action。

---

## 8.1 search()

沿用 BrowseComp-Plus 的检索工具。

Search Result 本身只代表候选页面进入 observation space，不自动进入 RawEvidenceStore。

---

## 8.2 open_page()

打开 Search Result 中的具体文档。

成功打开后：

1. Harness 将实际页面内容保存为 Raw Evidence；
2. 分配 `evidence_id`；
3. 保存当前 `open_page` action 与 Evidence 的 provenance；
4. 保存使该 docid 对 Agent 可见的上游 Search action；
5. 将 `evidence_id + raw content` 返回给模型。

---

## 8.3 read_evidence(evidence_id)

从 RawEvidenceStore 重新读取原始 Evidence。

其主要用途是：

- State 发生疑问后重新检查原文；
- Gap 修复时重看已有材料；
- Verify 前后的 Evidence 恢复；
- Finding 可能写错时重新读取原文。

---

## 8.4 update_state()

`update_state()` 是正常 Research 阶段的信息吸收动作。

建议采用结构化增量更新，例如：

```text
update_state(
    answer = ...,
    claim_updates = [...],
    evidence_findings = [...]
)
```

它可以：

- 新建或修改 Claim；
- 修改 Claim status；
- 修改 `supporting_evidence_ids`；
- 修改 `contradicting_evidence_ids`；
- 修改 Answer / Candidate；
- 创建或修正 Finding。

它不能：

- 清除 Gap；
- 修改 Raw Evidence。

### Update 时机

一般在真正读取新的 Raw Evidence，且新信息改变当前理解后调用。

Search Result 本身通常不需要立即 Update。

---

# 9. Verification

`verify_claims()` 不是普通 confidence 估计。

它执行两类 Audit：

## 9.1 Question → Claims Coverage

检查题目中的必要条件是否都被当前 Claims 覆盖。

即检查：

$$
Q \rightarrow \{C_1,C_2,\ldots,C_m\}
$$

是否遗漏了题目要求。

如果发现某个必要条件没有对应 Claim，Verify 可以创建新的 unresolved Claim 和 Gap。

---

## 9.2 RawEvidence → Claim Grounding

对每个当前 Claim，直接检查其引用的 Raw Evidence 是否真正支持该 Claim：

$$
E_k \Rightarrow C_j \; ?
$$

同时检查：

- Evidence 是否只支持更弱的说法；
- 是否存在实体或关系绑定错误；
- 是否存在矛盾 Evidence；
- 是否证据不足。

因此 Verify 的核心结构为：

$$
Q
\rightarrow
Claims
\leftarrow
RawEvidence
$$

---

## 9.3 Verify 的触发时机

Verify 不需要在每个 Evidence 后调用。

主要触发条件：

1. 当前答案和主要 Claims 看起来已经基本完整，模型准备提交；
2. 模型认为某个已有 Gap 已经修复；
3. Candidate 或关键 Claim 发生重大变化时，可以主动 Verify。

Submit 前必须完成一次针对当前 `research_version` 的 Verify。

---

# 10. Context Compression

Context Compression 与 State Update、Verification 完全分开。

三者分别回答：

- Update：新 Evidence 如何改变当前状态？
- Verify：当前状态是否真的成立？
- Compress：哪些已经被状态吸收的旧对话可以从 Active Context 中删除？

因此：

$$
\text{Update} \neq \text{Verify} \neq \text{Compress}
$$

---

## 10.1 Compression 触发

V1 由 Harness 根据 Context/token budget 自动触发。

不把 `compact_context()` 设计为需要 RL 学习的 Policy Action。

---

## 10.2 Compression 操作

压缩前：

$$
C_t
=
Q
\oplus
RenderResearch(S_t)
\oplus
H_t^{recent}
$$

压缩后：

$$
C_t'
=
Q
\oplus
RenderResearch(S_t)
\oplus
Tail(H_t^{recent})
$$

其中 Tail 可以默认保留最近 2–3 个工具交互轮次。

但有一个硬约束：

> **尚未被 State 吸收、且其中包含新 Raw Evidence 的 Observation 不能被删除。**

因此 Harness 删除旧 turn 前必须确认相关 Evidence 已经：

- 存入 RawEvidenceStore；
- 出现在 Evidence Directory；
- 完成必要的 State Update，或明确不改变当前 State。

如果某个最近 Evidence 尚未处理，则即使超过普通 recent-tail 范围，也必须暂时保留该 turn。

---

## 10.3 Compression 不重新生成总结

ESR 不在压缩边界调用模型重新总结完整历史。

Harness 直接根据最新结构化 State 构造新的 ResearchView。

因此：

$$
\text{Compression}
\neq
\text{LLM Re-summarization}
$$

Raw Evidence 始终保留在模型外部，可以按 ID 恢复。

---

# 11. 完整前向流程

一次典型 rollout：

```text
Question
↓
Search
↓
Search Results
↓
Open Page
↓
Raw Evidence E1
↓
update_state()
↓
Claim / Evidence Directory / Answer 更新
↓
继续 Search / Open / Read / Update
↓
Context 达到预算
↓
Harness 保存当前 trajectory segment
↓
Harness 使用最新 ResearchView + recent tail 重建上下文
↓
继续 Research
↓
模型认为答案基本完整
↓
verify_claims()
↓
Question → Claims Coverage Audit
RawEvidence → Claim Grounding Audit
├─ failed / needs_revision
│  ↓
│  创建或保留 Gap
│  ↓
│  Search / Read Evidence
│  ↓
│  update_state()
│  ↓
│  verify_claims()
│
└─ passed
   ↓
   submit_answer()
```

核心闭环为：

$$
Search
\rightarrow
Evidence
\rightarrow
State
\rightarrow
Verify
\rightarrow
Gap
\rightarrow
Repair
$$

---

# 12. Provenance 设计

Harness 为每一个 Policy Action 分配全局唯一的 `action_id`。

建议每条 action log 至少保存：

```text
ActionRecord(
    action_id,
    action_type,
    turn_id,
    trajectory_segment_id,
    token_start,
    token_end,
    state_version_before,
    state_version_after,
    payload
)
```

不同动作额外保存：

### Search

```text
query
returned_docids
```

### Open

```text
docid
evidence_id
upstream_search_action_id
```

### Read Evidence

```text
evidence_id
```

### Update State

```text
answer_before / answer_after
claim_deltas
finding_deltas
referenced_evidence_ids
```

### Verify

```text
audited_research_version
created_gap_ids
resolved_gap_ids
claim_verification_results
```

### Submit

```text
submitted_answer
research_version
verified_research_version
legal_submit
```

同时维护最终 Claim–Evidence relation 的 provenance，例如：

```text
relation_provenance[
    (claim_id, evidence_id, relation_type)
] = update_action_id
```

---

# 13. ESR-GRPO 反向信用分配

ESR-GRPO 只使用 Benchmark 的最终 Reward。

对同一个问题采样 $G$ 条 rollout：

$$
\tau_1,\tau_2,\ldots,\tau_G
$$

Benchmark 得到：

$$
R_1,R_2,\ldots,R_G
$$

GRPO 先计算正常的组内 advantage：

$$
A_i
=
\frac{R_i-\mu_g}
{\sigma_g+\epsilon}
$$

ESR 不改变最终 Reward 的定义，而是在 GRPO 已经得到 trajectory-level advantage 后决定：

> 这一个 advantage 应该由当前长 trajectory 中哪些动作分享？

---

## 13.1 Positive-only 原则

定义：

$$
A_i^+ = \max(A_i,0)
$$

再定义成功合法性 Gate：

$$
Z_i
=
\mathbf{1}
[
\text{task success}
\land
\text{legal submit}
\land
\text{final verify passed}
]
$$

当前 V1 只对：

$$
Z_i=1
$$

且：

$$
A_i>0
$$

的 rollout 做语义信用分配。

失败轨迹不进行语义负信用：

$$
A_i \le 0
\Rightarrow
\widetilde A_{i,t}=0
$$

原因是最终失败不能可靠说明哪一个局部语义动作一定错误。这样可以避免传统 trajectory-level negative advantage 误罚失败轨迹中本来正确的 Search、Open 或 Evidence acquisition。

---

# 14. 三类正信用

对成功 rollout，系统从最终 Verified State 反向构造贡献动作集合。

## 14.1 Final Claim–Evidence Chain

对最终 Verified State 中每一条有效 relation：

$$
(C_j,E_k,\text{support})
$$

回溯：

$$
Claim
\rightarrow
Evidence
\rightarrow
Open
\rightarrow
Search
$$

并回溯建立最终 Claim–Evidence relation 的：

$$
update\_state
$$

如果最终 Evidence 曾通过 `read_evidence()` 被重新读取并直接用于后续有效 State Update，也可以回溯对应的 Read action。

---

## 14.2 Successful Gap Repair Chain

若 Verify 创建：

$$
Gap(G_j,C_j)
$$

随后某些新 Evidence 和 State Update 真正使该 Gap 在后续 Verify 中被清除，并且修正保留到最终成功状态，则保留：

$$
Verify_{create}
\rightarrow
Gap
\rightarrow
Evidence/Update
\rightarrow
Verify_{resolve}
$$

注意：

> 不奖励 Gap 创建和清除之间时间区间里的所有动作。

只奖励与该 Gap 对应 Claim 的最终修复存在明确 provenance 的动作。

---

## 14.3 Final Decision Chain

保留：

- 最后一次形成最终 Answer 的有效 `update_state()`；
- 针对当前 `research_version` 的最终 `verify_claims()`；
- 合法的 `submit_answer()`。

---

# 15. Action Mask

设最终回溯得到的贡献动作集合为：

$$
\mathcal A_i^+
=
\mathcal A_i^{claim}
\cup
\mathcal A_i^{repair}
\cup
\mathcal A_i^{final}
$$

则：

$$
M_{i,t}
=
\mathbf{1}
[
action(i,t)\in\mathcal A_i^+
]
$$

最终 token advantage 为：

$$
\boxed{
\widetilde A_{i,t}
=
M_{i,t}
Z_i
A_i^+
}
$$

GRPO 的 ratio、clipping、KL 等主体保持不变，仅把原来的 token 上广播的 trajectory advantage 替换为 $\widetilde A_{i,t}$。

---

# 16. 与 GRPO 的结合

标准 GRPO 的 policy objective 可写成：

$$
L_{i,t}
=
-
\min
\left(
r_{i,t}A_i,
\operatorname{clip}(r_{i,t},1-\epsilon,1+\epsilon)A_i
\right)
$$

其中：

$$
r_{i,t}
=
\frac{
\pi_\theta(y_{i,t}|C_{i,t})
}{
\pi_{\theta_{\mathrm{old}}}(y_{i,t}|C_{i,t})
}
$$

ESR-GRPO 只替换 advantage：

$$
A_i
\rightarrow
\widetilde A_{i,t}
$$

得到：

$$
L^{ESR}_{i,t}
=
-
\min
\left(
r_{i,t}\widetilde A_{i,t},
\operatorname{clip}(r_{i,t},1-\epsilon,1+\epsilon)
\widetilde A_{i,t}
\right)
$$

---

# 17. 跨 Context Segment 的训练

Context Compression 以后，旧 Policy token 已经不再存在于新的 Active Prompt 中，但它们仍需要参加训练和信用分配。

因此实现时应像 ECHO 一样，在每次 Context 重建边界：

1. 保存当前 trajectory segment 的：
   - prompt token；
   - response token；
   - response mask；
   - log probability；
   - action/token provenance；
2. 重建新的 Active Context；
3. 继续生成新的 segment；
4. 最终以一个共同 `rollout_id` 将多个 segment 关联起来；
5. 只有最终 segment 获得 Benchmark reward；
6. Trainer 在 rollout 级计算 GRPO advantage；
7. 再根据每个 segment 的 `response_action_ids` 构造 ESR token mask。

建议每个 response token 对齐保存：

```text
response_action_ids: list[int]
```

无归属的 token 使用 `-1`。

Rollout 结束后产生：

```text
credited_action_ids: list[int]
```

于是每个 segment 都可以本地构造：

$$
M_t
=
\mathbf{1}
[
response\_action\_ids[t]
\in
credited\_action\_ids
]
$$

这使 ESR 的工程结构与 ECHO 的 source-turn credit routing 非常接近，但 ESR 的 credit root 从“最终选择的 Turn ID”改成“最终 Verified Claim–Evidence provenance 对应的 Action ID”。

---

# 18. 一个具体信用分配例子

问题要求找到同时满足三个条件的人：

```text
C1: attended Amherst
C2: father is Bob
C3: joined Z after 2015
```

真实答案为 Alice。

Rollout：

```text
a1 Search("Amherst graduate joined Z")
a2 Open(page_A) → E1

E1:
Alice attended Amherst.
Bob was a relative of Alice.
Alice joined Z in 2017.

a3 Update:
C1 ← E1
C2 ← E1   # 当前模型错误理解
C3 ← E1
Answer = Alice

a4 Verify:
C1 pass
C2 insufficient
C3 pass
Create Gap G1(C2)

a5 Search("Alice Bob father daughter")
a6 Open(page_B) → E2

E2:
Alice is the daughter of Bob.

a7 Update:
C2 ← E2

a8 Verify:
G1 resolved
All claims pass

a9 Search("Alice company revenue")  # 无关搜索

a10 Submit(Alice)
```

最终 Verified State：

$$
C_1\leftarrow E_1
$$

$$
C_2\leftarrow E_2
$$

$$
C_3\leftarrow E_1
$$

假设该 rollout 的 GRPO advantage 为：

$$
A_i=+1
$$

则动作级 mask 可以为：

| Action | Mask |
|---|---:|
| a1 Search | 1 |
| a2 Open E1 | 1 |
| a3 Update | 1 |
| a4 Verify | 1 |
| a5 Search | 1 |
| a6 Open E2 | 1 |
| a7 Update | 1 |
| a8 Verify | 1 |
| a9 Irrelevant Search | 0 |
| a10 Submit | 1 |

于是普通 GRPO 近似为：

$$
(+1,+1,+1,+1,+1,+1,+1,+1,+1,+1)
$$

ESR-GRPO 变成：

$$
(+1,+1,+1,+1,+1,+1,+1,+1,0,+1)
$$

如果另一条 rollout 最终失败且：

$$
A_i=-1
$$

当前 ESR V1 不把 $-1$ 广播给整条轨迹，而令该 rollout 的语义训练 mask 为 0。

---

# 19. 当前 V1 的一个已知信用粒度限制

一次 `update_state()` 可能同时包含多个 Claim change，例如：

```text
C1 ← E1   # correct
C2 ← E1   # later revised
C3 ← E1   # correct
```

如果 V1 以整个 `update_state()` 为 action-level mask，则只要该 Update 对最终 C1/C3 有贡献，整个 action 都会获得正 credit。

这会产生一定的 **mixed-update credit leakage**。

因此：

- V1 可以先使用 action-level mask，保证实现简单和与 Search/Open/Verify 粒度一致；
- 后续可以增加 `claim_span` ablation，将结构化 `update_state()` 中不同 Claim update 的 token span 分开 mask；
- `claim_span` 不改变 Reward，也不需要新模型，只改变 $M_{i,t}$ 的粒度。

这属于自然扩展，不作为第一版跑通 Pipeline 的必要条件。

---

# 20. 与 ECHO 的关系

ECHO 的核心是：

$$
\text{Final Context Selection Trace}
=
\text{Credit Assignment Trace}
$$

即最终重新选择进入 Context 的历史 Turn ID 同时作为历史 token 的 credit route。

ESR-GRPO 则改为：

$$
\text{Final Verified Semantic Relation}
=
\text{Credit Assignment Trace}
$$

即：

$$
FinalOutcome
\rightarrow
VerifiedResearchState
\rightarrow
Claim
\rightarrow
Evidence
\rightarrow
Action
$$

两者都可以使用：

- 多 segment rollout；
- rollout-level reward；
- positive-only sparse credit；
- token-aligned provenance metadata；
- GRPO advantage 后处理。

但 ESR 不使用 ECHO 的 Turn Memory 作为最终事实来源，也不使用最终 context selection 作为 credit root。

---

# 21. 与 AREX 的关系

AREX 已经证明了结构化 Research State 和长程 Context Management 对 Deep Research Agent 有价值。

ESR-GRPO 进一步强调：

1. Raw Evidence 与模型 State 分离；
2. Raw Evidence 可以按 Evidence ID 恢复；
3. Answer 被拆成 Claim；
4. Claim 显式绑定 Evidence；
5. Verify 直接重新读取 Raw Evidence；
6. Gap 独立维护；
7. 同一套 Claim–Evidence provenance 同时服务前向验证和反向 GRPO credit。

---

# 22. 训练与对比建议

4B 实验建议统一使用：

```text
Qwen/Qwen3.5-4B
```

作为以下受控实验的共同初始化：

1. Qwen3.5-4B + GRPO
2. Qwen3.5-4B + ECHO
3. Qwen3.5-4B + ESR-GRPO

三者尽量保持一致：

- BrowseComp-Plus 划分；
- Retriever；
- Judge reward；
- rollout group size；
- 最大工具调用数；
- working context budget；
- Sampling parameters；
- RL training steps。

同时使用：

```text
BAAI/AREX-Turbo
```

作为 4B 规模的外部强基线。

AREX-Turbo 是已经额外完成 Deep Research post-training 的 checkpoint，因此更适合作为 external trained baseline，而不是严格 controlled initialization baseline。

---

# 23. V1 最小实现范围

第一版只需要实现：

### 状态层

- RawEvidenceStore
- EvidenceDirectory
- Claim
- Gap
- TaskState
- StateVersion
- ProvenanceLog

### Agent Loop

- Search/Open 保持现有接口；
- Open 后自动注册 Evidence；
- `read_evidence()`；
- `update_state()`；
- Verify mode / VerifyView；
- `submit_answer()` gate；
- Context budget 触发的 State-based reconstruction；
- 多 segment rollout 保存。

### Trainer

- `response_action_ids`
- rollout-level `credited_action_ids`
- ESR positive-only advantage routing
- `$M_{i,t}Z_iA_i^+$` token mask
- 失败 rollout semantic credit = 0

### 测试

- Evidence 不可变；
- Finding 可修改；
- Update 无法清除 Gap；
- Verify 可以创建/清除 Gap；
- stale Verify 无法 Submit；
- Context reconstruction 不删除 RawEvidenceStore；
- 未处理 Evidence 不会从 Active Context 被安全删除；
- final Claim–Evidence chain 能正确回溯 Action；
- unrelated Search mask = 0；
- failed rollout semantic mask = 0。

---

# 24. 总结

ESR-GRPO V1 的核心并不是增加更多 Agent 规则，而是建立一个同时服务于推理和训练的最小 Research State：

$$
\boxed{
RawEvidence
\rightarrow
ClaimState
\rightarrow
Verification
\rightarrow
Gap
}
$$

前向：

$$
\boxed{
Search
\rightarrow
Evidence
\rightarrow
State
\rightarrow
Verify
\rightarrow
Repair
}
$$

反向：

$$
\boxed{
FinalOutcome
\rightarrow
VerifiedState
\rightarrow
Claim
\rightarrow
Evidence
\rightarrow
Action
}
$$

最终通过：

$$
\boxed{
\widetilde A_{i,t}
=
M_{i,t}Z_iA_i^+
}
$$

把 GRPO 的正 trajectory advantage 只分配给最终成功轨迹中具有可靠语义贡献证据的 Policy Action。

一句话概括：

> **ESR-GRPO 用同一套 Claim–Evidence Research State 连接“长程研究过程中该记住什么、该验证什么”和“最终成功以后究竟该奖励哪些动作”。**
