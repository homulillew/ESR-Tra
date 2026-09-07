# ESR Harness v2 全自动验收实验总指令

## 任务

对 ESR-Tra 的 ESR Harness v2 进行严格前向推理验收，并区分 Harness、Researcher、Auditor 与 Retrieval 的责任。

你现在是这个研究项目的实验负责人、代码工程师和实验分析负责人。

仓库：

`https://github.com/homulillew/ESR-Tra`

当前研究目标不是训练，不是优化 GRPO，也不是追求一个好看的 BC+ 分数。

你的唯一核心目标是：

> **严格验证当前 ESR Harness v2 是否已经足够正确、稳定、可恢复、可解释，使得后续在 4B 上观察到的失败，可以主要归因于模型能力，而不是 harness 本身。**

在完成本任务之前：

- 不进行 SFT。
- 不进行 GRPO / PPO / RL。
- 不修改 ESR credit assignment。
- 不修改 ECHO / verl 训练接入。
- 不通过 case-specific 规则让 bad case “过掉”。
- 不通过降低 verifier 标准、人为放行、连续失败 N 次强制 submit 等方式提升通过率。
- 不使用 gold answer、gold docid 或 test evidence 作为 policy / auditor 的输入。
- 不让 Strong Policy API 使用其自带联网搜索、浏览器、隐藏知识库或额外工具。
- 所有 policy 必须严格通过同一个 ESR Harness 工具接口访问相同固定 corpus。
- 32B、4B、Strong Policy 之间，除了模型 checkpoint / API 本身，其余实验条件尽量完全相同。
- 所有实验结果必须区分“事实”“推断”“尚未确定”。

---

## 0. 总原则

本实验必须把以下四类因素拆开：

```text
Retrieval / Corpus
        ↓
Researcher Policy
        ↓
ESR Harness
        ↓
Auditor / Verifier
        ↓
Final Submit
```

最终任何失败都必须尽可能被归因到以下类别之一：

```text
retrieval_failure
policy_reasoning_failure
auditor_semantic_failure
harness_mechanical_failure
budget_failure
infrastructure_failure
ambiguous_or_label_issue
```

禁止最终留下大量：

```text
unknown
unclear
maybe harness maybe model
```

如果无法归因，必须进一步做：

```text
trajectory replay
frozen audit packet replay
observation inspection
state transition inspection
policy/auditor role swap
```

而不是直接下结论。

---

## 1. 第一件事：冻结和审计当前环境

进入仓库后先执行，不要立即跑大实验。

检查：

```bash
git status
git branch --show-current
git rev-parse HEAD
git log -5 --oneline
```

确认当前代码包含：

```text
src/esr_harness/
docs/harness/DESIGN.md
docs/harness/RUNBOOK.md
docs/harness/VALIDATION.md
tests/harness_v2/
```

Harness v2 的参考提交应接近：

```text
e84f310914f733a75b0d998ad08bc5891b60259a
```

如果远程 main 已经有更新：

- 以服务器实际最新 main 为准。
- 记录实际 commit。
- 不要擅自退回旧版本。

创建独立实验分支：

```bash
git switch -c exp/harness-acceptance-v2
```

如果分支已存在：

```bash
git switch -c exp/harness-acceptance-v2-<timestamp>
```

不要直接在 main 上做实验性改动。

禁止 force push main。

---

## 2. 自动发现服务器现有资源

自动识别服务器已有：

```text
Strong Policy API
32B model endpoint
4B model endpoint
BM25 / ECHO retrieval endpoint
BC+ dataset path
Qwen tokenizer path
model revision
retrieval/index revision
现有 inference scripts
已有 vLLM / SGLang 服务
```

优先从以下位置发现：

```text
README
scripts/
analysis-L/
results/
.env.example
config files
shell scripts
running processes
environment variable names
existing experiment logs
```

不要打印：

```text
API key
Authorization header
secret token
完整凭据
```

不要把 secret 写入：

```text
report
JSON
SQLite
Git commit
shell history helper file
```

