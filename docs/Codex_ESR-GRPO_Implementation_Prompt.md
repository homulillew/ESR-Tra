# Codex 实现任务：在 ECHO/verl 多轮 Agent 框架上实现 ESR-GRPO V1

你现在需要在一个以 ECHO 仓库为基础的 `verl + SGLang + multi-turn tool agent` 代码库中实现 ESR-GRPO V1。

目标不是重写训练框架，也不是复现 ECHO 的 Turn Memory 方法，而是**复用 ECHO 已经存在的多轮 rollout、context segment、metadata plumbing 和 sparse token credit 框架，实现 ESR 的 Research State、Verification、Context Reconstruction 和 Claim–Evidence Action Credit**。

请以“最小侵入、模块化、可测试”为原则实现。

---

# 0. 先阅读现有代码

在修改代码之前，先定位并阅读下列模块。如果当前 repo 的具体路径略有不同，请搜索等价模块，不要硬编码假设。

重点参考：

```text
verl/experimental/agent_loop/tool_agent_loop.py
verl/experimental/agent_loop/agent_loop.py
verl/trainer/ppo/core_algos.py
verl/trainer/ppo/ray_trainer.py
examples/sglang_multiturn/config/tool_config/search_tool_config.yaml
examples/sglang_multiturn/browsecomp_retrieval_server.py
```

特别理解 ECHO 现在已经提供的几个机制：

1. `AgentData` 持有 rollout 内部长期状态；
2. `TrajectoryOutput` 可以在 Context Compression 后保存多个 trajectory segment；
3. 每个 segment 保存 prompt/response/mask/logprob 和 token-aligned metadata；
4. 多个 segment 通过同一个 `rollout_id` 关联；
5. 最终 reward 在 rollout 级计算；
6. `core_algos.py` 中的 ECHO/SUPO advantage logic 能将 rollout-level advantage 再路由到特定 token；
7. `ray_trainer.py` 已经有把 non-tensor rollout metadata 传入 advantage estimator 的管线。

ESR 应优先复用这套 plumbing。

不要把 ECHO 的：

```text
turn_history
sum_last_turn
memory selection
selected_turn_ids
```

直接当作 ESR 的方法本体。

ESR 的 credit root 不再是 selected turn，而是：

```text
Final Verified Claim
→ Evidence
→ Provenance
→ Action ID
```

---

# 1. 实现范围限制

## 必须实现

- RawEvidenceStore
- EvidenceDirectory
- Claim-level TaskState
- Gap
- State version
- Provenance log
- `read_evidence`
- `update_state`
- Verify mode / VerifyView
- `submit_answer`
- Harness-triggered context reconstruction
- 多 segment rollout
- `response_action_ids`
- `credited_action_ids`
- ESR positive-only GRPO advantage mask
- unit tests / simulated rollout tests

## 不要实现

- Megatron-specific launch/config changes
- 新的分布式训练后端
- 新 Reward Model
- Value Critic
- frozen verifier
- external Judge for intermediate steps
- Requirement graph
- Claim dependency graph
- Candidate graph
- mandatory counter-search
- candidate pivot controller
- negative semantic credit for failed rollouts
- ECHO-style learned memory selection
- model-generated rolling summary as ESR context compression

训练后端保持现有 verl 能工作的方式即可。不要为了 ESR 修改 Megatron/FSDP 等底层训练逻辑。

---

# 2. 目标模型

代码不能硬编码模型，但本项目第一阶段目标 Policy 是：

```text
Qwen/Qwen3.5-4B
```

需要保证：

- tool calling 能正常工作；
- chat template 不依赖 32B 模型特例；
- 所有新配置通过 Hydra/现有 config 系统传入；
- 不在 ESR 核心模块里写死模型路径。

---

# 3. 建议新增模块

尽量不要继续把所有逻辑堆进 `tool_agent_loop.py`。

建议新增类似：

```text
verl/experimental/agent_loop/esr_state.py
verl/experimental/agent_loop/esr_context.py
verl/experimental/agent_loop/esr_credit.py
```

如果现有 repo 结构更适合其它位置，可以调整，但保持职责清晰。

---

# 4. ESR State 数据结构

实现 dataclass 或等价 typed structure。

## 4.1 Evidence

```python
@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source: dict
    content: str
    origin_open_action_id: int
    origin_search_action_id: int | None
```

Evidence 创建以后不可修改。

---

## 4.2 EvidenceDirectoryEntry

