# Failure audit and falsifiable evaluation

## Scope

Reviewed all model decision rounds and trajectory events for q775/q774 in both arms of harnesses/stride/artifacts/20260915-workflow-v1-live, with targeted inspection of actual request evidence windows. Used q771/q778 as short controls and read stride_search/workflow.py. Did not inspect the other eight questions or private gold answers, call a model, or change product code. Historical runs generate hypotheses; they are not current experimental controls. The findings concern evidence support and behavior, not knowledge of the correct development answers.

## Findings

1. q775-full: conflict precedes compression. R2 treats the 2002 Man Booker renaming as award creation and notices that the 2019 winners were not published the preceding year. R3 explicitly restates the year conflict and switches to 2015. R4 calls Kingston and Akure strong evidence without satisfying the required same-city relation. R16 acknowledges the award's 1969 origin and dismisses the question's incompatible condition as misdirection. Candidate commitment overrides hard constraints.
2. q775-full: a definite source-subject mismatch. R5 reads d86, creating e2 [0,3000). Its title is King Yellowman, its credit includes photography by Marlon James, and its subject is Winston Foster/Yellowman. The delivered window does not say that Marlon James was born in Kingston. R6-15 repeat that assertion; R16 explicitly attributes the nonexistent sentence to e2. The valid d38/e1 statement that Obioma was born in Akure cannot supply his required childhood-city relation. Reference validity is not semantic support.
3. q775-full: varying actions mask repeated reasoning. R6-15 largely repeat the same paragraph while alternating rephrased searches, read, find, and new windows. Compression occurs at R4/6/8/9/12. It may preserve fixation, but the candidate error exists earlier; these observations cannot establish compression as the cause.
4. q775-legacy: two fixed query batches persist from R5 through R16. There are 90 query_execution events, 30 backend requests, and no raw evidence windows. Compression starts at R6 and continues each round. Saying reconsider does not produce a discriminating action; caching saves backend requests without saving model decisions.
5. q774-full: no transition from navigation to reading. It has 27 query executions and zero evidence windows. R1-7 rephrase broad relational descriptions; R7-11 repeat the same batch; R12 abstains. Compression starts at R6. No established candidate means this is not yet an observed hard-constraint contradiction. The observable failure is repeated searching without obtaining primary text.
6. q774-legacy: one supported relation sustains an unverified candidate. R2 picks Jessica/Richard Harmon. R6 reads d1 [4344,5844), whose e2 genuinely supports siblings playing unrelated characters in The 100. Marriage count, surviving child, and height remain unestablished while R7-16 repeat the candidate. Missing evidence does not itself refute the candidate. Compression occurs only at R14, after fixation has begun.
7. Short controls: q771 and q778 finish in four rounds without compression, reading three and one windows respectively. q778 e1 directly contains the mother's age of 21 and the article's 2021 publication date. These are useful noninterference checks, not an estimate of overall success.

None of the four difficult trajectories has a gap_update event. workflow.py resets recovery after new navigation, a new raw window, or a previously unseen query. Its semantic_progress field explicitly says not_measured. Changed observation identity and improved understanding of a question are distinct.

## Minimal optional mechanism

This is an independent fallback proposal, not the implemented first-stage prompt-only intervention. Do not attribute its expected effects to constraint-review-v1.

Use at most two bounded evidence-review interruptions per episode, reserving the second for finish. Trigger after three consecutive search rounds without a new raw window, after two highly similar normalized assistant paragraphs (initial development threshold 0.9), or at finish. Similarity triggers review; it does not establish truth.

One short same-model review sees the original question, current candidate and proposed action, recent tool results, and cited raw windows with source offsets. It outputs one discriminating required relation, supported/contradicted/unresolved status, an exact source phrase and reference when available, one executable next tool action, and which outcomes would support, reject, or leave the candidate unresolved. With no candidate, it may choose to read a relevant received navigation result.

The harness validates reference visibility, quoted substring presence, and action parameters, then executes that action and exposes both the review and actual result. Substring presence is not entailment; the judgment remains explicitly fallible. Finish review can use the remaining review allowance for a discriminating action; after exhaustion the normal termination rules apply, with uncertainty or abstention available.

Prevent empty bookkeeping: each review must execute an action. Rewording a gap, changing a label/query, or reading an arbitrary new window does not reset review allowance. Review a candidate/relation once unless a new raw sentence provides a different relevant value. Log triggers, cost, action, observed text, and actual changes to candidate judgment. Completing a record is never a progress metric. Possible falsifiers include persistent subject errors, irrelevant new reads, and increased abstention without improved correctness.

## Development, freeze, and independent execution

New allowance: 1000 model attempts inclusive of policy, auxiliary review, judge, failures, and retries. Count CPU search requests and latency separately. Match model identity, CPU corpus fingerprint, retrieval configuration, context/token ceilings, and total calls per episode. Auxiliary calls consume the treatment episode's existing cap.

Suggested allocation: development 240, frozen replication 720, exceptional retry/adjudication reserve 40. Development uses only the two difficult questions and two controls: four questions x two arms x two executions x (up to 14 policy/auxiliary attempts + one judge) = 240. Select one mechanism and fixed parameters. Require observable action changes and corrected relation/source judgments; short controls should preserve their supported answers. If development shows no mechanism effect, do not inspect the other eight to rescue it.

Freeze code, prompt hashes, thresholds, total call/token ceilings, two preselected seeds and a nonzero temperature where supported, ordering, and evaluation rules. Replication uses twelve questions x two arms x two executions x (14 policy/auxiliary + one judge) = 720. Interleave paired arms. Report the four previously inspected questions separately from the eight uninspected questions. Fresh executions on twelve questions are independent runs, not twelve unseen questions. A 16-call episode cap requires recalculating this allocation.

The primary measure is the paired difference in correctness averaged over two runs per question, using questions as the statistical unit. Report intervals, each seed's difference, inspected/uninspected strata, supported correctness, erroneous citations, abstention, attempts, tokens, and CPU cost. Blind judges to arm labels and order; never expose gold to policy. Do not treat 24 runs as 24 independent questions.

Suggested preregistered success standard: positive overall paired difference with a question-level 95% interval strictly above zero, positive uninspected-eight mean, positive effect in both execution seeds, no increase in erroneous citation rate, and no budget breach. A small sample may be inconclusive; do not lower the threshold after results. Reduced loops without correctness improvement supports an efficiency claim only. A single temperature-zero win cannot establish general superiority.

Secondary mechanism measures: raw reading within two rounds after a trigger, corrected subject attribution, preserved contradictions, repeated candidate/relation rounds, auxiliary cost, and added calls on short controls. These explain effects and do not replace correctness. Proving a causal compression effect would require a separate fixed-prefix randomized compression experiment; the present audit does not do so.

## Local boundary tests completed

Synthetic test_decision_protocol.py: 12 passed in 6.87 seconds using the designated virtual environment. Checks system-only wire differences including FINAL, unchanged schemas/budgets/source scope, string/integer submission, rejection of unreceived or navigation refs, read-only archive replay, instruction identity hash, and CLI defaults.

Synthetic test_decision_stage.py: 5 passed in 4.79 seconds using the designated virtual environment. Checks preserved old request rows, 1000-call renewal and idempotence after spending, role limits/sealing, unknown attempt charging, old budget rejection after a new epoch, timeout capture, both protocols through the formal local CLI search/read/finish/export/seal path, file hashes, equal schemas/identities, and blocking gold access before policy seal. No GLM calls or production data were used. These tests establish boundaries, not model research quality.
