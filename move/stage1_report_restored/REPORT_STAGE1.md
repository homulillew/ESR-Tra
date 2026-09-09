# Stage1 前向验证报告 — ESR Harness State 2.1（32B：policy + verifier 同模型）

- **日期**：2026-09-09
- **政策**：Qwen3-32B（`:8002`，OpenAI 兼容）作 **policy + verifier 同一模型**（用户指令："32B 的实验就 32B 推理和验证"）
- **对照**：Stage0 = 强 API（Lanz-Medium）policy+verifier。本报告为**弱模型（32B）**，并补上 Stage0 缺失的 `baseline/off` 臂。
- **配套文件**：`trajectories/` = 全部 32 局逐 decision 轨迹；`source_code/` = 相关源码。

---

## 8. 附：源码索引（`source_code/`）

| 路径 | 引用点 |
|---|---|
| `source_code/run_stage1.sh` / `run_stage1_batch.sh` | §2 全部改动（唯一新增），32 局 CLI 串行 batcher |
| `source_code/src/esr_harness/protocol.py` | delta 工具字段（target/answer/claim_updates/retire/focus/dismiss/attempt_note） |
| `source_code/src/esr_harness/prompts.py` | `END_SYSTEM[hard/soft/off]`（§5 verify 机制）；`ESR_SYSTEM`（focus.need） |
| `source_code/src/esr_harness/engine.py` | §2 `_submit` hard/soft 放行；`_verify` |
| `source_code/src/esr_harness/audit.py` | §2 `status()` / `validate_report()` |
| `source_code/src/esr_harness/runner.py` / `cli.py` | CLI `run` 入口（Stage1 对 32B 走原生 OpenAI path） |
| `source_code/src/esr_harness/context.py` / `views.py` / `ledger.py` | workcard/视图/账本 |

---

