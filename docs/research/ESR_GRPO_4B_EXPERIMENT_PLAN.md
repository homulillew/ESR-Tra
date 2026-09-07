# ESR-GRPO 4B Experiment Plan

> Status: **PROPOSED / NOT EXECUTED**.
>
> This Markdown document converts the earlier YAML experiment plan into a model-readable research protocol. Parameter values are starting points, not proven optima.
>
> **Hard prerequisite:** do not execute SFT/RL until the forward harness has passed [`docs/harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md`](../harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md).

---

# 1. Objective

The experiment program should answer three questions in order:

1. **Harness:** can the search → evidence → state → audit → repair → submit loop operate without mechanical ambiguity?
2. **4B capability:** after fixing the harness, is the primary bottleneck the researcher, the auditor, or both?
3. **Training:** given a stable 4B forward system, does ESR provenance improve learning relative to standard outcome GRPO?

Never answer question 3 by changing question 1 and question 2 at the same time.

---

# 2. Fixed research target

Primary model family/size:

```text
Qwen3.5-4B or the repository's pinned 4B target checkpoint
```

Before running, pin and record:

```text
model revision
tokenizer revision
chat template / thinking mode
code commit
corpus snapshot
retrieval index revision
final judge revision
```

Any unverified deployment declaration should be recorded as `operator_declared`, not as a verified model hash.

---

# 3. Reproducibility contract

Every episode should be uniquely identified by:

```text
(run_id, query_id, experimental_arm, seed)
```

A run manifest should record at least:

```text
code_commit
model_revision
tokenizer_revision
system_prompt_hash
auditor_prompt_hash
tool_schema_hash
corpus_snapshot
retriever_index_revision
judge_revision
harness_contract_version
thinking_mode
context_budget
generation_budget
action_budget
seed
```

Persist for each rollout:

```text
raw model responses
sampled policy token IDs        # required before RL integration
actual prompt token IDs         # required before RL integration
old policy logprobs             # required before RL integration
parsed and executed action
controller intervention/error type
exact ObservationView text/hash
state snapshot/fingerprint
policy token mask
provenance mask
final draft before audit
final output
terminal status
infrastructure errors
token/latency ledger
```

Harness v2 already records the forward evidence/state trace, but **it is not yet a complete RL sampler format**. Exact token/logprob/span integration remains separate work.

---

# 4. Data split policy

## Preferred split strategy

Use:

```text
train: independently constructed and verified synthetic/development tasks
dev: historically inspected BC+ questions + synthetic dev tasks
test: never-tuned locked BC+ questions
```

Do not treat repeatedly debugged bad cases as untouched evaluation.

## Alternative internal BC+ split

If training directly on BC+ questions is necessary:

- explicitly label the setting as a custom BC+ internal split;
- derive the split after auditing all historically inspected qids;
- lock at least a substantial never-tuned test subset before training;
- do not compare a train-on-BC+ result to full-benchmark zero-shot numbers as though they were the same protocol.

## Contamination checks

At minimum inspect:

```text
near-duplicate question
answer entity overlap
bridge entity overlap
evidence document/cluster overlap
relation-chain overlap
template overlap
```

The executing search policy/teacher must not receive gold answer or gold docid before searching.

---

# 5. Forward phase gate

The canonical forward experiment is now maintained separately:

[`docs/harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md`](../harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md)

Its order is:

```text
P0 mechanical regression
P1 real-service smoke
P2 Strong Policy + 32B Auditor acceptance
P3 fix any mechanical bugs and rerun the full phase
P4 frozen audit packets: 4B vs 32B
P5 researcher scaling: Strong / 32B / 4B with 32B auditor
P6 4B + 4B
P7 final attribution report
STOP
```

Training begins only after an explicit harness acceptance decision.

---

# 6. Common forward inference budget

The following are **pilot starting values** and should be identical across model-role comparisons unless a new experiment ID is created for all arms:

```text
retriever: fixed existing BM25/ECHO first
search_top_k: 5
max_context_tokens: 32768
max_actor_output_tokens_per_call: 2048
max_auditor_output_tokens_per_call: 2048
max_total_completion_tokens_per_episode: 24000
max_model_actions: 64
actor_sampling_temperature: ~0.6–0.7
auditor_temperature: 0 or as deterministic as the endpoint allows
```

