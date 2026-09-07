# RL 后训练前：Harness 介入的合规梳理（修正版）

日期：2026-09-02
依据：`/data1/ESR-GRPO/ESR-GRPO/src/esr_grpo/environment.py` 与 `rollout.py` 的实际实现；Homulillew/ESR-GRPO-Code-L《同一 Harness 下的 Agentic RL 设计分析》
状态：**本文为更正版**，取代前一版的"RL 前应拆掉策略层引导"立场。本文采用"训练与部署使用同一套 harness"的 Agentic RL 前提。

---

## 〇、立场修正说明

前一版的核心立场是："凡 harness 替模型做的策略判断，RL 前应交还模型，否则挡住 credit assignment。"

该立场隐含一个并未显式声明的目标——**训练一个最终可脱离 harness 的裸模型**。但本项目的真实目标（训练并部署同一个 model + harness 复合 Agent）并不需要如此。因此该立场**过强**。

在"训练=部署同一套 harness"前提下，正确判定一条 harness 介入是否合法的标准不是"是否替模型做决策"，而是下面三条：

1. **部署可用性**：该机制在部署阶段是否仍存在？若两端都存在，则它不是训练期特权。
2. **信息合法性**：harness 是否只使用部署阶段真实可获得的信息（当前问题、当前 evidence、verifier 返回、未解 gaps、剩余预算、当前版本号、工具错误、动作历史）？若使用 gold answer / hidden label / 未来轨迹 / 人工标注正确下一步 / 训练集特有 oracle 信息，才是真正的特权/泄漏。
3. **过渡一致性**：对同一 `(s_t, a_t)`，训练与部署的 harness 是否产生相同 `(o_{t+1}, s_{t+1})`？只有当规则、阈值、重试机制、提示在两端之间变化时，才会造成真正的分布偏移。

核心原则一句话：**最终部署中稳定属于 Harness Contract 的机制，都可以存在于 RL rollout 中。RL 优化的是模型在固定 harness 下的最优策略，而非训练一个脱离 harness 的裸模型。**

---

## 一、三层架构分类（取代原 A/B/C）

在 train=deploy 前提下，harness 介入按"承担什么角色"分三层：

| 层 | 内容 | 性质 |
|---|---|---|
| **Layer 1：环境 / 状态机** | evidence 不可变、未登记不可引用、stale 拒绝、update_state 协议、submit 合法性、tool/action schema、malformed call、动作在当前状态是否可执行 | 定义 `A_legal(s_t)`（当前状态下的合法动作集）。非法动作返回 error observation 让模型重决策，是**标准 Agentic RL 环境设计**，RL 不该重学 |
| **Layer 2：Harness / Controller** | 未解 gap 列表、剩余轮数、连续 search 次数、是否进入 deadline、verifier 是否通过、是否 SUBMIT_READY、gap 该补证据、search query 通用构造规范、建议 verify、verify 后可提交 | `π_H`：harness 自担的 controller policy。只要部署永久存在，**不属于 train-time leakage**，而是**策略分工**（policy factorization） |
| **Layer 3：模型语义策略** | 当前缺什么信息、搜什么 query、优先追哪个实体、open 哪个 source、evidence 够不够、finding 如何抽、被改后如何修改、先解哪个 gap、候选答案如何变、质量/成本权衡、何时探索/commit | 高语义、高分支、高不确定，**最该交给 RL 学习** |

关键转变：不再是"合法 vs 踩线"，而是**"这部分行为放在模型里，还是放在 harness 里？"**——这是架构分工，不是 RL 合规问题。

---

## 二、对具体介入项的重新定性

### `_gap_worklist`：不是必须删，而是定性 + ablation
- 若只报"存在未解 gap：G1…G2…" → **属于 observation**（Layer 2 结构化状态）。
- 若进一步给"从 G1 抽实体/日期/标题词去 search，不要同义改写原问题" → 是 **semantic action guidance / generic policy prior**。在 train=deploy 前提下**不天然不合理**：模型实际学的是 `π_θ(a_t|s_t, H)`，搜索能力由模型策略与 harness prior 共同构成。作为完整 Agent system 合理。
- 若给出固定序列 gap→提实体→search→open→update→verify→submit → harness 接近 workflow controller，系统被明确拆成 `π_H × π_θ`（harness 做低熵 workflow planning，模型做每步语义执行）。**只要部署就是这个架构，就没必要因进入 RL 而删除。**
- **推荐做 H0/H1/H2 三档 ablation**（见 §四），而非先验删除。