实验 manifest 只记录：

```text
endpoint type
endpoint URL without credential
model alias
model revision
tokenizer revision
retrieval/index revision
corpus revision
code commit
```

如果 revision 只是配置声明、无法真正验证：

明确写：

```text
operator_declared
```

不要写成：

```text
verified_model_hash
```

---

## 3. 先执行机械回归测试

执行：

```bash
python -m pip install -e '.[test]'
python -m pytest -q tests/harness_v2
```

随后：

```bash
python -m esr_harness smoke \
  --store /tmp/esr-v2-acceptance-smoke.sqlite

python -m esr_harness replay \
  /tmp/esr-v2-acceptance-smoke.sqlite
```

保存：

```text
Python version
pytest result
test count
smoke terminal
commit hash
```

### 如果测试失败

立即停止后续模型实验。

必须：

1. 建立最小复现。
2. 新增 regression test。
3. 修复代码。
4. 再跑完整 `tests/harness_v2`。
5. 在报告中写清 root cause。
6. commit 到实验分支。

禁止通过：

```text
删除失败测试
skip 测试
降低 assertion
修改 fixture 迎合 bug
```

来“解决”问题。

---

## 4. 建立本轮实验目录

建立：

```text
experiments/harness_acceptance_v2/
├── README.md
├── cases.jsonl
├── run_manifest.json
├── scripts/
│   ├── discover_environment.py
│   ├── build_suite.py
│   ├── run_acceptance.py
│   ├── export_audit_packets.py
│   ├── replay_auditors.py
│   ├── run_researcher_matrix.py
│   ├── classify_failures.py
│   └── analyze.py
└── reports/
    ├── phase_a_harness_acceptance.md
    ├── phase_b_auditor_isolation.md
    ├── phase_c_researcher_isolation.md
    ├── phase_d_4b_target_system.md
    └── FINAL_HARNESS_ACCEPTANCE.md
```

真实 rollout 放到：

```text
runs/harness_acceptance_v2/<run_id>/
```

不要默认 commit：

```text
SQLite
完整网页正文
完整 API response
大体积 trajectory
可能受版权限制的原文
```

Git 中只提交：

```text
实验脚本
case IDs
case categories
aggregate statistics
脱敏的错误摘要
必要 regression test
必要 harness bug fix
最终分析文档
```

---

## 5. 构造 40 题 Harness Acceptance 开发集

不要随机抽 40 题。

从仓库历史 bad case 中构造一个“机制覆盖集”。

优先检索：

```text
analysis-L/
results/local32b100_badcase_unified.md
results/local32b100/
results/
docs/
旧 4B / 32B 分析
```

目标组成：

```text
10 题：历史正常成功 / 相对容易完成
10 题：candidate lock-in / repeated search / repeated open
 8 题：multi-hop / target binding / answer-slot confusion
 5 题：long document / tail evidence / read/re-open
 4 题：unknown / contradicted / missing evidence
 3 题：abstain / ambiguous / refusal 类
---------------------------------------
40 题
```

优先考虑历史中真实存在的典型 qid，例如：

```text
q120
q170
q324
q364
q161
q1201
q199
q18
q591
q580
q624
q1022
q1007
```

但是：

> 必须先从仓库确认这些 qid 确实存在并与对应历史分析一致。

不要仅根据这份提示词生成不存在的题。

如果某类不足：

- 从已经被历史实验分析过的开发题中补。
- 不要为了凑数使用未来计划锁定为 unseen test 的题。

固定 suite seed：

```text
20260907
```

`cases.jsonl` 至少包含：

```json
{
  "qid": "q...",
  "category": "candidate_lockin",
  "historical_source": "results/...",
  "historical_failure_type": "...",
  "notes": "..."
}
```

不要把 gold answer 放进传给 policy 的 case manifest。

---

## 6. 固定公共实验条件

所有 model-role comparison 必须尽可能保持：

