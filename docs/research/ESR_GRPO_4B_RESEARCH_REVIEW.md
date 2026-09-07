# ESR-GRPO 4B Research Review

> Status: research review / design record. This document is model-readable Markdown converted from the earlier research-analysis artifact. It is **not** a record of completed training.
>
> Current precedence: the forward harness has since been reorganized as Harness v2. Before any SFT/RL experiment, first follow [`docs/harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md`](../harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md) and require a PASS or an explicitly justified CONDITIONAL PASS.

## 0. Scope

Repository: `homulillew/ESR-Tra`

Historical review baseline: `040710279e591162d793883cd64f8b1ae424a759`

Primary research setting:

- benchmark/data environment: BC+ / BrowseComp-Plus-style deep search;
- target model size: **4B**;
- objective: improve long-horizon search and evidence-grounded repair without turning the system into a large collection of case-specific rules;
- desired algorithmic direction: ESR-GRPO, where the same traceable evidence state can support both inference-time repair and training-time credit assignment.

This review separates:

1. repository facts observed in design/code/reports;
2. interpretations of historical experiments;
3. proposed next experiments;
4. items already addressed by Harness v2.

It does **not** claim that the proposed SFT/RL experiments have been executed.

---

# 1. Executive conclusion

The strongest part of ESR is not “call verify one more time.” The useful idea is:

> **A traceable evidence state should serve both reasoning and later credit assignment.**

The historical implementation mixed several layers:

- answer state;
- free-form gaps;
- evidence cataloging;
- verifier decisions;
- tool-protocol recovery;
- loop-breaking heuristics;
- experimental drivers with slightly different semantics.

This made bad-case fixes accumulate into a hybrid system where it became difficult to tell whether a gain came from:

- better retrieval;
- more context;
- a stronger verifier;
- a more permissive gate;
- a special-case recovery rule;
- or a genuinely better search policy.

The recommended simplification is:

```text
immutable actually-visible evidence
        ↓
stable question requirements / target binding
        ↓
answer candidate
        ↓
fresh atomic audit
        ↓
repair / candidate change / finish
```

For training, provenance should initially be treated as a **bounded credit modulation signal**, not as exact causal credit and not as a reason to zero every unselected token.

---

# 2. What the historical repository actually established

## 2.1 Design and implementation were not identical

The V1 design described richer structure:

- Claim;
- Claim–Evidence support / contradiction;
- Question → Claims coverage;
- RawEvidence → Claim grounding;
- VerifyView;
- provenance-oriented credit routing.

The historical runtime state was much flatter: answer, supporting evidence, findings and free-form gaps. Therefore the old experiments should be interpreted as testing an **answer-level stateful self-verification agent**, not the complete claim-level design.

Implication:

- old failures do not fully falsify the richer V1 idea;
- old successes also do not prove that claim-level ESR-GRPO was implemented end to end.

## 2.2 Historical experiment reading

The repository contained several qualitatively different experiments.

| Experiment | Historical reported behavior | Safe interpretation |
|---|---|---|
| 4B / ~100 questions | ESR submitted relatively few answers; conditional submitted precision looked better than overall accuracy | ESR changed termination behavior; this did not establish an end-to-end accuracy gain |
| scripted/oracle-like verifier diagnosis | selected positive paths could be made to submit | useful integration diagnosis, not an unbiased natural-search benchmark |
| 32B policy + 32B verifier / ~100 questions | ESR did not outperform the baseline and used far more rounds | simply scaling both roles did not make the historical harness automatically successful |

Do not use “submitted precision” as the primary system metric. For BC+ style tasks, abstain/no-submit still counts as failure for answer accuracy unless the benchmark explicitly says otherwise.

## 2.3 Why the old 12-case diagnosis was not a clean verifier-only experiment

The historical diagnosis included privileged elements such as preselected answer-containing document IDs or explicit gold-conditioned state updates. That is useful for checking whether a success path exists, but it cannot establish:

> “100% of failures are caused by the 4B verifier.”

A clean diagnosis must freeze the actual search state and replay the same packet across different auditors.