### `_soft_deadline_note`：保留或降级都成立，取决于目标
- "预算已用 90%，请尽快收尾" → controller-level stopping prior。训练部署一致即可保留，停掉行为是 `H_deadline + π_θ` 而非纯 π_θ，属架构分工。
- 若希望模型自己学停止策略，则只暴露客观信息 `remaining_steps=4`，让模型自决。两种都成立，取决于产品设计目标。

### verify→submit：可状态机化，不必靠 RL 学
- 当 verified=1、gaps=0、且为当前版本，协议下唯一合理操作就是 submit。此类属**低熵、规则确定、与语义能力关系不大**的行为。
- 可直接由状态机进入 VERIFIED_READY 甚至自动触发提交，把模型容量与 RL credit 留给更有价值的语义决策。

### `_search_open_break` 规律：重新分类，别一刀切
- stale evidence / illegal read（若"非法"由状态机严格定义）→ **硬协议不变量**（Layer 1），保留。
- "连续 N 次 search 后 break" 通常**不是 legality**——模型连续 search 可能是合理探索。更准确属 **controller heuristic**，可保留，但必须作为 Harness Contract 固定（如 MAX_SEARCH_STREAK=3 是契约的一部分，训练 3 部署 8 才会改变 transition dynamics）。

---

## 三、真正要担心的四件事（不是"策略引导"）

主线：**harness 强不等于非法，但可能影响 GRPO 学习信号与 credit 正确性。** 风险集中在四类：

1. **Harness Contract 漂移**：训练与部署的阈值/提示/break 规则不一致 → 分布偏移。解决：正式 RL 前**冻结 Harness Contract v1**（system prompt、tool schema、parser、malformed/auto-repair 策略、evidence 登记规则、state/verify/retry 语义、gap 格式、`_gap_worklist`、`_soft_deadline_note`、search streak 阈值、max turns、submission 语义、verifier 接口、tool error 表示、状态迁移）。保证 `H_train = H_eval = H_deploy`。

2. **oracle 信息**：verifier 是否使用了部署不存在的 gold label / hidden answer？需检查。违背"信息合法性"。

3. **action replacement 后的 credit 错位（最关键）**：若 harness 把 `{bad json` 自动补成 `{"query":"xxx"}` 并直接执行，而最终 reward 回传给原始 model action → **credit corruption**（成功来自 H 而非模型真实采样的动作）。必须记录 raw_action / parsed_action / executed_action / repair_flag / repair_type，原则上尽量 `a_sampled`，修复时必须明确为 environment transformation。

4. **loss mask 覆盖到 harness/tool/verifier token**：policy loss 只能覆盖模型自生成的 token；`_gap_worklist`、error message、verifier result 都是 observation，不能当 policy action token 参与 loss。`M_t = 1` 仅对 model-generated token。

另有两个学习信号维度要监控：
- **Group reward variance**：harness 太强 → 所有 rollout 被纠正到同一条路径 → `(1,1,1,1,1)` 或 `(0,0,0,0,0)` → `σ≈0` → GRPO 相对学习信号消失。需监控固定 harness 下模型自身语义决策是否仍造成足够 variance。
- **Action entropy**：harness 每步都指明 search/open/update/verify → 模型学到 `π_θ(a_t|explicit instruction)` 而非自主 workflow。这是 policy factorization（harness planner / model executor），LEGAL；但若希望模型保留 workflow 能力需注意。

---

## 四、语义重试与基础设施重试必须分开（信号保真）

- **Semantic retry**：模型生成非法 evidence ID→拒绝→重决策；或 query 不符合固定 search policy→返回 violation→重新生成。属 Agent trajectory 一部分，**应保留** `bad action → error → recovery`，因为 recovery 本身是模型能力。
- **Infrastructure retry**：verify()→HTTP timeout→底层自动重试。**不是模型犯错**，应底层自动完成（attempt×3），不把每次 transport retry 当新 agent step；否则模型浪费 capacity 学"API 超时后重发完全相同请求"。