```text
same questions
same corpus
same retriever
same retrieval index
same tool schema
same ESR prompt
same ObservationView rules
same search_top_k
same view_chars
same context limit
same action limit
same completion budget
same thinking setting where technically possible
same final evaluator
same stopping semantics
```

建议第一版固定：

```text
max_actions = 64
max_context_tokens = 32768
max_policy_output_tokens = 2048
max_audit_output_tokens = 2048
max_total_completion_tokens = 24000
search_top_k = 5
view_chars = 8000
```

如果服务器有硬限制，可以调整。

但是一旦 Phase A 开始：

> 不允许只给某一个模型扩大预算。

如必须修改公共预算：

- 新建 run_id。
- 所有模型重跑同条件对照。
- 不和旧 run 合并。

---

## 7. Strong Policy API 的严格环境隔离

Strong Policy API 是本轮 Harness Acceptance 的主要 researcher probe。

它必须遵循：

```text
Strong API
    ↓
统一 ESR system prompt
    ↓
只返回 ESR tool action JSON
    ↓
ESR Harness
    ↓
固定 BM25/ECHO corpus
```

禁止 Strong API：

```text
使用自带 web search
调用 browser
访问互联网
使用内部 retrieval plugin
使用 Deep Research
读取 gold
读取 gold_docid
读取 test evidence labels
直接看到 corpus 全文
访问仓库以外的答案资料
```

如果 Strong API 无法完全关闭这些额外能力：

记录：

```json
{
  "strong_policy_environment_isolated": false
}
```

并降低 Phase A 证据等级。

**不能使用一个拥有额外信息源的 Strong API 来证明 Harness 正确。**

---

## 8. Phase A：Strong Policy × 32B Auditor

这是整个实验最重要的阶段。

配置：

```text
Policy     = Strong Policy API
Auditor    = 32B
Harness    = ESR Harness v2
Audit mode = hard
Retriever  = fixed BM25/ECHO
Cases      = 40
```

32B Auditor 必须 fresh context。

禁止 auditor 接收：

```text
policy hidden reasoning
policy complete conversation history
old verifier rationale
gold answer
gold docs
retrieval snippets that were never opened
```

Auditor 只能看到：

```text
Question
Target
Candidate Answer
Claims
Referenced actual ObservationViews
```

---

## 9. Phase A 每题必须生成详细诊断记录

每题至少输出：

```json
{
  "qid": "",
  "category": "",
  "run_id": "",
  "policy_model": "",
  "auditor_model": "",
  "terminal_reason": "",
  "final_answer": "",
  "answer_correct": null,
  "correct_candidate_ever_formed": null,
  "correct_final_draft_before_audit": null,
  "required_evidence_in_corpus": null,
  "required_evidence_retrieved": null,
  "required_evidence_actually_visible": null,
  "required_evidence_cited": null,
  "target_binding_correct": null,
  "claims_complete": null,
  "claims_grounded": null,
  "audit_verdict_correct": null,
  "audit_false_reject": null,
  "audit_false_accept": null,
  "harness_false_block": null,
  "harness_illegal_accept": null,
  "duplicate_query_count": 0,
  "duplicate_view_count": 0,
  "new_observed_chars": 0,
  "candidate_changes": 0,
  "claim_repairs": 0,
  "action_count": 0,
  "policy_completion_tokens": 0,
  "audit_completion_tokens": 0,
  "root_cause": "",
  "confidence": "high|medium|low",
  "notes": ""
}
```

不能让模型自己根据 gold 自动填所有诊断。

至少这些字段需要通过：

```text
trajectory inspection
actual ObservationView inspection
independent final judge
必要时人工/强模型盲审
```

来确认。

---

## 10. Phase A 的关键定义

### 10.1 Harness-caused failure

定义：

```text
Policy 已经形成正确候选
AND
必要证据已经实际展示
AND
状态引用基本正确
BUT
由于 state/version/view/audit-cache/tool-protocol/gate 等机械问题失败
```

例如：