## 2.4 Evaluation contract was a first-class risk

The legacy `ExactMatchJudge` behaved like normalized substring containment rather than a benchmark-grade exact semantic answer judge.

This can create both false positives and false negatives. Examples of the general failure mode:

- gold `17` may match an answer containing `117`;
- a sentence such as “the answer is not Alice” may contain the string `Alice`;
- unit/date/alias variants may be mishandled.

Therefore:

> Historical accuracy numbers must be read under their historical judge version. A final benchmark result needs a separately frozen and audited evaluator.

Harness v2 intentionally does not use the legacy smoke judge as the final evaluator.

---

# 3. Bad-case taxonomy

The bad cases are most useful when reduced to mechanisms instead of qid-specific rules.

## 3.1 Candidate anchoring and information stagnation

Typical pattern:

```text
wrong candidate
  → query contains wrong candidate
  → retrieval finds documents related to that candidate
  → state keeps the same candidate
  → auditor repeats an unresolved judgement
  → another query about the same candidate
```

Historical examples included repeated queries and duplicate opens with little genuine new evidence.

The lesson is **not** “reward query diversity.” That can be gamed.

The useful signal is:

- did the model see new raw evidence spans?
- did it establish a new necessary relation?
- did counterevidence cause a candidate change?

Harness v2 therefore tracks actual observation novelty rather than resetting stagnation merely because the action name changed.

## 3.2 Target-binding and answer-slot errors

Several failures were not “entity absent from page” failures. The model found an entity on the chain but returned the wrong relation position.

Typical forms:

- person mentioned in the target paper vs. third person in a different paper;
- winner in year `Y` vs. winner two years before `Y`;
- intermediate entity in a multi-hop chain vs. the requested final entity;
- “fewer than 10 seasons” vs. a show whose title matches but whose relation contradicts the condition.

The state therefore needs an explicit target and stable requirements. “The answer string appears in evidence” is not sufficient.

## 3.3 Refusal / “not found” confused with a factual answer

A verifier can truthfully support the proposition:

> “The evidence does not tell me the answer.”

while that text still fails to answer the user’s entity question.

Hence:

- `answer` and `abstain` must be distinct terminal types;
- target correctness must be audited separately from factual support;
- a refusal must not become `supported` merely because the evidence supports the refusal statement.

Harness v2 now encodes typed abstention and target audit.

## 3.4 Correct candidate but insufficient evidence

Three concepts must remain separate:

```text
answer_correct

evidence_sufficient

auditor_verdict
```

A candidate can equal the gold answer while the current evidence still fails to prove all requested conditions. Conversely, a verifier can reject a genuinely sufficient packet.

This distinction is essential for deciding whether to train the researcher or the auditor.

## 3.5 Arithmetic / label disputes

A historical analysis around `28498 / 43487 × 100` illustrates another risk: a disagreement with the stored gold is not automatically an arithmetic error.

The computed percentage is about `65.53%`, which rounds to `66%` under ordinary integer rounding. If a benchmark expects `65%`, the task definition, source numbers, denominator or rounding convention must be rechecked.

Do not turn disputed labels into SFT examples until the source semantics are resolved.

## 3.6 Useful success pattern to preserve

A genuinely useful successful pattern is:

```text
initial candidate
→ audit identifies concrete missing conditions
→ search specifically for missing condition A
→ update stable requirement A
→ search specifically for missing condition B
→ update stable requirement B
→ audit supported
→ submit
```

This “repair trajectory” is more valuable for later 4B data construction than examples where a teacher knows the gold first and merely backfills evidence.

---

# 4. Historical implementation risks and current Harness v2 status

The earlier analysis identified the following implementation-level risks.