## 目录
1. [实验设置](#1-实验设置)
2. [我修改了什么代码 —— off / hard / soft（Stage1 视角）](#2-我修改了什么代码--off--hard--softstage1-视角)
3. [完整 Stage1 结果](#3-完整-stage1-结果)
4. [完整轨迹展示（代表性 4 条）](#4-完整轨迹展示代表性-4-条)
5. [完整 Stage1 分析](#5-完整-stage1-分析)
6. [Stage0 vs Stage1 对比——state 设计是否有帮助](#6-stage0-vs-stage1-对比state-设计是否有帮助)

---

## 1. 实验设置

| 项 | 值 |
|---|---|
| 阶段 | Stage1（用户指令：先强 API 后 32B，policy 与 verifier 同一模型） |
| policy | **Qwen3-32B**（`:8002`，OpenAI `/v1`），thinking ON，temp 0.6 |
| verifier | **与 policy 同一模型**（Qwen3-32B），thinking OFF（`--no-audit-thinking`），temp 0.0 |
| schema | **3**（纯 delta state）。**走原生 CLI `python -m esr_harness run`** |
| 数据 | `questions_only.jsonl`（8 题，无 gold 泄漏） |
| 配置 | max_actions=64, max_context=32768, output 2048, budget 24000, top_k=5, view_chars=8000, max_pending=4 |
| 并发 | 1（串行） |
| 题集 | 8 题与 Stage0 相同（324/120/594/234/364/854/1000/170） |
| 局数 | 8 题 × **4 臂** = **32 局**（此处有 baseline/off，因 CLI 支持） |
| 崩溃 | **0**（全部 exit=0，无 traceback/HTTP 错误） |

**关键差异**：Stage0 因 Lanz 只走 Anthropic Messages、没有 OpenAI `/chat`，被迫**程序化写驱动适配器**；Stage1 直接用原生 CLI `--mode baseline|esr --audit-mode off|hard|soft`，**无需任何自定义适配器**。

---

## 2. 我修改了什么代码 —— off / hard / soft（Stage1 视角）

**Stage1 没有任何逻辑改动**——off/hard/soft 完全由置顶的既有 harness 逻辑决定，我只写了串行 batcher `run_stage1_batch.sh`：

```bash
ARM_ARGS[baseline/off]="--mode baseline --audit-mode off"   # 无 state 循环, 无 auditor
ARM_ARGS[esr/off]     ="--mode esr  --audit-mode off"       # state 循环, 无 auditor
ARM_ARGS[esr/hard]    ="--mode esr  --audit-mode hard"      # state 循环, auditor 硬校验
ARM_ARGS[esr/soft]    ="--mode esr  --audit-mode soft"      # state 循环, auditor 宽松
```

每局调用（与 FORWARD_VALIDATION_PROMPT 单题模板一致）：
```bash
python -m esr_harness run \
  --dataset questions_only.jsonl --qid "$q" ${ARM_ARGS[$arm]} \
  --policy-url http://127.0.0.1:8002/v1 --model Qwen3-32B \
  --thinking --temperature 0.6 --no-audit-thinking \
  --retrieval-url http://127.0.0.1:8000 \
  --max-actions 64 --max-context-tokens 32768 --max-output-tokens 2048 \
  --audit-max-output-tokens 2048 --max-total-completion-tokens 24000 \
  --search-top-k 5 --view-chars 8000 --max-pending-views 4 --recent-actions 4 \
  --store "$q.sqlite" --output "$q.summary.json"
```

**off/hard/soft 的语义仍由 `engine.py:_submit` + `audit.py:status()` 决定**（与 Stage0 报告 §3.2 完全相同）：
- **off**：auditor=None → `evidence_status=unverified`，提交不背书，policy 自行交/弃。
- **hard**：`audit_mode=="hard" and audit.status != "supported"` → `HarnessError("not_supported","Repair or abstain")`；需 `supported` 才放行。
- **soft**：`audit_mode!="hard"` → `status(report)` 保留真实标签，unknown/contradicted 也放行提交。

---

## 3. 完整 Stage1 结果（32 局）

| 臂 | submitted | abstained | budget_exh | correct/8 | 总 invalid | 总 attempts |
|---|---|---|---|---|---|---|
| **baseline/off** | **8** | 0 | 0 | **3** | 6 | 22 |
| esr/off | 1 | 4 | 3 | **1** | 76 | 100 |
| esr/hard | 1 | 4 | 3 | **1** | 113 | 140 |
| esr/soft | 1 | 3 | 4 | **0** | 112 | 147 |

**逐局明细**：

| qid | cat | baseline/off | esr/off | esr/hard | esr/soft | gold |
|---|---|---|---|---|---|---|
| 324 | easy | sub ✗"Jennifer Harman" | budget(None) | budget(None) | budget(None) | Svetlana Gromenkova |
| 120 | easy | sub ✓ | **sub ✓** | **sub ✓supported** | abstain ✗"third..." | …Nigeria? |
| 594 | easy | sub ✓ | budget(None) | budget(None) | budget(None) | XML |
| 234 | lockin | sub ✗"Cane River" | abstain | abstain | sub ✗"Nancy's Brook" | Little Lovely |
| 364 | binding | sub ✗"Justin Bieber" | budget(None) | abstain | budget(None) | Bada Lee |
| 854 | binding | sub ✗"(weight)" | abstain | abstain | abstain | 37kg |
| 1000 | long | sub ✓ | abstain | budget(None) | budget(None) | Matthew Arnum Barnor |
| 170 | long | sub ✗"Atlanta" | abstain | abstain | abstain | The Good Karma Hospital |

> `✓ = final_draft 与 gold whitespace-insensitive 匹配`。`(None)=abstain/budget 时 final_draft 为空`。

**abstain/budget 时 final_draft 的空洞性**（交叉核验）：全部 esr 臂的 abstain/budget 局里，**除 q120（abstain 有 draft）外，其余 final_draft 均为 None**——32B 在 esr 循环里**根本不形成/不保留候选答案**。

---

## 4. 完整轨迹展示（代表性 4 条）

> 全部 32 条在 `trajectories/`。以下 4 条覆盖不同结局。

### 4.1 `baseline_off_364`（submitted，错误）— single-shot
```
### baseline/off / qid 364  (2 decisions, 6 events)
[d1 ] policy: "K-pop audition program Mnet 2010-2017 ... group debuted..."
      [finish] ok=True
```
**读法**：baseline 无 state 循环，policy 一次生成直接 `finish` 答 → 快、稳，但完全无检索校验，答错 "Justin Bieber"。

### 4.2 `esr_off_364`（budget_exhausted，draft=None）— ESR 崩溃代表
```
### esr/off / qid 364  (~15 decisions, 大量 search/update)
[d1 ] search    q="K-pop audition program Mnet 2010 2017 ..."
[d...] search    (反复同义 query: "...same country debut Japan showcase...")
[d...] update_state 多次 claim[c0] 绑定
... generation_budget_exhausted, final_draft=None
```
**读法**：32B 进入 ESR 循环后反复 search/update 却无法收敛到答案，最终当 create_budget 耗尽，**却连一个 best-draft 都没保留**（None）。与 Stage0 Lanz 的 `esr_off_364`（同样 budget 但 draft=含 Bada Lee 线索）形成对照。

### 4.3 `esr_hard_120`（submitted，**supported**）— 唯一真正的 ESR 成功
```
### esr/hard / qid 120  (~15 decisions)
[d...] search, 读 doc, update_state
   claim[c0] oids=[o1] finding="The third focused research question in the study is: 'Why would any graduate wan..."
[d55] submit_answer ok=False err=pending_observations   ← 被 pending 卡一次
[d61] update_state ✓ 绑定
[d67] verify_answer AUDIT status=supported target=supported
[d75] verify_answer AUDIT status=supported target=supported
[d81] submit_answer ok=True → submitted, supported, 正确
```
**读法**：q120 是简单题，32B 能胜任 → ESR 的 state 循环成功地把 evidence 绑进 `c0`、经 verify 达 `supported`、提交正确。**这是 32B 下 ESR 机制的正面范例**，也是唯一一个。

### 4.4 `esr_soft_234`（submitted，错误"Nancy's Brook"）— soft 放行但 verifier 未拦截
```
### esr/soft / qid 234  (~11 decisions)
[d...] search/update, claim[c0] oids 累加
... submit_answer decision=answer → submitted, evidence_status=supported, 但 final_draft="Nancy's Brook"
(gold="Little Lovely")
```
**读法**：q234(证据密集) 32B 凑出一个 supported 答案但**是错的**，soft 放行 + verifier(同为32B)没拦住 → 提交错误。直接印证「auditor 不宜与 policy 同弱模型」。

---

## 5. 完整 Stage1 分析

### 5.1 头号结论：**ESR 状态循环在弱模型(32B)下是净负担，baseline 反超**
- baseline 8/8 提交、3/8 正确、invalid 6、attempts 22。
- 三个 esr 臂都只拿到 1/8 甚至 0/8 正确，invalid 76–113（10× 于 baseline）。
- → **对 32B，"带搜索的 baseline 单次生成"比"多轮 claim/focus 状态机"可靠得多**。

### 5.2 为什么？三个机制性缺陷
1. **工作记忆过载**：ESR 要求 policy 在 thinking 中同时维护多根 claim、focus.need、attempt 历史、pending observation。32B 撑不住 → 无法收敛到答案。
2. **abstain/budget 不保留 best-draft**：32B 的 esr 局在终止时 `final_draft=None`（除 q120）。连"算到哪了"都没留下 → 判分只能靠 submitted，全盘归零。
3. **同弱 auditor 失效**：esr/soft q234 提交错误答案 reached supported，verifier(同 32B) 没拦住。auditor 弱于/等于 policy 时失去把关价值。

### 5.3 q120 例外——state 在简单题上有价值的唯一证据
唯一 submitted+supported 是 q120（易）。说明 state 循环**非全然负面**，其价值取决于 policy 能力是否足以驾驭 evidence→claim→need。

---

## 6. Stage0 vs Stage1 对比——state 设计是否有帮助

| 维度 | Stage0（强 API Lanz） | Stage1（弱模型 32B） |
|---|---|---|
| baseline 臂 | （无 baseline） | **3/8 正确、8/8 提交** ← 最优 |
| esr 最优臂 | soft：7/8 正确、6/8 提交 | esr/off：1/8 正确、1/8 提交 |
| esr 终止时 draft | 常保留正确答案（off 弃权但 draft=gold） | 大多 None（不形成答案） |
| invalid 量级 | 修复后简单题 ≤4 | esr 臂 76–113 |
| 判定 | state 循环"可用但策略未充分利用" | state 循环"明显拖累弱模型" |

**结论（正面回答"state 设计是否有帮助"）**：
- **对强 API（Lanz）**：state 机制名义存在、实质闲置——强模型靠"整段记住+一句 combine"，不需要分治，但也不被拖累（soft 甚至借此拿到 7/8）。
- **对弱模型（32B）**：state 循环是**净负担**——32B 无法在多轮 claim/focus 中维持工作记忆与严格 JSON 契约，导致 draft=None、invalid 上百、正确率远低于自身 baseline。
- **推论**：ESR 状态机的适用域是"强到能驾驭evidence→claim→need 的模型"。对 4B/32B，**带搜索的 baseline 更可靠**。这也提示 4B(Stage2) 大概率同样崩，或更糟。

---

## 7. 产物
- `stage1_runs/REPORT_STAGE1.md`、`metrics.json`、`manifest.json`
- `trajectories/`（32 条，本次编码进 move 包）
- sqlite ledger + summary：`stage1/{arm}/{qid}.{sqlite,summary.json}`