```python
@dataclass
class EvidenceDirectoryEntry:
    evidence_id: str
    finding: str
```

finding 可以被后续 `update_state()` 修改。

---

## 4.3 Claim

```python
@dataclass
class Claim:
    claim_id: str
    statement: str
    status: str
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
```

允许的 status：

```text
unresolved
supported
contradicted
conflict
```

---

## 4.4 Gap

模型可见字段：

```python
@dataclass
class Gap:
    gap_id: str
    claim_id: str | None
    description: str
```

Harness 后台额外维护：

```text
created_by_verify_action_id
created_research_version
resolved_by_verify_action_id
```

---

## 4.5 TaskState

```python
@dataclass
class TaskState:
    answer: str | None
    claims: dict[str, Claim]
    evidence_directory: dict[str, EvidenceDirectoryEntry]
    gaps: dict[str, Gap]
    verification_status: str
    state_version: int
    research_version: int
    verified_research_version: int | None
```

---

# 5. Provenance 数据结构

每个 Policy Action 分配 rollout 内唯一的整数 `action_id`。

实现：

```python
@dataclass
class ActionRecord:
    action_id: int
    action_type: str
    turn_id: int
    trajectory_segment_id: int
    token_start: int
    token_end: int
    state_version_before: int
    state_version_after: int
    payload: dict
```

Action type 至少包括：

```text
search
open_page
read_evidence
update_state
verify
submit
```

另外维护：

```python
relation_provenance: dict[
    tuple[str, str, str],  # claim_id, evidence_id, relation_type
    int                    # update_action_id
]
```

以及：

```text
answer_provenance_action_id
docid_to_latest_search_action_id
evidence_access_log
```

---

# 6. Action ID 与 token 对齐

这是实现 ESR credit 的关键。

在每个 trajectory segment 中新增与 `response_ids` 等长的：

```python
response_action_ids: list[int]
```

要求：

```python
len(response_action_ids) == len(response_ids)
```

规则：

- 某个显式 tool/action 的 trainable assistant token 标记对应 `action_id`；
- tool observation token 仍由现有 `response_mask` 控制，不参加 policy gradient；
- 无法可靠归属到显式 Action 的普通 reasoning token 使用 `-1`；
- `verify` 专用生成可以整体使用同一个 verify action id；
- `submit` 最终生成整体使用 submit action id；
- 如果一个 assistant message 有多个并行 tool call，尽可能只给各自 tool-call token span 分配不同 action id，共享 reasoning token 可以保持 `-1`。

不要为了给所有 reasoning token 强行分配 action id 而引入模糊归因。

---

# 7. Search / Open 复用现有 ECHO 工具

ECHO 当前已经有：

```text
search(query, topk)
open_page(docid, query?)
```

尽量复用。

## Search

执行以后记录：

```text
search_action_id
query
returned_docids
```

更新：

```python
docid_to_latest_search_action_id[docid] = search_action_id
```

如果同一 docid 被多个 Search 返回，记录**当前 open 之前最近一次让该 docid 对 Agent 可见的 Search**作为主要 upstream search。

---

## Open Page

成功返回页面后：

1. 创建新的 immutable Evidence；
2. 分配 `evidence_id`，例如 `E1`, `E2`, ...；
3. 记录：
   - `origin_open_action_id`
   - `origin_search_action_id`
4. 返回给模型时必须明确带上 Evidence ID，例如：

```text
[EVIDENCE_ID: E2]
[SOURCE_DOCID: ...]
<raw page content>
```

注意：

- Search snippet 不进入 RawEvidenceStore；
- 只有实际 open/read 的页面创建 Evidence。

---

# 8. 新增 read_evidence 工具

实现：

```text
read_evidence(evidence_id)
```

行为：

- 从当前 rollout 的 RawEvidenceStore 读取；
- 返回 immutable raw content；
- 不生成新的 Evidence ID；
- 记录一个新的 `read_evidence` action_id；
- 将该 action 写入 evidence access log。

不存在的 ID 返回明确 tool error，不修改 State。

---

# 9. 新增 update_state 工具

建议使用增量结构，而不是要求模型每次重写完整 State。

Schema 可以类似：

```json
{
  "answer": "Alice",
  "evidence_findings": [
    {
      "evidence_id": "E1",
      "finding": "..."
    }
  ],
  "claim_updates": [
    {
      "claim_id": "C1",
      "statement": "Alice attended Amherst.",
      "status": "supported",
      "supporting_evidence_ids": ["E1"],
      "contradicting_evidence_ids": []
    }
  ]
}
```