| ID | Historical issue | Why it mattered | Harness v2 status |
|---|---|---|---|
| C01 | exposed `read_evidence(offset)` did not match runtime signature | legal model actions could fail | **addressed**: single protocol schema/runtime contract |
| C02 | verifier JSON retry could lose original Q/A/evidence context | format error became a different semantic judgement | **addressed**: bounded retry preserves full packet |
| C03 | conflicting `supported + gaps` could be silently normalized | adapter could override model contradiction | **addressed**: no free overall supported flag; aggregate from atomic fields |
| C04 | research and verify could share session history | self-confirmation/context contamination | **addressed**: auditor uses fresh context |
| C05 | old evidence could crowd out newer useful evidence | new information became invisible | **addressed**: immutable views + pending observation protection |
| C06 | character budget did not equal true chat-template token budget | hidden truncation / overflow risk | **substantially addressed**: live CLI requires actual tokenizer; real deployment still needs endpoint/template verification |
| C07 | substring smoke judge used for historical evaluation | inaccurate benchmark score | **still external to harness**: final benchmark judge must be frozen separately |

Additional historical risks now handled by Harness v2 include:

- no-op update refreshing verification;
- free-text gap paraphrase counted as repair;
- verifier reconstructing a different chunk than the policy saw;
- duplicate opens resetting crude action-name stagnation counters;
- infrastructure failures being treated as semantic gaps;
- baseline exposing dead tools;
- replay mutating legacy stores;
- action/protocol errors escaping decision accounting.

These changes are mechanical improvements. They do **not** prove that a 4B auditor understands every BC+ relation correctly. That is the purpose of the acceptance experiment.

---

# 5. Simplified ESR inference concept

The recommended inference design is intentionally small.

## 5.1 Immutable observations

Keep two layers:

```text
DocumentSnapshot
  immutable raw document snapshot

ObservationView
  exactly what the model saw
  docid
  raw character/token span identity
  actual rendered text
  view hash
  producing search/open action
```

The verifier may only audit stored actual observations. It must not rerun retrieval and silently substitute another chunk.

## 5.2 Stable question requirements

Represent only the relations needed to answer the question:

```text
ResearchState
  target
  candidate answer
  requirements[
    claim_id
    requirement
    observation_ids
  ]
```

Avoid two overlapping free-form graphs such as “Claim graph + Gap graph” when a gap can simply be:

> a required claim whose status is not `supported`.

Requirement identity should remain stable across rewording. Real decomposition changes must be explicit revisions.

## 5.3 Fresh atomic audit

Audit:

- target correctness;
- requirement coverage;
- each requirement individually.

Statuses:

```text
supported
unknown
contradicted
```

The harness should derive overall status deterministically.

`unknown` is missing evidence, not falsehood.

`contradicted` requires actual conflict evidence.

## 5.4 Hard vs soft audit is an experiment, not a theological choice

The system should compare:

- **hard**: only supported state can submit;
- **soft**: audit remains advisory but the final output preserves the real evidence label;
- **off**: state exists but audit is not called.

The benchmark judge remains separate from the online auditor in all cases.

---

# 6. Related work and the useful comparison points

This project should not claim that provenance-based credit or verify→repair is unique. The contribution should be narrower and testable.

## ECHO

Paper: `https://arxiv.org/abs/2606.31650`

Useful idea:

- source-turn traceability;
- selective positive credit;
- context/memory reconstruction.

Closest comparison question for ESR:

> Does requirement/evidence repair provenance provide better training signal than selecting final source turns alone?

## TRACE

Paper: `https://arxiv.org/abs/2607.13988`

Useful idea:

- turn-level credit using a frozen model’s change in answer likelihood;
- demonstrates that pure RL without mandatory cold-start SFT is a meaningful baseline.

Implication:

> Do not remove the no-SFT GRPO baseline merely because SFT seems intuitively useful.

## STAMP

Paper: `https://arxiv.org/abs/2607.11172`

Useful idea:

- provenance-guided bounded modulation of advantage;
- preserve the outcome objective rather than replacing it with a large collection of hand rewards.

## AREX

Paper: `https://arxiv.org/abs/2607.21461`

Useful idea:

- requirement-wise verification;
- gap-driven search;
- repair-oriented training data.

Do not import its entire multi-stage architecture before the simpler ESR mechanism has been isolated.

## ABSeeker

Paper: `https://arxiv.org/abs/2608.05102`