---

## 五、修正后的整改清单（取代原 R1–R5）

| # | 整改项 | 说明 |
|---|---|---|
| R1 | **冻结 Harness Contract v1** | 全部规则/提示/阈值固定并版本化，保证 train=eval=deploy | 高 |
| R2 | **给所有 intervention 打标记** | 每条标 PROTOCOL / CONTROLLER / INFRA，明确归属层 | 高 |
| R3 | **检查 automatic correction** | 防 action-credit 错位；记录 raw/parsed/executed/repair | 高 |
| R4 | **保证 policy loss 只盖模型 token** | 所有 harness/tool/verifier token 进 loss mask | 高 |
| R5 | **加 trajectory-level transition consistency 测试** | 同一 (s,a) 两端给同 (o,s') | 中 |
| R6 | **监控 GRPO group reward variance** | 防 harness 太强致 σ≈0 学习信号消失 | 中 |
| R7 | **对 `_gap_worklist` 做 ablation，而非删除** | H0/H1/H2 三档对比 | 中 |
| R8 | **检查 verifier 是否用部署不存在 oracle** | 违背信息合法性的唯一真泄漏源 | 高 |
| R9 | **记录 raw/parsed/executed action 与 intervention 类型** | 数据审计必需 | 中 |
| R10 | **明确 semantic retry 与 infra retry 边界** | 信号保真 | 中 |

## 六、Harness 强度：Ablation 作为实验（替代"先验删除"）

| 档 | harness 内容 | 特点 |
|---|---|---|
| H0 Minimal | `Validation failed. Unresolved gaps: G1…G2…` | 模型完全自主决策；学习空间最大、sample efficiency 最低 |
| H1 Structured | 未解 gaps + 当前 evidence + 剩余预算 | 给结构化状态，不指定下一 action；可能是较好折中 |
| H2 Guided | 加"针对 gap 抽实体/日期/标题词做 query，勿只同义改写；补证据后重新 verify" | 给 generic semantic prior；短期成功率高、模型 workflow 自主性最低 |

三组均保持 H_train=H_deploy，比较：final reward、task success、submission rate、average turns、tool cost、tokens per success、group reward std、invalid action rate、retry rate、semantic search diversity、verifier pass rate、first-pass completion rate。

**由实验决定 harness 强度，而非提前把"策略指导"认定为不合法。**

---

## 七、对 4B 级模型的合适分工

若最终产品永远用 harness，不必追求"裸模型什么都自己学"。尤其对 4B，以下低熵规则塞回模型里学（JSON 格式、verify 后如何 submit、stale 不能操作、budget 快耗尽要提醒、协议状态迁移、重复 verify 无意义）**往往浪费有限 capacity 与 RL sample**。

更合适架构：
- **语义上让模型学**：语义检索、证据推理、revision、不确定性下决策。
- **机制上让 harness 保证**：syntax、invariants、workflow scaffolding。

---

## 八、最终结论与设计原则

在"训练与部署用同一套 harness"前提下，旧文"凡是 harness 替模型做的策略决策，RL 前都应删除"的结论**过强**。更准确原则：

> **凡是在最终部署中稳定属于 Harness Contract 的机制，都可以继续存在于 RL rollout 中。RL 优化的是模型在固定 harness 下的最优策略，而非必须训练一个脱离 harness 的裸模型。**

保留：协议拒绝、syntax/schema 校验、infrastructure retry（harness 处理）、semantic retry（进 trajectory）。不强制删除：`_gap_worklist`、`_soft_deadline_note`（可作为 ablation）。可状态机化：verify→submit。可作为固定 policy prior：semantic search heuristic。

**真正危险**：train/deploy mismatch、oracle 信息、action replacement 后错误 credit、错误 loss mask、harness 太强致 GRPO reward variance 消失。

系统定位：**Harness-conditioned Agentic RL** —— The harness is part of the deployed environment/controller, not a temporary training-time teacher。

**一句话设计原则**：**冻结 harness 契约，在同一套 harness 中训练模型，并对每一次干预明确记账。**