要求：

1. referenced Evidence ID 必须存在；
2. claim_id 必须稳定；
3. 新 Claim 可以创建，已有 Claim 可以覆盖其当前字段；
4. finding 可以新建或修正；
5. answer 可以修改；
6. **不能修改/删除 gaps**；
7. 不能修改 Raw Evidence；
8. 成功 Update 后：
   - `research_version += 1`
   - `state_version += 1`
   - `verification_status = "stale"`
9. 记录 before/after delta；
10. 更新最终 relation provenance：

```text
(claim_id, evidence_id, support) → update_action_id
(claim_id, evidence_id, contradict) → update_action_id
```

如果某 relation 被移除，要同步删除/替换其 active relation provenance。

---

# 10. Evidence Directory 覆盖

Harness 应知道哪些 Evidence 已经进入 Directory。

Context Reconstruction 删除某个旧 Open/Read observation 前，必须确认：

```text
该 observation 对应的 Evidence
已经存在于 RawEvidenceStore
且已经进入 EvidenceDirectory
```

如果 Evidence 尚未处理：

- 不要删除这个包含 Raw Evidence 的 recent turn；
- 即使它超过普通 recent-tail 范围，也暂时保留；
- 可以给 Policy 一个简短 system hint：先使用 `update_state` 登记新 Evidence。

不要因为 context budget 直接丢失尚未处理的 Evidence observation。

---

# 11. ResearchView

实现纯函数：

```python
render_research_view(question, task_state) -> list[message] | str
```

只渲染：

```text
Question
Current Answer/Candidate
Claims
  - statement
  - status
  - supporting evidence IDs
  - contradicting evidence IDs
Gaps
Evidence Directory
  - evidence_id
  - finding
```

不要渲染：

```text
action ids
relation provenance
state history
trainer metadata
raw evidence full text
old verify reasoning
old search history
```

正常 Context：

```text
System
+ Question
+ ResearchView(latest TaskState)
+ RecentTrajectory
```

---

# 12. Harness-triggered Context Reconstruction

不要实现 ESR 的 model-generated rolling summary。

当 active context token 数超过配置阈值：

```text
esr_working_context_length
```

执行：

1. 保存当前 trajectory segment；
2. 保留 FullTrajectoryLog 和 RawEvidenceStore；
3. 构造新的 ResearchView；
4. 自动保留最近 `esr_recent_turns` 个 turn，默认 3；
5. 额外保留所有仍含“未处理 Evidence”的 turn；
6. 重建 active messages；
7. 开启新的 trajectory segment。

建议直接复用 ECHO 现有：

```text
TrajectoryOutput
trajectory_outputs
rollout_id
traj_idx
is_final
```

等多 segment 机制。

重要：

> Context Reconstruction 只改变 Active Context，不修改 TaskState，不修改 research_version，也不是 Policy Action。

---

# 13. Verify 模式

这是 ESR 与普通 ECHO agent loop 差异最大的部分。

Policy 调用：

```text
verify_claims()
```

以后，不要让普通 external tool 直接“替模型验证”。

而是：

1. 创建 `verify_action_id`；
2. Agent Loop 进入 `VERIFYING` 状态；
3. Harness 构造 fresh VerifyView；
4. 使用**同一个 policy**进行一次专门的 verification generation；
5. verification generation 不允许 Search/Open 等普通工具调用；
6. 解析结构化 verification result；
7. 应用到 TaskState；
8. 恢复普通 Research context。

可以给 `AgentState` 新增：

```text
VERIFYING
```

也可以用等价机制实现，但不要启用第二个模型。

---

# 14. VerifyView

只包含：

```text
System: evidence-grounded audit instruction
Original Question
Current Answer
Current Claims
Raw Evidence directly referenced by those Claims
Current Gaps（可选，但建议保留）
```

明确排除：

```text
Evidence Directory findings for referenced evidence
long search history
old plans
old candidate reasoning
old confidence
old verification reasoning
```

---

# 15. Verification 输出结构

要求模型返回严格 JSON 或严格 tag-wrapped JSON。

例如：

```json
{
  "claim_results": [
    {
      "claim_id": "C1",
      "status": "supported",
      "reason": "E1 explicitly states ...",
      "supporting_evidence_ids": ["E1"],
      "contradicting_evidence_ids": []
    }
  ],
  "missing_claims": [
    {
      "claim_id": "C4",
      "statement": "...",
      "gap_description": "..."
    }
  ],
  "new_gaps": [
    {
      "claim_id": "C2",
      "description": "Need direct evidence that Bob is Alice's father."
    }
  ],
  "resolved_gap_ids": ["G1"],
  "overall_status": "passed"
}
```