```text
正确证据被 harness 丢掉
verifier 看到旧 view
no-op 导致错误 state
正确 audit 被 stale cache 覆盖
提交工具错误阻断
schema 与 runtime 不一致
```

这些归类为：

```text
harness_mechanical_failure
```

### 10.2 Auditor semantic failure

如果：

```text
候选正确
证据充分
audit packet 正确
harness 没有机械错误
```

但 auditor 判断：

```text
unknown
contradicted
wrong target interpretation
```

这是：

```text
auditor_semantic_failure
```

不要归为 harness。

反过来，如果错误答案在证据不足或反证明确的情况下被 auditor supported，也归类为 `auditor_semantic_failure`，除非是 harness 错误地修改了 auditor 输出。

### 10.3 Policy failure

如果 policy：

```text
没有形成正确候选
没有搜索关键条件
看到了反证仍不换候选
把 intermediate entity 当 final target
反复围绕错误候选查询
```

而 harness 正常提供了信息：

归类：

```text
policy_reasoning_failure
```

### 10.4 Retrieval failure

必须区分四层：

```text
Evidence exists in corpus
Evidence returned by search
Evidence opened / exposed
Evidence correctly cited
```

如果正确证据根本不在 corpus，或者在合理搜索下固定 retriever 完全召不出来，归类 retrieval/corpus 问题。

不要把 retrieval miss 全部归给 researcher。

---

## 11. Phase A 验收标准

本阶段不以最终 accuracy 作为唯一标准。

### Harness mechanical failure

目标：

```text
0
```

最多允许极少数、且必须能解释并修复。

### 正确候选 + 充分证据条件下的 Harness false-block rate

目标：接近 0。

开发阶段建议：

```text
< 5%
```

如果超过 5%，继续修 harness，不进入后续训练。

### Audit protocol failure

目标：

```text
< 1%
```

包括：

```text
JSON/schema invalid
非法 quote
缺 claim
重复 claim
context 不完整
```

如果 protocol failure 较多，先修 auditor interface/prompt/protocol，不归因模型能力。

### 无信息循环

统计：

```text
same query
duplicate observation
zero new chars
same candidate
same claims
same audit
```

重点看 Strong Policy 是否仍被系统引导进机械循环。

如果大量循环来自 harness interaction，继续修。

---

## 12. Phase A 遇到 bug 时怎么做

如果发现真正的 harness mechanical bug：

不要继续跑剩余题。

流程：

```text
1. 停止当前 batch
2. 保存触发轨迹
3. 新增最小 regression test
4. 修 harness
5. 跑全部 tests/harness_v2
6. 重跑触发 case
7. 新 commit
8. 重新开始 Phase A
```

不要混用 bug 修复前后的题目统计。

每一次协议变化：

```text
new code commit
new run_id
```

Phase A 最终报告只使用同一个稳定 commit 下的完整结果。

---

## 13. Phase A 报告

生成：

```text
experiments/harness_acceptance_v2/reports/phase_a_harness_acceptance.md
```

必须包含：

```text
environment
commit
model identities
retriever/index
40题构成
per-category results
terminal distribution
harness mechanical failures
auditor failures
policy failures
retrieval failures
budget failures
loops
cost
case-by-case root cause
```

并明确回答：

> **Strong Policy + 32B Auditor 是否足以证明当前 Harness 已基本调通？**

结论只能为：

```text
PASS
CONDITIONAL PASS
FAIL
```

并解释标准。

---

## 14. Phase B：冻结 Audit Packet，隔离 Auditor 能力

只有 Phase A 机械 harness 基本通过后才进行。

从 Phase A 保存每个有代表性的审核节点。

构建：

```text
frozen_audit_packets.jsonl
```

每个 packet 只包含：

```json
{
  "packet_id": "",
  "qid": "",
  "question": "",
  "target": "",
  "candidate_answer": "",
  "claims": [],
  "observations": [],
  "source_trajectory": "",
  "state_fingerprint": ""
}
```

不要包含：

