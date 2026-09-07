# ESR-GRPO Harness 实现梳理

> 现状快照（2026-09-03）。Harness = 一套对**前向研究 Agent**的约束与观测系统，把
> 「搜索 → 读证据 → 维护结构化状态 → 验证 → 提交」这条链路用可审计的事件账本串起来，
> 既约束 4B 策略不跑偏，又把动作关系留给训练做反向信用分配。
> 代码根：`src/esr_grpo/`（`environment.py` 是核心状态机）。

---

## 0. 分层：三件事各管一层

| 层 | 谁 | 职责 | 例子 |
| --- | --- | --- | --- |
| **Layer-1** | `environment.py`（ESREnvironment 状态机） | 合法动作协议、状态推进前置条件 | open_page 必须 parent=合法 search；update_state 必须 coverage 全覆盖 |
| **Layer-2** | `rollout.py` AgentRunner + environment 的确定性 guidance | 推进策略、打破死循环、预算收敛 | `_search_open_break`、`_gap_worklist`、`_soft_deadline_note` |
| **Layer-3** | 模型语义策略 | 判断答案、因果关系 | 4B 产下一动作；verify 打回与否 |

关键设计原则：**harness 只做「协议观测」与「确定性打捞」，绝不替模型判断答案语义**。
门禁的拒绝文案只点名「缺哪个证据、该用什么 ID、下一步调什么」，不裁决对错。

---

## 1. 数据协议（`models.py`）

全部**不可变 dataclass**，SQLite 里 Evidence / TaskState / ActionRecord 只允许 INSERT（触发器拒绝 UPDATE/DELETE），
保证训练回溯时看到的是不被覆盖的历史。

- **ActionKind**：`search / open_page / read_evidence / update_state / verify_answer / submit_answer / finish`
- **VerificationStatus**：`unverified → needs_revision → supported`
- **Evidence**（Raw Evidence）：`evidence_id, source, content(全文原文), content_sha256, created_by_action_id, search_action_id, created_at`
  - `search_action_id` 是**回放/排序关键**：记录这条证据是被哪次 search 打开的。
- **EvidenceFinding**：`evidence_id, finding`（Evidence Directory 里的一句简短记录，不负责判断结论）
- **TaskState**（版本化）：`version, evidence_directory, answer, supporting_evidence, gaps, verification_status, created_by_action_id`
- **Gap**：`gap_id, description, created_by_action_id`
- **ActionRecord**：`action_id, sequence_index, turn_id, kind, token_spans, legal, state_version_before/after, parent_action_ids, referenced/created_evidence_ids, active_gap_ids, metadata`
  - 这是反向信用分配的原始材料：Claim→Evidence→(created/search)→action 的父子链全部可回溯。

---

## 2. 工具生态（environment 对外接口）

### `search(query, token_spans, turn_id)`
- `retriever.search(query, top_k)` 拿 top-5 命中；纯记录，不改状态。
- 校验：query 非空。

### `open_page(docid, *, search_action_id, ...)`
- **父动作校验**：`search_action_id` 必须存在、是合法 search、且该 search 的 hits 里确实有这个 docid → 否则拒绝（Layer-1 防「凭空开页」）。
- **持久化全文**：拉整篇 `get_document`，sha256 去重（`source.key + content_sha256` 唯一）。若已有一致原文则不重复建证（`duplicate=True`），否则建 `Evidence(e{i+1})` 存**完整原文**。
- **观察视图**：返回 `_chunk_view(docid, sort_query, full)`。`sort_query` = 引发本次 open 的 `search_action.metadata["query"]`（方案 B）。chunk 视图 = 单篇按 token 分块 → BM25 按 query 排序 → 取 top-3 → 按 chunk_index 升序拼接 + 相邻去 overlap。
  - 服务异常/无 chunk → 回退 `content[:16000]`（`view="head"`）。
- 把 evidence_id 记为「本窗口可见」（见 §3 的 visible-original 门禁）。

### `read_evidence(evidence_id, ...)`
- **前置**：只能是 `evidence_directory` 里已登记的 ID（state 之外的 ID 拒绝）。
- **方案 E'**：无 offset，唯一返回 chunk 视图，排序 query 由 `_evidence_sort_query(evidence)` = `evidence.search_action_id` 对应的 search query（回退 question）。**与 open_page、verify 读同一份视图**。

### `update_state(answer, evidence_findings, supporting_evidence, ...)`
本工具门禁最密集：
1. finding 非空、不超 `finding_char_limit`、无重复 evidence_id。
2. evidence_id 必须**真实存在**（`store.get_evidence` 命中）。
3. **changed-finding 需原证可见**：若某条 finding 相对上一个 TaskState 变了，则必须已 `read_evidence`/`open_page` 亲眼读过该原文（`_visible_evidence_inputs`），否则拒绝。防止模型硬塞记忆里的旧 ID。
4. **coverage 全覆盖**（Fix7）：`evidence_directory` 必须覆盖**本轨迹所有已 open 的证据**（含旧的归档 ID）。缺哪个点名哪个，并提醒「缺失 ID 来自 open_page，需一并写入 findings」。这是 Layer-1 观测增强，不判语义。
5. `supporting_evidence` 无重复、且都在 directory 里。
6. 非空 answer 必须配 `supporting_evidence`。
- 合法则追加 TaskState（版本+1，`verification_status` 重置为 unverified，gaps 保留），记录 `changed_finding_ids/answer_changed/support_changed`。