Harness 必须验证：

- Evidence ID 存在；
- claim_id 有效；
- resolved gap id 存在；
- `overall_status=passed` 时 gaps 必须最终为空；
- missing claim 会创建 unresolved Claim + Gap。

Verify 完成后：

```text
verified_research_version = research_version
state_version += 1
verification_status = result
```

注意：

- Verify 可以创建或清除 Gap；
- Update 不可以清除 Gap。

---

# 16. Verify 逻辑目标

Verify prompt 明确要求执行两类检查：

## A. Question → Claims Coverage

检查题目所有必要条件是否都有 Claim。

## B. RawEvidence → Claim Grounding

检查引用 Raw Evidence 是否真的支持当前 Claim。

不要让模型输出单一 confidence score 作为通过依据。

---

# 17. Submit

用新的：

```text
submit_answer(answer)
```

替代/禁用原 ECHO 的直接 `finish`。

Harness gate：

```python
legal_submit = (
    task_state.verification_status == "passed"
    and task_state.verified_research_version == task_state.research_version
    and len(task_state.gaps) == 0
)
```

如果不合法：

- 返回 tool error；
- 不 terminate；
- 告诉 policy 必须先 Verify / repair gap。

合法时：

- 记录 `submit_action_id`；
- 保存 final state snapshot；
- terminate rollout；
- final answer 继续交给现有 BrowseComp-Plus reward/judge。

---

# 18. Gap provenance

Harness 对每个 Gap 后台保存：

```text
gap_id
claim_id
created_by_verify_action_id
created_research_version
resolved_by_verify_action_id
```

Verify 创建 gap 时赋值。

Verify 明确清除 gap 时记录 `resolved_by_verify_action_id`。

---

# 19. Rollout 结束后的 credit traceback

新增独立函数，例如：

```python
compute_esr_credited_action_ids(
    final_task_state,
    provenance_log,
    evidence_store,
    legal_submit,
    task_success,
) -> set[int]
```

只对：

```text
task_success == True
legal_submit == True
final verification passed
```

计算 semantic positive credit。

失败 rollout 返回空集合：

```python
set()
```

---

# 20. Final Claim–Evidence trace

从 final verified TaskState 遍历所有最终有效：

```text
claim.supporting_evidence_ids
```

对于每个：

```text
(claim_id, evidence_id, support)
```

加入：

1. 当前 active relation 的 `update_action_id`；
2. Evidence 的 `origin_open_action_id`；
3. Evidence 的 `origin_search_action_id`（如果存在）；
4. 如果该 relation 对应的最终 Update 明确使用了最近一次 `read_evidence`，加入对应 read action。

不要根据“这个 Evidence 曾经在轨迹里出现过”奖励所有相关动作。

---

# 21. Gap Repair trace

对最终已经成功解决的 Gap：

```text
Verify(create)
→ Gap
→ repair
→ Verify(resolve)
```

只加入：

- `created_by_verify_action_id`
- `resolved_by_verify_action_id`
- gap 对应 Claim 最终保留下来的 relation update action
- 这些 final relation Evidence 的 acquisition provenance

不要简单奖励：

```text
[gap creation time, gap resolution time]
```

区间中的所有 Search。

---

# 22. Final decision trace

加入：

- 最后形成 final answer 的 `update_state` action；
- final verify action；
- legal submit action。

---

# 23. ESR token mask

Rollout 结束后得到：

```python
credited_action_ids: set[int]
```

每个 segment 已经保存：

```python
response_action_ids
```

于是：

```python
credit_mask = torch.tensor([
    1 if action_id in credited_action_ids else 0
    for action_id in response_action_ids
])
```

再与现有 response mask 相乘。

---

# 24. ESR Advantage

不要新增 process reward。

Benchmark reward 保持不变。

先按正常 GRPO group 计算：

$$
A_i
=
\frac{R_i-\mu_g}
{\sigma_g+\epsilon}
$$

然后：

$$
A_i^+
=
\max(A_i,0)
$$

成功合法性：

$$
Z_i
=
\mathbf{1}
[
task\_success
\land
legal\_submit
\land
final\_verify\_passed
]
$$

ESR token advantage：