```text
gold answer
gold label
old auditor verdict
policy chain-of-thought
future evidence
```

---

## 15. Phase B Packet 类型

至少构建约 200 个 packet。

建议：

```text
50：答案正确 + 证据充分
50：答案正确 + 证据不足
50：答案错误 / target binding 错
50：明确反证 / refusal / abstention
```

来自：

```text
Strong Policy trajectories
历史 bad-case 合法 packet
必要的合成 protocol packet
```

合成 packet 必须与真实协议一致。

---

## 16. Phase B Auditor 对照

对完全相同 packet，分别运行：

```text
4B Auditor
32B Auditor
Strong Auditor（如果有且能严格隔离）
```

使用：

```text
same audit prompt
same schema
same context budget
same output budget
temperature 0 或尽量 deterministic
```

不要让不同 auditor 使用不同证据。

统计：

```text
supported precision
supported recall
false accept
false reject
unknown vs contradicted confusion
target binding error
coverage error
protocol invalid rate
quote invalid rate
repeat stability
```

对于最重要的 50 个 packet，进行独立盲审。

如果人工不可用，可使用一个更强模型做独立 label assistant，但：

- 不把模型大小当 truth。
- 对争议 packet 标记 ambiguous。
- 必须保存争议。

---

## 17. Phase B 的核心问题

回答：

> **4B Auditor 到底是不是独立瓶颈？**

重点比较：

```text
32B Auditor vs 4B Auditor
```

例如如果：

```text
32B false reject = 5%
4B false reject = 30%
```

且协议完全一样，那么后续应该考虑 audit SFT。

如果 4B 和 32B 都在同类型 packet 上失败，则不能简单说“4B 太弱”。

要检查：

```text
audit task definition
claim decomposition
evidence visibility
problem ambiguity
```

---

## 18. Phase C：Researcher Scaling Isolation

保持 Auditor 固定为 32B。

分别运行：

```text
Strong Policy + 32B Auditor
32B Policy     + 32B Auditor
4B Policy      + 32B Auditor
```

必须使用：

```text
same 40 cases
same harness
same retrieval
same budget
same prompts
same auditor
```

如果 Strong API 无法严格隔离环境，仍可以跑，但在报告中把其结果标记为 diagnostic upper reference，而非严格公平对照。

---

## 19. Phase C 重点指标

不只看 answer accuracy。

统计：

```text
correct candidate ever formed
correct final draft
required evidence actually seen
target binding accuracy
candidate revision after contradiction
successful claim repair
search diversity
duplicate view rate
actions per solved question
budget exhausted rate
final answer accuracy
```

重点分解：

```text
Strong → 32B 的下降
32B → 4B 的下降
```

---

## 20. Phase C 的归因逻辑

如果：

```text
StrongP + 32V  >> 4P + 32V
```

说明 researcher 能力明显是瓶颈。

进一步看：

```text
retrieval success
target binding
candidate revision
evidence extraction
termination
```

定位应该 SFT 哪种行为。

如果：

```text
4P + 32V ≈ StrongP + 32V
```

但：

```text
4P + 4V << 4P + 32V
```

说明 researcher 已经够强，主要瓶颈是 auditor。

此时不要给 researcher 做大量 SFT。

---

## 21. Phase D：目标系统 4B × 4B

只有 A/B/C 做完后进入。

配置：

```text
Policy  = 4B
Auditor = 4B
Harness = same accepted v2
```

先在同 40 题跑。

如果行为正常，再扩：

```text
100题固定开发评估
```

不要直接全量 830。

此阶段回答：

> 在 harness 已经被强模型验收后，4B × 4B 的主要失败到底是什么？

生成分布：

```text
policy failure %
auditor failure %
retrieval failure %
budget failure %
remaining harness failure %
```

---

## 22. 最关键的角色矩阵

最终至少形成：

| Policy | Auditor | 含义 |
|---|---|---|
| Strong | 32B | Harness acceptance upper probe |
| Strong | 4B | Auditor isolation |
| 32B | 32B | Local strong baseline |
| 4B | 32B | 4B researcher isolation |
| 4B | 4B | Target system |

