# Results — constraint-state-v1

## Offline (complete)

| Metric | Value |
|--------|-------|
| Offline tests | 19 passed, 0 failed |
| Full suite regression | 574 passed (555 existing + 19 new) |
| Duration | ~178s full suite; ~3s new tests |
| Profile | `constraint-state-v1` |
| NL view | `natural-language-local-v1` |

### Three data dependencies — fixed

1. **Original question → current local task.** The `Frame.answer_target`
   drives the auto-created first task. The original question text and its hash
   are stable across all evidence updates (tested). An evidence update never
   mutates the frame; only an audited `amend()` does.

2. **Delivered observations → sourced, scoped, correctable judgments.** Every
   judgment must cite a delivered `source_ref` (undelivered →
   `unreceived_reference`) and an exact `quote` (not in window →
   `quote_not_found`). Judgments are scoped to a task and correctable via
   `CorrectionPatch` (a wrong contradiction can be corrected to supported;
   the candidate is recoverable, not permanently banned).

3. **Updated judgments → available research options → real tool execution.**
   `reduce()` updates routing from the judgment. `choose(query)` reaches the
   real search backend via `harness._dispatch("search", ...)`.
   `choose(read_hit_dN)` emits a real native read. The full execution test
   confirms `navigation_history` is non-empty — the search backend actually
   ran.

### What remains model judgment

- Whether a passage *supports* or *contradicts* a fact (semantic).
- Subject identity disambiguation.
- Which entry to choose next.
- Whether the answer is ready to submit.

The program enforces structural validity and deterministic routing
consequences; it does not verify semantic correctness
(`semantic_status: "not_automatically_verified"`).

## Online (not yet run)

Online validation (Stages A/B/C, ≤168 new model HTTP requests) has not been
executed. It proceeds only after offline acceptance passes, which it now does.

### Planned

- **Stage A** (≤72): near-end mechanism — 3 versions × 4 slots × ≤6 requests.
  Verify Interpret/Choose alternation and routing transitions on real model
  output.
- **Stage B** (≤88): one natural pairing under the real CPU index.
- **Stage C** (≤8): judge whether submitted answers and cited evidence
  satisfy the constraint-state contract.

### Budget

- Total cap: 168 new model HTTP requests.
- All requests including format repairs count.
- No empty ledger created to reset; historical 357/844 balances are not current.
- No key/account/model switch on failure.

## Cost

Offline: 0 model HTTP requests (all tests use `ScriptedModel` fixtures).
Online: not yet incurred; capped at 168.

## Failures / not-run items

- Online Stages A/B/C: not run.
- Real model semantic judgment: not verified offline (by design).
- Multi-task research episodes with task switching: left to online validation.

## Remote branch

- Branch: `research/stride-local-state-nl-20260916T104031Z`
- Base commit: `0f34e9006b38be1e7119d934f39b151581f2dd18`
- Push status: pending (will be pushed with the frozen implementation commit)