### `verify_answer(...)`
- **前置门禁**（`_verification_error`）：有 TaskState、无未登记证据、答案有 supporting_evidence、且 `verification_status == unverified`（不能重复 verify 同一 state）。
- **方案 E'**：把每条 supporting Evidence 的 content 用 `dataclasses.replace` 换成**重建的 chunk 视图文本**（按各自 `_evidence_sort_query`），再传给 verifier —— **验证器与模型看同一份视图**，不再喂 60k 全文（堵住观察不对称/越权实体）。
- verifier 返回 `VerificationResult(status, gaps, rationale)`；异常/无法解析 → `needs_revision`（不崩轨迹）。
- 合法则追加状态：SUPPORTED 清空 gaps；NEEDS_REVISION 生成/保留 gaps。

### `submit_answer(...)`
- **提交门禁**（`_submission_error`）：已提交告警、有 TaskState、无未登记证据、answer 非空、有 supporting_evidence、**gaps 为空**、且 `verification_status == supported`。缺一即拒绝。
- 成功写入 `submitted_answer` + `submit_action_id`（只此一次）。

### `finish(answer)` —— Baseline 模式
- 无 TaskState、无验证 gate，直接提交答案。供「普通 Agent」对比条件用，保证检索层与 ESR 一致，唯一差距是少了结构化 State 与验证门禁。

### `execute_parallel(calls, turn_id)`
- 只允许 `search / open_page / read_evidence`（查询/只读类），每项分配独立 action_id，`ThreadPoolExecutor` 并发。

### `execute_tool(name, arguments, ...)`
- 统一入口。捕 `TypeError`（模型传签名外参数，如 `update_state(gaps=...)`）→ 降级为一次非法动作拒绝并指明正确 schema，不让它逃逸炸掉轨迹。

---

## 3. 观察视图：chunk（第二段检索）+ 方案 E'

**核心问题**：单篇综述 doc（几十万字）在 16k 观察窗内关键信息可能不可见。BM25 search 恒命中 doc 头部让模型看不到 RQ 等关键段（query 120 实证的观察窗缺陷）。

**解法**（`retrieval.py` + `_chunk_view`）：
- 检索服务提供 `/get_doc_chunks`：单篇按 token 分块（512 token ≈ 2048 字，overlap 64），BM25 按 query 排序取 top-3。
- `_chunk_view(docid, query, full, topk=3)`：取 chunks → 按 chunk_index 升序 → 相邻 overlap 去重 → 拼成 `[关键片段 #N]\n...`。
- `open_page` / `read_evidence` / `verify_answer` **三处统一读这份视图**（方案 E'）：
  - 排序基准都要 `_evidence_sort_query(evidence)` = 该证据 `search_action_id` 的 search query（回退 question）。
  - 保证「模型 open/重读看到的」==「验证器审计的」== 同一份 chunk 视图。
- chunk 服务不可用 → 回退 16k 头截断（`view="head"`），行为不倒退。

**方案 E' 的语义**：verify 不再读全文 60k，消除旧假 fixation（如 query 120 里 supervisor/"exclusivity" 线索）与泄露/绕过。验证器拿到的 content 与模型拿到的严格一致。

---

## 4. Store：追加式事件账本（`store.py`）