如果成本允许，可以增加：

```text
32B Policy + 4B Auditor
```

得到更完整角色矩阵。

---

## 23. 禁止混淆 Final Judge 和 Online Auditor

Online Auditor：

```text
帮助 researcher 判断当前 evidence 是否充分
```

Final Judge：

```text
离线评估最终 answer 是否正确
```

两者必须分开。

Final judge 不得影响 policy trajectory。

不得使用旧的 substring smoke judge 作为正式 benchmark judge。

如果当前正式 BC+ judge 不确定：

- 固定一个独立评测版本。
- 记录 judge revision。
- 对数值、单位、别名、日期等争议结果复核。
- 不为了某一个模型改单题判分规则。

---

## 24. 特别审查数值与 target-binding case

对于类似：

```text
percentage
rounding
before / after
third person
fewer than
years before
multi-hop target
```

不能只看：

```text
gold string 是否出现
```

必须分开判断：

```text
source numbers correct?
operator / denominator correct?
rounding rule explicit?
intermediate entity correct?
final relation target correct?
```

如果 gold 或历史分析自身有争议：

归类：

```text
ambiguous_or_label_issue
```

不要为了匹配 gold 教模型错误规则。

---

## 25. 每题轨迹自动生成“责任时间线”

为每个重要失败 case 自动生成简洁时间线。

示例：

```text
qid: qXXX

A1 search(...)
  new evidence: yes

A2 open(...)
  visible relevant evidence: yes

A3 update_state(...)
  candidate: X
  target binding: wrong

A4 verify
  auditor: supported
  expected: contradicted
  => auditor semantic failure

A5 submit
  final wrong

root cause:
auditor_semantic_failure

harness mechanical bug:
no
```

或者：

```text
A7 open(...)
  policy saw Observation o5

A8 update_state cites o5

A9 verify
  auditor packet unexpectedly contains old o2 instead of o5
  => harness mechanical failure
```

只有第二种才算 harness bug。

---

## 26. 自动化分析脚本必须生成这些汇总表

### 总体 failure attribution

```text
retrieval_failure
policy_reasoning_failure
auditor_semantic_failure
harness_mechanical_failure
budget_failure
infrastructure_failure
ambiguous_or_label_issue
```

### 按 bad-case category

```text
candidate_lockin
target_binding
long_document
missing_evidence
contradiction
abstention
easy
```

### 按角色组合

```text
Strong+32B
Strong+4B
32B+32B
4B+32B
4B+4B
```

### 成本

```text
policy calls
audit calls
search calls
open calls
input tokens
output tokens
actions
wall time
cost per solved question
```

---

## 27. Harness Acceptance 最终判据

只有满足以下条件，才允许报告：

```text
HARNESS ACCEPTED FOR 4B TRAINING EXPERIMENTS
```

### 条件 1：机械完整性

```text
harness_mechanical_failure ≈ 0
```

如果不是 0，必须全部解释。

### 条件 2：强研究者可以正常使用 harness

Strong Policy + 32B 不应大量出现：

```text
正确答案已形成
充分证据已见
但 harness 自己阻止成功
```

### 条件 3：循环主要不是由协议 bug 造成

重复 query/open 可以是模型弱点，但不能是：

```text
state 没更新
audit 看错 view
缓存错
预算逃逸
```

### 条件 4：Auditor 错误能独立测量

4B / 32B auditor 的错误可以通过 frozen packets 分离。

### 条件 5：所有关键 observation 可重放

对于失败 case：

```text
read-only replay
```

必须能恢复：

```text
state
views
audits
actions
terminal
```

且不重新调用 retriever。

---

## 28. 如果 Harness Acceptance FAIL

禁止开始训练。

输出：

```text
FAIL
```

然后只修改真正的 mechanical bug。

修复原则：

