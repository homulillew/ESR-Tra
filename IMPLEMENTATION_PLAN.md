# Implementation Plan: constraint-state-v1 (natural-language local-task ReAct)

Base: `0f34e90` on branch `research/stride-autonomous-search-20260915T093818Z`.
New branch: `research/stride-local-state-nl-20260916T104031Z`.
Design docs `STRIDE_Constraint_State_V1_Formal_Design_2026-09-16.md` and the
Binding-Scope Addendum were **not found** in the worktree or attachments; this
plan implements the full contract stated in the task prompt and records that
the external design files were not read.

## Architecture decision: new decision_protocol profile

The existing engine already routes everything through `decision_protocol`:
- `decision_protocol.PROTOCOLS` supplies per-protocol system instruction text.
- `decision_protocol.identity()` returns a versioned identity blob.
- A state object (e.g. `SearchPivotState`) with `project()/commit()/complete()`
  is instantiated in `Harness.__init__` when the profile is selected.
- `context.build()` calls the state object's `project()` to inject a scope
  block + optional trigger into the model-visible control state, and adapts
  tools/history as needed.
- `engine._step()` calls `commit()` then `complete()` around each model round.

`constraint-state-v1` plugs into exactly this machinery. No second competing
state machine. The legacy `baseline` profile and all old artifacts are
untouched.

## Reuse / replace map

| Concern | Reuse | New / replaced by constraint-state-v1 |
|---|---|---|
| tool dispatch (search/read/find/recall/notes/finish) | `engine._dispatch` unchanged | new `interpret`+`choose` task contracts routed through the same dispatch boundary |
| CPU index, OR/BM25 corpus | `cpu_index.SQLiteFTS5`, `EchoRetriever` | unchanged; no reranker/embedding |
| goal-aware page read | `goal_read.select_window` | reused for read tickets produced by Choose |
| archive / replay / integrity | `Archive` | unchanged; new events appended, old SQLite stays readable |
| answer contract | `string-integer-v1` + `legacy` | unchanged |
| budget metering | `ByteCounter`, `usage_of`, `Config` limits | unchanged; Interpret/Choose/repair all counted |
| workflow gap state | NOT stacked on top | replaced by `LocalState` (one gap carrier) |
| review_memory / relation_review / once_prose / search_pivot | NOT stacked | independent profiles; constraint-state-v1 does not enable them |
| context.build | extended with a constraint-state branch | adds natural-language task view + option list |

## Three internal responsibilities (one file: local_state.py)

1. **Frame** — original question, answer target fragment, descriptive roles,
   current expansion/ambiguity. Immutable by ordinary evidence; amended only
   via explicit `task_amendment` carrying old/new interpretation + affected
   tasks.
2. **Evaluation** — per-task judgments: source ref, statement, subject/role
   binding, support/contradict/unknown, scope, revision. Three-state; backend
   keeps full history, online projects active task. Navigation is a lead, not a
   source_statement; question_given vs source_statement vs hypothesis kept
   distinct.
3. **Task** — one natural-language current question, original-question clause,
   candidate nature, entry points, attempt history. Single gap carrier; task
   rename does not reset attempts.

## Two model tasks (Interpret / Choose)

Driven by a phase alternator inside `LocalState`:
- **Interpret**: called when a relevant read/recall result was just delivered
  or an old interpretation needs correction. Small output: value/statement,
  subject correspondence, support-phrase location or short quote, unknown
  reason. Exits include `task_mismatch`, `identity_unclear`, `not_mentioned`,
  `propose_amendment`. Program pre-fills source/role/version.
- **Choose**: called to pick the next research entry. Input: NL goal, current
  task, active judgments + exact evidence, available unread entries, recent
  attempts, budget, a few options. Selecting an existing option needs only
  `choice_id`; a new query fills `query`; final answer fills `answer`/`refs`;
  a new direction is a short NL note. Must have "no suitable option / new
  direction / task wrong / re-review" exits.

Both are bounded JSON schemas (not arbitrary Patch / universal oneOf). One
format-repair per response, ≤2 per episode, all budgeted. Semantic errors are
not format errors.

## Program-closed loop & hard boundaries

Order: Choose picks entry → validate local deps → program executes →
observation delivered → Interpret produces judgment → program commits state →
build next options → new Choose. First task + first query may share one
request when both depend only on the original question. New-evidence
interpretation and the next query are NOT pre-generated in one old response.

Deterministic read/replay needs no extra parameter request (controller_planned
label). Choose selecting `read_hit_7` → program emits `read`; never silently
rewrites an illegal `search` into `read`.

Contradiction affects local interpretation + dependents, not a name ban:
q774 role-pair refuted ≠ actor has no other real-world relative pair; an
independent height check may still be reasonable. Old tasks voided only when
their actual dependency fails.

## Offline acceptance (tests must hit real dispatch, not just labels)

Cover: NL target not replaced by equations; original question not rewritten by
ordinary update; source actually delivered; quote/sentence location accurate;
subject-unknown and not-mentioned not mis-contradicted; local refutation not
expanded; same-source correction recoverable; independent tasks retained;
dependency-stale tickets voided before dispatch; identity/source conflict;
integer/string; old archive compatible; new CLI entry + existing provider
loopback. One full execution test: text → fixture model output → state update
→ stale task voided / independent retained → new task reaches the underlying
tool.

## Online (frozen plan, bounded)

A. up to 3 candidate versions × 4 slots × ≤6 = 72. L1 q774 real prefix, L2 q775
real prefix, L3 synthetic "material lacks target relation", L4 synthetic
"local pair fails but independent task + correctable extraction".
B. one natural pairing, ≤88 policy: q774/q775=16 each, q771/q778=6 each,
interleaved. baseline = existing reproducible `decision_protocol=baseline`.
C. ≤8 independent judge on submitted only.

Hard cap 168 new model HTTP. Persisted ledger queried + atomically debited
before each send. No key/account/model switch on failure.

## Deliverables

DESIGN.md, TOOL_CONTRACTS.md, CAMPAIGN_PLAN.json, VALIDATION.md, RESULTS.md,
IMPLEMENTATION_PLAN/RUN_STATE. Code + tests committed frozen before online;
results committed separately. Push new branch, verify remote ref.