单 episode 一个 SQLite 文件，`:`memory:` 供测试。
- 4 张表：`metadata`（键值）、`evidence`、`task_states`、`actions`。
- 触发器：evidence/state/action 均 `no_update/no_delete` → **数据库层保证不可变**。
- `commit_transition(action, evidence, state, metadata_once)`：原子追加动作及其产生的 Evidence/TaskState/提交元数据。
- 查询：`list_evidence / latest_state / list_states / get_action / list_actions / snapshot`。
- 事件维度：每个 action 记录 `parent_action_ids / referenced_evidence_ids / created_evidence_ids / active_gap_ids / state_version_before/after` —— 训练时做 Credit Trace 的全部分解依据。

---

## 5. 验证器（`verification.py`，Layer-3 的外部组件）

`Verifier` 协议：`verify(question, answer, evidence) -> VerificationResult`。
- **KeywordVerifier**：测试/确定性用，验 required_terms 是否在证据 content 里（隔离 4B 可靠性）。
- **OpenAICompatibleVerifier**（正式，复用 Qwen3.5-4B，policy GPU）：
  - 独立新上下文，只喂 Question + Answer + 每条 Evidence 的 `content`（设计上就是支持它的 **chunk 视图 content**）。
  - `per_evidence_char_cap=60_000`（两条保险，正常 chunk 远小于此）、`evidence_char_budget=480_000`（超出则 needs_revision 而非静默丢弃）。
  - `enable_thinking=False`：关闭模型思考，让它直接输出干净 JSON，避免思考块污染解析。
  - 解析失败（4B 常输出探索文本）→ 保守 `needs_revision`（不崩 rollout，让主循环继续整理 answer/evidence）。
  - 重试：5xx/超时/连接错误指数退避 3 次（2s/4s），4xx 请求问题不重试；带 `chat_template_kwargs` 被 400 拒则去掉重试一次。
  - 判断规则：实体身份（答案须有可指认实体名）→ 证据逐项支撑（名字必须真出现在证据原文，不得凭空补）→ 拒绝计划/过程描述/空。

> 定界：在线 verify 与 episodes 结束后的 Benchmark Judge 分离。verify 只决定要不要继续搜；最终奖励由 Judge 给。therefore verify 的 needs_revision 并**不**判 answer 对错，只是状态审计。

---

## 6. Rollout 外层（`rollout.py`）：AgentRunner 推进与打捞

- **PolicyTurn**：含 `dropped_notes`（模型重复编码/断言非 dict → 记 dropped，noop-nudge 拼进提示让模型重发，不崩训练）。
- **AgentRunner.run()**：每轮 `render_context(mode)` → policy 产工具调用 → `execute_parallel`/`execute_tool` → 把结果与 `next_step_guidance` 并回 messages。
- **Baseline 模式**：`render_context(mode="baseline")` 只给 4 工具（search/open_page/read_evidence/**finish**），无 TaskState/无验证 gate。
- 预算用尽未提交：从最近 assistant 文本提取最佳猜测强制 `finish`（baseline）/ 收敛提醒（ESR）。

### environment 的确定性 guidance（Layer-2，全在 `environment.py`）
这些不是模型语义判断，而是**协议打捞**，经 `_next_step_guidance_core` 按优先级注入：
1. `_stale_evidence_id_break`：连续非法 update/read → 点名最近合法 open/read 返回的新 ID，禁止再用没读过原文的旧 ID。
2. `_illegal_read_break`：连续非法 read_evidence（读未登记 ID）→ 点名缺登记，让先 update_state。
3. `_search_open_break`：连续 ≥3 个纯 search 没 open/update/verify → 强制 open 最近 search 的 top-1 命中。
4. `_verify_service_glitch`：最近 verify 被拒是服务故障而非答案打回 → 引导原地重试，别去搜新证据。
5. `_gap_worklist`：把剩余 gap 编译成「提取检索词→open→update→verify」的逐条作业单。
6. `_soft_deadline_note`：预算 ≥70% 提醒收敛、≥90% 强制停止开新检索方向。
- 优先级顺序：stale-break > 无 state(纯搜/未登记) > 无 answer > unverified →请 verify > needs_revision(搜断环/服务故障/gap 作业单) > supported → submit。

---

## 7. 一层到三层的分工（「谁放行谁打回」）

| 动作 | Layer-1 硬门禁（environment） | Layer-2 打捞（guidance） | Layer-3 语义 |
| --- | --- | --- | --- |
| search | query 非空 | 连续纯搜→强制 open | 选检索词 |
| open_page | parent=合法 search、doc 在 hits 里 | — | 选哪篇 |
| update_state | 存在性/visible-original/coverage/support 校验 | stale/illegal-read 打捞 | 填 finding/answer |
| verify_answer | TaskState 存在、unverified、有 support | verify->需改先 update；服务故障重试 | verify 打回理由(gaps) |
| submit_answer | supported、gaps 空、answer 非空 | 预算收敛提醒 | 是否真收敛 |

**实测边界（强模型+真实 harness 归因）**：门禁（coverage/stale-id/visible-original/verification-once/unresolved-gaps）与 chunk 观察视图经真实 BM25+真 4B verifier 验证全部合理，非候选缺陷；query 120 经方案 E' 后残余卡点纯在 4B verifier 对「答案是问句」复合题的实体实例化过严，属验证器迭代点，而非 harness。

---

## 8. 文件清单

| 文件 | 职责 |
| --- | --- |
| `models.py` | 不可变数据协议 + enum |
| `environment.py` | 状态机、工具、门禁、chunk 观察、确定性 guidance |
| `store.py` | SQLite 追加式事件账本 + 不可变触发器 |
| `verification.py` | verifier 协议 + KeywordVerifier + OpenAICompatibleVerifier |
| `retrieval.py` | Retriever 协议 + InMemoryRetriever + EchoRetrievalClient(+get_doc_chunks) |
| `rollout.py` | OpenAIChatPolicy + AgentRunner（外层推进/打捞/预算/Baseline） |

**测试**：`tests/test_environment.py`（14 个，覆盖 chunk 观察、门禁、方案 E' verify 同视图）、`/analysis/verify_chunk_harness_gates.py`（17 个门禁回归）。