$$
\widetilde A_{i,t}
=
M_{i,t}Z_iA_i^+
$$

失败 rollout：

```text
credited_action_ids = empty
```

因此 semantic ESR advantage 全部为 0。

不要对失败 rollout 中“看起来错误”的 State Update 做负 semantic credit。

---

# 25. Trainer 实现建议

不要重写 PPO/GRPO loss。

优先参考 ECHO 当前 `compute_supo_advantage()` / ECHO sparse credit 的做法。

可以：

```python
@register_adv_est("esr_grpo")
def compute_esr_advantage(...):
    ...
```

或者在现有 SUPO/ECHO multi-segment estimator 上增加清晰独立的 ESR mode。

推荐独立 estimator，减少与 ECHO 逻辑互相污染。

输入 metadata 至少包括：

```text
rollout_id
is_final
overlong
traj_idx
response_action_ids
credited_action_ids
legal_submit
task_success
```

行为：

1. 聚合同一个 rollout 的 final reward；
2. 按 prompt group 计算正常 GRPO scalar advantage；
3. 同一个 rollout 的所有 segment 共享同一个 scalar $A_i$；
4. 取 $A_i^+$；
5. 使用 `credited_action_ids` 和每段 `response_action_ids` 生成 token mask；
6. 得到 $\widetilde A_{i,t}$；
7. overlong / invalid rollout 默认 semantic advantage = 0。

不要改变现有 clipping / policy loss 公式。

---

# 26. Metadata plumbing

参考 ECHO 在：

```text
tool_agent_loop.py
agent_loop.py
ray_trainer.py
core_algos.py
```

中传：

```text
response_turn_ids
selected_turn_ids
```

的方式。

ESR 对应新增：

```text
esr_response_action_ids
esr_credited_action_ids
esr_legal_submit
esr_task_success
```

确保：

- numpy/object array 序列化正常；
- DataProto concat/repeat/reorder 后不会错位；
- multi-segment rollout 的 rollout_id 保持一致；
- padding sample 不污染 group advantage。

---

# 27. Action-level V1

第一版统一使用 action-level mask。

即：

```text
search
open
read
update
verify
submit
```

整个逻辑 action 进入或退出 credit set。

不要第一版就实现 Claim-span token mask。

但请把数据结构设计成后续容易支持，例如 `ActionRecord.payload` 中保留 `claim_deltas` 和 token span 信息。

可以加配置占位：

```text
esr_credit_granularity: action
```

但当前只实现 `action`。

---

# 28. Research System Prompt

新增 ESR 专用 system prompt，要求 Policy：

1. Search result 只是候选，不等于已读 Evidence；
2. 真正打开页面后会得到 Evidence ID；
3. 读取新 Evidence 后，应使用 `update_state` 吸收有用信息；
4. finding 只描述原文明确说了什么，不加入没有根据的推断；
5. Answer 必须拆成 Claims；
6. Claim 要明确关联 supporting/contradicting Evidence ID；
7. Gap 不能由普通 update 清除；
8. 认为答案完整时调用 `verify_claims`；
9. Gap 修复后必须再次 `verify_claims`；
10. 只有 Verify 通过且无 Gap 时才能 `submit_answer`；
11. 不要为了增加搜索量而重复搜索，优先解决当前 Gap。

---

# 29. Context Token 预算

新增配置，例如：

```yaml
esr:
  enable: true
  working_context_length: 16384
  recent_turns: 3
  credit_granularity: action
```

不要硬编码 32K。

4B smoke test 可以先使用较短 working context。

---

# 30. 必须写的测试

## 30.1 Evidence Store

测试：

- open 后生成 E1；
- E1 content 不可修改；
- read_evidence(E1) 返回完全相同内容；
- search snippet 不创建 Evidence。

---

## 30.2 Update Permission

测试：

- update 可以改 Claim；
- update 可以改 finding；
- update 可以改 answer；
- update 不能删除 gap；
- update 后 research_version 增加；
- update 后 verification 变 stale。

---

## 30.3 Verify / Submit Gate

测试：

```text
update
→ verify passed
→ submit allowed
```

以及：

```text
update
→ verify passed
→ update again
→ submit rejected
→ verify again
→ submit allowed
```

---

## 30.4 Context Reconstruction

构造：

```text
Search
Open E1
Update E1
很多历史 turn
```

触发 reconstruction 后检查：

- E1 raw content 仍在 RawEvidenceStore；
- ResearchView 仍有 E1 finding；
- 旧 raw observation 可以从 active messages 消失；
- read_evidence(E1) 仍可恢复原文。

