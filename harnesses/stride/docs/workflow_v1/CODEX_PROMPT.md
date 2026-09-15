# Codex GPT-6 execution prompt: Workflow v1 offline validation + bounded live experiment

Work in `homulillew/ESR-Tra` on branch `research/stride-workflow-gap-v1-20260915`. Freeze the exact remote SHA first. Expected base is `9ac875aed9f3d7acd369cb913f0bfc3b768ca8f6`; package version remains `0.1.0a3` for compatibility and workflow identity is `gap-workflow-v1`.

Your task is to review the implementation, run the complete repository-local STRIDE tests, fix deterministic integration bugs within scope, then—if the offline acceptance conditions below pass and the real credentials/index/budget are valid—automatically run the bounded live experiment. Do not stop merely to ask again for approval; this prompt authorizes at most 80 new real HTTP model calls. Do not reset or create a new budget ledger.

## Offline acceptance

Read `docs/workflow_v1/{README,TOOL_CONTRACTS,VALIDATION}.md` and inspect `workflow_contract.py`, `workflow.py`, `goal_read.py`, `engine.py`, `context.py`, `archive.py`, `cli.py`.

Verify at least:
1. all enabled tools have FUNCTION/USE WHEN/AVOID/INPUT/OUTPUT/WORKFLOW;
2. `read({"ref":"dN"})` works, goal/start modes are disjoint, eN replay is exact;
3. goal-read returns exact contiguous frozen text; no-match creates no eN;
4. unseen/withheld search results are never marked delivered; compact reuse can restore a full card;
5. gap state is optional, provenance-scoped and explicitly non-verified; no-op updates do not reset stagnation;
6. bounded repetition cannot loop forever and does not turn a duplicate-query error into a blocker for an otherwise-valid finish;
7. integer answer support, CPU retrieval, provider tool-call round trips and archive replay still pass.

Run the actual tests available in the full repository and report the real count. Scripted tests are not model-quality evidence.

## Live environment

Use the existing EB-GLM-5.2 deployment and expect `glm-5.2`, temperature 0, same read-only CPU SQLite FTS5 index, same corpus/ranking/source rules across arms. Explicitly instantiate `answer_contract="string-integer-v1"` and the arm's `WorkflowConfig`; do not rely on Python API defaults.

Use the existing persistent budget/capture infrastructure. Check current balance before sending. Historic balances are not current authorization. Each attempt, including failed/unknown attempts, is charged before send. Do not change account/model/route or auto-retry infrastructure failures.

## Live plan (max 78 planned, hard cap 80 HTTP calls)

Stage A: q775 and q774, each in two fresh natural arms with max 16 policy calls:
- q775 legacy
- q775 full
- q774 full
- q774 legacy

`legacy = WorkflowConfig.profile("legacy")`; `full = WorkflowConfig.profile("full")`. Keep every non-workflow setting identical. Use `max_actions=200`, `max_backend_calls=120`, `max_output_tokens=4096`, `max_total_output_tokens=48000`, `context_limit=96000` bytes, `response_reserve=4096` bytes, `max_seconds=600`; record all other Config values exactly. One run per arm, no reseeding or rerun-to-success. Normal task failure continues the frozen queue; infrastructure/model-identity/integrity failures stop the queue and leave later slots NOT_RUN.

Stage B: short controls under full, q771 and q778, max 4 policy calls each. These check that the expanded interface does not obstruct direct read/finish and that integer answers still work.

Stage C: after all policy episodes are sealed, run the project's independent judge for submitted answers only, at most 6 judge calls. The judge is not part of the search loop. Preserve full original answers; do not remove unsupported explanation before judging. Also perform an offline evidence audit because answer-label correctness and explanation support are separate.

Policy max 72 + judge max 6 = 78. The remaining two under the hard cap are not retry credits.

## Per-episode analysis

Record full new requests/responses, native IDs/arguments, tool receipts, evidence windows, workflow view/gap versions, usage and timings in a new private run directory. Public commits should contain only code/tests, redacted summaries and hashes—no credentials, production index or unnecessary raw task text.

For each episode answer:
- after useful navigation appears, does the model actually read, or merely say it will read and continue searching?
- when goal-read fires, is the selected exact text relevant and is the subject/relation interpreted correctly?
- when exact repetition appears, when do reuse/recovery/final stages fire and what behavior changes?
- did the model merely paraphrase queries to evade exact-repeat control, or obtain a new relation/evidence?
- did a search loop turn into an irrelevant read/gap loop?
- was update_gap naturally used; if so, did it retain a real rejection/conflict without being treated as verified? If unused, report NOT_EXERCISED.
- did full finish/abstain/stall earlier than legacy, and was that a correctness improvement or merely cheaper failure?
- do q771/q778 remain short and correct?

Report policy calls, declared/executed tools, query count, actual SQL/document backend calls, cache use, known/unknown tokens, end-to-end time, terminal reason, formal judge label and evidence-support audit separately.

Do not call fewer requests, early `stalled_no_submission`, random reads, or less logging an accuracy improvement. Preserve every failure. Do not modify prompts/code after the first live arm based on observed results.

## Deliverable

Commit any scoped deterministic fixes, frozen plan and redacted report to a new successor experiment branch. Give the exact implementation SHA, experiment SHA, test result, real call count, remaining budget and private artifact location. State which mechanisms actually triggered and whether `full` should remain default. Recommend at most one next mechanism to study; do not automatically launch it.