```text
prefer invariant
over case-specific rule

prefer explicit state
over hidden controller behavior

prefer typed error
over semantic fallback

prefer replayable evidence
over re-retrieval

prefer deterministic aggregation
over another LLM judgement
```

修复后重新完整执行 Phase A，而不是只重跑失败题后拼接统计。

---

## 29. 如果 Harness Acceptance PASS

不要立即开始 RL。

先根据 B/C/D 决定下一步训练目标。

### 情况 A

```text
4B Policy + 32B Auditor 明显差
4B Auditor 还可以
```

下一步优先：

```text
Researcher repair/search SFT
```

数据重点：

```text
candidate revision
query reformulation
target binding
evidence extraction
stop decision
```

### 情况 B

```text
4B Policy + 32B Auditor 好
4B Policy + 4B Auditor 明显差
```

下一步优先：

```text
Audit SFT
```

数据重点：

```text
supported
unknown
contradicted
missing bridge
wrong target
wrong relation
refusal vs answer
```

### 情况 C

```text
4B researcher 和 auditor 都弱
```

做小规模：

```text
protocol + repair + audit SFT
```

不要直接大 SFT。

### 情况 D

```text
4B × 4B 已经有足够成功率和 mixed reward groups
```

必须保留：

```text
No-SFT + standard GRPO
```

作为正式训练对照。

---

## 30. 暂时不要做的事情

这一轮禁止：

```text
修改 ESR-GRPO reward
设计新的 dense reward
添加 gap reward
reward new document
reward verify pass
引入 reward model
引入新的 controller
引入多 agent debate
引入 knowledge graph
引入训练时 32B 在线 verifier
大量生成 teacher SFT 数据
```

这些都必须等 Harness Acceptance 后再讨论。

---

## 31. 对现有 Harness v2 的态度

不要假设当前 Harness v2 已经正确。

虽然仓库已有自动化测试，但：

> 单元测试通过只证明机械 fixture 通过，不证明真实 4B / 32B / Strong API 环境中没有系统问题。

你必须主动寻找：

```text
actual tokenizer mismatch
provider response mismatch
tool parser mismatch
context template mismatch
retriever payload mismatch
offset edge cases
resume behavior
usage accounting mismatch
audit packet overflow
Qwen thinking wrapper
tool action JSON formatting
```

任何真实部署接口问题都必须新增 regression test 后修复。

---

## 32. 不允许为了“强模型成功”修改 Harness

Strong Policy 本轮是探针，不是优化目标。

如果 Strong Policy 输出某个不符合 schema 的动作：

不要直接扩大 schema 来迎合它。

先判断：

```text
动作是否真正必要？
还是模型没有遵守协议？
```

同理，如果 Strong Policy 想直接 submit without state，不要为了提高成功率开放绕过路径。

---

## 33. Git 工作规则

每一个真正 harness bug fix：

```text
一个清晰 commit
```

例如：

```text
fix(harness): persist exact view used by audit
test(harness): cover stale audit after candidate change
fix(protocol): reject duplicate claim ids
```

实验脚本：

```text
experiment(harness): add acceptance role matrix
```

分析：

```text
analysis(harness): add phase A acceptance report
```

不要 commit：

```text
API keys
raw large traces
model weights
full corpus
temporary cache
```

如果测试全部完成并且修改稳定，推送实验分支。

不要自动 merge main。

---

## 34. 最终报告结构

最终生成：

```text
experiments/harness_acceptance_v2/reports/FINAL_HARNESS_ACCEPTANCE.md
```

必须包含以下章节。

### Executive conclusion

只能明确回答：

```text
PASS
CONDITIONAL PASS
FAIL
```

以及：

> 当前是否已经有足够证据认为后续 4B 的主要失败来自模型能力，而不是 harness？

### Environment

```text
code commit
dataset revision
retrieval/index
Strong Policy identity
32B identity
4B identity
tokenizer
budgets
prompts
```

### Phase A — Harness acceptance

```text
Strong + 32B
40 cases
failure attribution
mechanical failure rate
false block rate
loops
cost
```