再测试未处理 Evidence：

```text
Open E2
但还没 update_state
```

触发 reconstruction 时：

- 含 E2 raw observation 的 turn 不能被删除。

---

## 30.5 VerifyView Isolation

测试 VerifyView：

必须包含：

```text
Question
Claims
Raw Evidence
```

不得包含：

```text
对应 Evidence finding
长 Search history
old reasoning
old confidence
```

---

## 30.6 Credit Trace

使用固定模拟 rollout：

```text
a1 Search useful
a2 Open E1
a3 Update C1←E1
a4 Search irrelevant
a5 Verify creates G1
a6 Search useful
a7 Open E2
a8 Update C2←E2
a9 Verify resolves G1
a10 Submit correct
```

期望：

```text
credited = {
  a1, a2, a3,
  a5,
  a6, a7, a8, a9,
  a10
}
```

且：

```text
a4 not in credited
```

---

## 30.7 Failed Rollout

同样构造一个最终错误 rollout。

即使里面有 useful Search/Open：

```text
credited_action_ids == empty
```

ESR semantic token advantage 全 0。

---

## 30.8 Multi-segment Alignment

至少模拟一次 context reconstruction。

检查：

- 同一 rollout 产生两个以上 segment；
- rollout_id 相同；
- 每段 `len(response_action_ids) == len(response_ids)`；
- final credited action 如果位于早期 segment，对应早期 token 仍能得到正 advantage；
- irrelevant action 即使位于成功 rollout 也为 0。

---

# 31. Debug / Logging

增加可读 debug 输出，但可通过 config 关闭。

每个 rollout 最终建议输出：

```text
Final reward
GRPO scalar advantage
Legal submit
Final TaskState
Final Claim-Evidence edges
Created/resolved gaps
Credited action IDs
Credit density
Per-action:
  action_id
  type
  mask
  reason
```

Credit reason 例如：

```text
final_claim_support
gap_repair
final_answer_update
final_verify
submit
```

这对后续 bad-case 分析非常重要。

---

# 32. 不要做的“聪明优化”

第一版请避免：

- 自动给失败轨迹中的错误 Update 负 reward；
- 根据 Verify 自己的判断产生额外 numeric reward；
- 根据 confidence 调 reward；
- 根据 Search relevance score 直接打 reward；
- 根据 Evidence Recall/gold doc 直接决定 credit；
- 用 gold evidence 作为训练时隐式 supervision；
- 自动 reward 所有 gap 区间动作；
- 自动 reward 所有 final segment token；
- 自动 reward 所有最终正确 trajectory token。

ESR 的核心必须保持：

```text
Final outcome reward only
+
Final verified semantic provenance
+
Positive-only sparse action credit
```

---

# 33. 与 ECHO 共存

不要删除 ECHO 现有功能。

最好通过 config：

```yaml
algorithm:
  adv_estimator: esr_grpo

actor_rollout_ref:
  rollout:
    multi_turn:
      context_compression_method: esr_state
```

或等价清晰配置切换。

目标是最终可以在同一个 repo 中运行：

```text
GRPO
ECHO
ESR-GRPO
```

以便使用相同：

- Policy initialization
- Retriever
- BrowseComp-Plus data
- Judge reward
- rollout settings

进行受控实验。

---

# 34. 完成标准

实现完成后，请给出：

1. 修改/新增文件列表；
2. 每个文件的职责；
3. 数据流说明；
4. Context reconstruction 流程；
5. Verify state machine 流程；
6. Credit traceback 流程；
7. ESR advantage 公式对应的代码位置；
8. 配置示例；
9. 单元测试结果；
10. 一个 deterministic simulated rollout 的完整 debug 输出。

在提交最终实现前，至少运行相关 unit tests。

如果现有 ECHO 代码结构与这里的建议冲突，优先保持现有框架的稳定性，但不能改变以下方法语义：

$$
RawEvidence
\neq
Finding
\neq
Claim
$$

$$
Update
\neq
Verify
\neq
ContextCompression
$$

$$
FinalOutcome
\rightarrow
VerifiedState
\rightarrow
Claim
\rightarrow
Evidence
\rightarrow
Action
$$

以及最终 ESR advantage：

$$
\boxed{
\widetilde A_{i,t}
=
M_{i,t}Z_iA_i^+
}
$$

其中失败 rollout 当前不做语义负信用。