Useful idea:

- answer-backtracked clues and step credit at 4B scale.

It is useful as a data/credit comparison, not as evidence that its reported benchmark scores transfer directly to BC+.

---

# 7. Research hypothesis after simplification

The strongest publishable hypothesis is not:

> “ESR adds verification.”

A better hypothesis is:

> **Under the same 4B model, retriever and compute budget, a compact state grounded in actually-visible evidence improves candidate repair and termination; provenance derived from the same state then improves credit assignment relative to ordinary outcome GRPO and simpler source-turn routing.**

This naturally decomposes into two independent questions:

1. Does the inference state improve forward search behavior?
2. Given a validated forward state, does its provenance improve RL optimization?

Do not test both at once.

---

# 8. Required order of work

Current repository work should follow this order:

```text
1. Harness mechanical tests
2. Strong-policy + 32B harness acceptance
3. Frozen audit packet: 4B vs 32B auditor
4. Researcher scaling: Strong / 32B / 4B with fixed 32B auditor
5. 4B + 4B target system
6. Decide whether SFT is necessary
7. Establish standard GRPO baseline
8. Compare ESR credit variants
```

The detailed automated instruction for steps 1–5 is:

[`docs/harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md`](../harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md)

---

# 9. SFT recommendation after harness acceptance

SFT is recommended only if role-isolation experiments show a behavior deficit that is hard to learn from sparse terminal reward.

## 9.1 Keep a no-SFT pilot

Before SFT, sample multiple 4B rollouts per development task and measure:

- valid action rate;
- pass@N;
- fraction of GRPO groups containing both successes and failures;
- candidate revision rate;
- audit protocol validity.

If the base 4B already generates enough mixed-reward groups and legal repair trajectories, retain `No-SFT + GRPO` as a serious main baseline.

## 9.2 If researcher SFT is needed

Prefer real student-failure repair windows:

```text
student legal failure prefix
→ teacher continues under exactly the same visible state
→ real search/open actions
→ candidate change or requirement repair
→ correct finish
```

Do not give the teacher unseen future evidence in its prompt.

Useful behaviors:

- counterevidence-driven candidate revision;
- query reformulation after zero novelty;
- target binding;
- missing-bridge search;
- evidence citation;
- stop decision.

## 9.3 If audit SFT is needed

Use frozen packets labeled as:

- supported;
- unknown;
- contradicted;
- wrong target binding;
- missing bridge;
- answer-vs-refusal mismatch.

Paired negatives are especially valuable:

- delete the only bridge evidence → `unknown`;
- replace candidate with explicitly contradicted entity → `contradicted`;
- name appears but relation is wrong → not `supported`.

---

# 10. RL recommendation after harness acceptance

## 10.1 Keep standard outcome GRPO as the baseline

Start from an independent benchmark correctness reward:

```text
R = 1 if final answer is correct
R = 0 otherwise
```

Do not initially add rewards for:

- number of new documents;
- fewer gaps;
- verification pass;
- query diversity;
- document novelty.

Those can be gamed and would make attribution harder.

## 10.2 Keep the old positive-only ESR as an ablation

The historical idea roughly routed positive group advantage only to final provenance-selected tokens/actions.

Potential benefit:

- avoid punishing useful actions inside failed trajectories.

Potential cost:

- successful but verifier-rejected trajectories get no ESR signal;
- failure trajectories contribute little/no localized learning;
- unselected but useful reasoning can be zeroed;
- sparse outcome × sparse audit × sparse mask may destroy learning signal.

Therefore it is an ablation, not the assumed winner.

## 10.3 Recommended first new credit variant: bounded residual provenance weighting

Let `A_i` be ordinary group-relative outcome advantage and `m_it ∈ {0,1}` indicate trusted provenance-selected policy tokens.

A simple candidate is:

```text
raw_weight_it = 1 + λ * m_it
weight_it = raw_weight_it / mean_policy_tokens(raw_weight_i)
A_tilde_it = A_i * weight_it
```

Initial comparison:

```text
λ = 0   → ordinary GRPO
λ = 0.5
λ = 1.0
```

Properties:

- ordinary GRPO remains the exact `λ=0` baseline;
- unselected policy tokens still retain learning signal;
- selected supporting-chain tokens receive bounded extra emphasis;
- average per-rollout scale is normalized.

This is a **heuristic biased credit modulation**, not an unbiased estimator of causal credit.

## 10.4 Essential controls

Compare from the same initialization:

```text
R0 standard outcome GRPO
R1 historical positive-only ESR
R2 bounded residual provenance weighting
R3 same-density random provenance mask
```

The random-mask control is important: otherwise an apparent gain may come merely from changing gradient density or magnitude rather than semantic provenance.

---

# 11. Provenance should initially include only reliable chains

Start with high-precision provenance:

```text
final cited supporting ObservationView
→ open/read action that exposed it
→ related search action

stable requirement repair that survives to the successful final state

final candidate update / answer action
```

Do not initially reward every event between “gap created” and “gap disappeared.”

A provenance path is a traceability heuristic, not proof that the action was uniquely causally necessary.

---

# 12. Data and split discipline

BC+ questions repeatedly inspected during harness development should be treated as development/regression data, not untouched test data.

Preferred strategy:

1. keep previously analyzed BC+ questions for harness regression;
2. synthesize training tasks from separate public corpus material when possible;
3. freeze a never-tuned held-out BC+ subset before SFT/RL;
4. report any custom split explicitly.

Contamination checks should include:

- near-duplicate question;
- answer entity overlap;
- bridge entity overlap;
- evidence-document cluster overlap;
- relation-chain/template overlap.

A teacher may know the answer while **constructing** a synthetic task. But a teacher generating a natural search demonstration should not receive the gold answer/docid before it searches.

---

# 13. What must be logged for later RL correctness

Before training integration, a real rollout must preserve:

- exact sampled policy token IDs;
- exact prompt token IDs;
- old-policy logprobs;
- actual executed tool call;
- controller intervention type;
- exact ObservationView text/hash;
- state fingerprint;
- policy loss mask;
- provenance mask;
- logical rollout identity across segments;
- terminal classification;
- infrastructure error classification;
- policy and auditor token usage.

Synthetic character spans or decode→re-encode approximations are acceptable for behavior debugging but not for production GRPO credit.

---

# 14. Practical go/no-go rule

Do **not** start training merely because Harness v2 unit tests pass.

Start training only after the acceptance suite shows:

- no meaningful recurring harness mechanical failures;
- correct candidate + sufficient evidence is rarely/never mechanically blocked;
- role swaps can isolate auditor vs researcher errors;
- actual observations can be replayed exactly;
- budget/accounting semantics are stable;
- final evaluation is independent of online audit.

Then choose training based on evidence:

| Observation | Next step |
|---|---|
| `4B policy + 32B auditor` poor, auditor replay okay | researcher repair/search SFT or direct RL curriculum |
| `4B policy + 32B auditor` good, `4B + 4B` poor | audit SFT |
| both researcher and auditor weak | small mixed protocol/repair/audit SFT |
| `4B + 4B` already has enough success/mixed groups | preserve no-SFT GRPO baseline and move quickly to RL credit ablation |

---

# 15. Current repository pointers

Use these as the current model-readable source of truth:

- Harness design: [`docs/harness/DESIGN.md`](../harness/DESIGN.md)
- Harness runbook: [`docs/harness/RUNBOOK.md`](../harness/RUNBOOK.md)
- Harness validation status: [`docs/harness/VALIDATION.md`](../harness/VALIDATION.md)
- Full automated acceptance prompt: [`docs/harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md`](../harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md)
- This research review: `docs/research/ESR_GRPO_4B_RESEARCH_REVIEW.md`
- Proposed experiment/training plan: [`docs/research/ESR_GRPO_4B_EXPERIMENT_PLAN.md`](ESR_GRPO_4B_EXPERIMENT_PLAN.md)

The central discipline remains:

> **First make the forward experiment attributable. Then train.**