### Phase B — Auditor isolation

```text
4B vs 32B
frozen audit packets
false accept
false reject
target binding
coverage
protocol validity
```

### Phase C — Researcher isolation

```text
Strong vs 32B vs 4B
all with 32B auditor
```

### Phase D — 4B target system

```text
4B + 4B
main failure modes
```

### Remaining Harness Risks

明确列出尚未证明的东西。

不要写：

```text
Harness is perfect.
```

即使 PASS，也应写：

```text
Harness mechanical failures were not observed / were below acceptance threshold on this suite.
```

### Training recommendation

最后才给：

```text
No SFT
Researcher SFT
Audit SFT
Mixed lightweight SFT
```

以及为什么。

不要在没有 B/C/D 证据前直接推荐。

---

## 35. 强制生成一个最终决策矩阵

最终报告必须有：

| Strong+32V | 4P+32V | 4P+4V | 结论 |
|---|---|---|---|
| 高 | 高 | 高 | Harness 和 4B 基本可用，可直接测 RL |
| 高 | 高 | 低 | 4B Auditor 是主瓶颈 |
| 高 | 低 | 低 | 4B Researcher 是主瓶颈 |
| 低 | - | - | Harness / retrieval / 32B audit 尚未验收 |

同时结合：

```text
Strong+4V
32P+32V
```

做更细归因。

---

## 36. 最终最重要的科学问题

本轮实验不是要证明：

```text
ESR 比 baseline 高多少点
```

本轮真正要回答：

> **如果给 ESR Harness 一个足够强的 researcher 和合理强的 auditor，它是否能够稳定地承载“搜索 → 观察 → 状态 → 缺口 → 修复 → 审核 → 提交”的完整闭环，而不会自行制造、隐藏或放大错误？**

只有这个答案基本为 YES，才进入第二个问题：

> **在相同 Harness 下，4B 相比强模型究竟弱在哪些具体行为？**

之后才有资格进入：

> **SFT / GRPO / ESR-GRPO 应该训练什么？**

---

## 37. 执行优先级

严格按顺序：

```text
P0  回归测试
↓
P1  真实服务单题 smoke
↓
P2  Strong Policy + 32B，40题 Harness Acceptance
↓
P3  修复所有 mechanical bug，必要时重新 Phase A
↓
P4  Frozen Audit Packet：4B vs 32B
↓
P5  Strong / 32B / 4B Policy + 固定 32B Auditor
↓
P6  4B + 4B
↓
P7  Final attribution report
↓
STOP
```

到这里停止。

不要自行进入 SFT 或 RL。

---

## 38. 完成条件

只有以下文件存在并完成，才算任务结束：

```text
experiments/harness_acceptance_v2/cases.jsonl
experiments/harness_acceptance_v2/run_manifest.json

experiments/harness_acceptance_v2/reports/
    phase_a_harness_acceptance.md
    phase_b_auditor_isolation.md
    phase_c_researcher_isolation.md
    phase_d_4b_target_system.md
    FINAL_HARNESS_ACCEPTANCE.md
```

以及：

```text
所有新增 harness bug 都有 regression tests
tests/harness_v2 全部通过
代码修改已 commit
实验分支已 push
```

如果由于 API、GPU、endpoint、数据缺失而无法完成某阶段：

不要假装完成。

在 FINAL 中明确：

```text
BLOCKED
reason
completed phases
missing resources
what remains to run
```

同时尽可能完成所有不依赖缺失资源的分析与代码工作。

---

## 39. 最后一句执行要求

现在开始执行。

不要先给我泛泛的实验建议。

直接：

```text
检查仓库
检查服务
跑测试
构造 acceptance suite
开始 Phase A
发现 bug 就修复并补测试
完成角色隔离实验
生成最终归因报告
推送实验分支
```

所有结论必须由真实轨迹、冻结 packet、实际 ObservationView 和可复现统计支持。

**在明确证明 Harness 已基本验收之前，不开始任何 SFT 或 RL。**