Policy and auditor tokens must both count toward compute/cost reporting.

Unknown/invalid actions count toward the decision budget.

Infrastructure retry must be bounded and must not create a new semantic “gap.”

---

# 7. Forward metrics

## Primary benchmark metric

```text
all-question final answer accuracy
```

No submission / abstention counts as incorrect unless the benchmark protocol explicitly says otherwise.

## Supporting metrics

Record:

```text
grounded answer accuracy
final-draft accuracy before audit
submission coverage
conditional submission precision
false-blocked-correct-answer rate
false-accepted-wrong-answer rate
required evidence recall at:
    search
    opened
    actually visible
    cited
stable requirement repair rate
candidate change after contradiction
duplicate view rate
zero-novelty loop rate
policy generated tokens
auditor generated tokens
prefill/input tokens
model calls
wall-clock latency
cost per correct answer
```

Statistics should be paired by `query_id`. Multiple seeds on the same question are repeated measurements, not independent new questions.

---

# 8. SFT decision gate

SFT is **not theoretically mandatory**.

Before SFT, perform a no-SFT pilot on a fixed development/synthetic set.

Suggested pilot:

```text
~64 development/synthetic questions
8 rollouts per question
```

Measure:

```text
valid action rate
pass@8
mixed-reward GRPO group rate
candidate revision rate
auditor protocol validity
```

If the base 4B already gives enough legal successful trajectories and mixed-reward groups, keep `No-SFT + standard GRPO` as a major experimental arm.

---

# 9. Proposed first SFT batch, if required

A reasonable first-pass scale is about **5k filtered records**, not a huge dataset.

Suggested composition:

| Type | Approx. count | Purpose |
|---|---:|---|
| end-to-end successful search trajectories | 2,500 | legal search/evidence/state/finish behavior |
| student failure-prefix repair windows | 1,500 | candidate revision, missing evidence repair, loop recovery |
| frozen audit packets | 1,000 | supported / unknown / contradicted / target binding |

These counts are initial engineering estimates, not optima.

## 9.1 End-to-end trajectory construction

Preferred process:

```text
real source spans
→ construct 1–4 hop necessary relation chain
→ generate indirect question + near-miss distractors
→ independently verify uniqueness/retrievability
→ teacher searches under the same harness WITHOUT gold in its execution prompt
→ post-hoc check answer correctness and evidence sufficiency
```

The task generator may know the answer while constructing the task. The executing search teacher should not.

## 9.2 Repair-window construction

Use real student failures:

```text
legal student prefix
→ frozen visible state
→ teacher corrects next action(s) under the same tool environment
→ actual tool calls execute
→ candidate/requirement repair
→ finish
```

Do not insert future evidence that the student/teacher had not yet observed.

Do not train the failed student suffix as though it were a positive demonstration.

## 9.3 Audit examples

Labels:

```text
supported
unknown
contradicted
```

Include target/coverage errors.

Useful paired examples:

```text
same correct answer, remove unique bridge evidence → unknown
same evidence, replace answer with contradicted entity → contradicted
entity name appears but wrong relation position → not supported
refusal text in answer slot → target failure
```

---

# 10. SFT experiment arms

Compare at least:

```text
S0 base 4B
S1 protocol-only SFT
S2 protocol + repair + audit SFT
```

Use the same Harness v2 development evaluation.

Choose checkpoints based on held-out behavior, not lowest training loss alone.

Initial full-finetuning learning-rate starting point from the earlier plan:

```text
~1e-5
~0.5–1 epoch
```

Actual optimization must be adjusted for hardware, batch size and parameterization. If LoRA is used, all scientific comparison arms should use the same parameterization unless parameterization itself is the experiment.

---

# 11. RL baseline

After the harness and optional SFT initialization are fixed, establish standard outcome GRPO first.

Reward:

```text
R_i = 1  if independent final answer judge says correct
R_i = 0  otherwise
```

Do not initially add rewards for:

```text
new document count
query diversity
gap reduction
auditor pass
number of claims
number of citations
```

Keep the online auditor and the independent final outcome judge separate.

---

# 12. GRPO sampling signal check

A group-relative method needs variation inside groups.

For group size `G=8`, record the **empirical** fraction of groups containing both successes and failures.

Do not rely only on theoretical independence assumptions because rollouts from the same prompt are correlated.

If groups are overwhelmingly all-fail:

- SFT/curriculum or easier verified training tasks may be needed;
- fancy provenance masks will not rescue zero outcome signal.

If groups are overwhelmingly all-success:

- the task curriculum may be too easy for learning credit.

---

# 13. RL experiment matrix

Use the **same initialization, harness, dataset, sampler and outcome reward**.

## R0 — Standard signed outcome GRPO

This is the baseline.

All actual policy-generated tokens receive the normal rollout/group advantage according to the trainer’s standard loss contract.

## R1 — Historical positive-only ESR

Reproduce the original ESR idea after provenance correctness is fixed.

Conceptually:

- only successful/eligible trajectories receive ESR positive credit;
- credit is concentrated on provenance-selected steps/tokens.

This must remain an ablation, not the assumed final algorithm.

## R2 — Bounded residual provenance weighting

Recommended first simplified ESR update.

Let:

```text
A_i = ordinary group-normalized outcome advantage
m_it ∈ {0,1} = trusted provenance mask for policy token t
```

Define:

```text
raw_weight_it = 1 + λ * m_it
weight_it = raw_weight_it / mean_over_policy_tokens(raw_weight_i)
A_tilde_it = A_i * weight_it
```

Start with:

```text
λ = 1.0
```

Optional ablation:

```text
λ = 0.5
λ = 0.0   # exact ordinary-GRPO weighting baseline
```

Failure rollouts initially remain ordinary GRPO until reliable local labels exist. Do not pretend that provenance identifies which actions inside every failure are correct.

Important status:

> This is a heuristic biased credit modulation mechanism, not an unbiased equivalence to standard GRPO.

## R3 — Same-density random mask control

Create a random token/action mask with the same approximate density as R2 provenance.

Purpose:

> determine whether a gain comes from semantic provenance or merely from changing gradient density/magnitude.

---

# 14. Initial provenance definition

Use only high-confidence trace edges initially.

Recommended:

```text
final cited supporting ObservationView
→ the open/read action that exposed it
→ the related search action

stable requirement repair that is still present in final successful state

final candidate/answer update
```

Do not reward “creating a gap.”

Do not select every action between gap creation and gap disappearance.

Do not assume that a traced action was uniquely causally necessary.

---

# 15. Auditor role during the first RL credit ablation

To prevent the training target from moving while testing provenance credit:

**Preferred first comparison:**

```text
researcher actor: 4B being trained
auditor: frozen post-SFT (or accepted) 4B snapshot
```

This preserves a 4B-scale system while preventing simultaneous actor+auditor drift during the first credit-assignment study.

Report both roles’ compute.

Later ablation:

```text
shared 4B weights + fresh auditor context
```

If shared weights are trained, the auditor-generated segments must be explicitly identified. Tool observations must never silently become policy-loss tokens.

The independent final outcome judge remains separate in all cases.

---

# 16. Initial RL optimization starting points

These are proposal values only.

```text
group_size: 8
actor_learning_rate_start: ~1e-6
PPO/GRPO update epochs per rollout batch: 1
pilot global prompts per update: 8
later, if stable: 16–32 prompts/update
```

Keep optimizer, KL handling and clipping identical across R0/R1/R2/R3 unless those quantities are explicitly under study.

Suggested sequence:

```text
10–20 updates: smoke / gradient-signal check
50 updates: first R0 vs R2 comparison
then add equal-budget R1 and R3 controls
only after a positive/understood signal: 100–300 updates
```

At `8 prompts/update × G=8 × 50 updates`, each arm samples about `3,200` logical rollouts. Treat this only as a scale estimate; actual episode length and service throughput determine cost.

---

# 17. RL mask and failure semantics

Mandatory invariants before claiming any result:

## Policy-token masks

- include only tokens actually generated by the trainable policy;
- tool observations receive zero policy loss;
- controller-forced outputs receive zero policy loss;
- padding must not change mask meaning;
- one logical rollout may contain multiple model segments but remains one GRPO group member.

## Sampling correctness

Preserve:

```text
sampled token IDs
actual sampling context
old policy logprobs
segment→rollout identity
```

Do not reconstruct production training spans using a character tokenizer or decode→re-encode approximation.

## Failure classification

Normal valid environment failure:

```text
wrong answer
no answer
budget exhausted under declared task budget
```

should follow the declared outcome reward, usually zero.

Infrastructure failure:

```text
service outage
corrupt response outside policy semantics
irrecoverable runtime exception
```

should be excluded or resampled according to a predeclared rule and reported separately.

Do not silently remove most negative trajectories from a group and then call the result ordinary GRPO.

---

# 18. RL monitoring

Every training run should report:

```text
all-question dev accuracy
mixed-reward group rate
credited-token fraction
provenance-mask density
provenance support precision on audited sample
KL
entropy
clip statistics
episode length
candidate-repair rate
auditor false accept / false reject
policy generated tokens
auditor generated tokens
prefill tokens
wall-clock / GPU cost
```

Comparison should be equalized by meaningful sampling/compute budgets, not merely by optimizer step count.

---

# 19. Decision table after role isolation

Use the forward acceptance results to choose training.

| Strong+32B | 4B+32B | 4B+4B | Interpretation | Training priority |
|---|---|---|---|---|
| high | high | high | harness and 4B forward system basically usable | no-SFT GRPO baseline first |
| high | high | low | 4B auditor bottleneck | audit SFT, then compare GRPO |
| high | low | low | 4B researcher bottleneck | repair/search SFT or curriculum |
| low | — | — | harness/retrieval/32B audit not accepted | **do not train** |

Use Strong+4B and 32B+32B to refine the attribution.

---

# 20. Training release gate

Do not start the main training campaign unless all are true:

- Harness acceptance mechanical tests pass.
- A final judge has been frozen and audited.
- No gold/oracle information enters policy/auditor observations.
- Observation/state replay is stable.
- No unexplained action/token provenance mismatch remains.
- The value of hard vs soft audit has been measured rather than assumed.
- Held-out questions have not been tuned on.
- Reported results use all-question accuracy and compute/cost, not only conditional submission precision.

For an ESR credit claim, additionally require:

- benefit over standard GRPO;
- benefit over same-density random-mask control;
- provenance implementation passes token/segment alignment tests.

---

# 21. Claims that this plan explicitly does not make

Do not state that:

- the proposed harness experiment has already been run;
- these thresholds/hyperparameters are optimal;
- literature scores are directly comparable to this repository setting;
- provenance is exact causal credit;
- 32B is a ground-truth verifier;
- SFT is mandatory;
- any historical ESR score is already a clean measure of the current Harness v2 design.

---

# 22. Recommended project sequence from here

```text
A. Complete Harness Acceptance
   Strong Policy + 32B
   frozen auditor packets
   researcher role scaling
   4B + 4B

B. Decide SFT
   no-SFT pilot
   researcher vs auditor vs mixed lightweight SFT only if evidence supports it

C. Establish RL baseline
   standard outcome GRPO

D. ESR credit study
   R1 historical positive-only
   R2 bounded residual provenance
   R3 same-density random mask

E. Only after clean ablation
   consider richer failure-local credit (TRACE/STAMP-like)
   consider retriever changes
   consider curriculum expansion
```

Do not change retriever, reward, state representation, gate policy and credit assignment simultaneously.

---

# 23. Source-of-truth links inside this repository

Read in this order:

1. [`docs/harness/DESIGN.md`](../harness/DESIGN.md)
2. [`docs/harness/VALIDATION.md`](../harness/VALIDATION.md)
3. [`docs/harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md`](../harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md)
4. [`docs/research/ESR_GRPO_4B_RESEARCH_REVIEW.md`](ESR_GRPO_4B_RESEARCH_REVIEW.md)
5. this document

The experiment policy is:

> **Forward attribution first, training second, credit-assignment novelty last.**
