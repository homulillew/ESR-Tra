# constraint-state-v1 — Natural-Language Local-Task State-Based ReAct

**Profile identifier:** `constraint-state-v1`
**NL view version:** `natural-language-local-v1`
**Base commit:** `0f34e9006b38be1e7119d934f39b151581f2dd18`
**Branch:** `research/stride-local-state-nl-20260916T104031Z`

---

## 1. Goal

A single controller that drives research as a sequence of *local tasks*.
The model sees natural-language descriptive roles — not A/B property equations,
not triples, not a logic DSL. The program carries stable IDs, dependencies,
sources, and versions. Two model task kinds alternate: **Interpret** (explain
the delivered observation for the current task) and **Choose** (select the next
research entry, or finish).

This profile **replaces** (does not stack on) the old `WorkflowState` gap
carrier for episodes that opt into it. Old profiles remain unchanged and
fully functional alongside it.

## 2. Three Internal Objects

### 2.1 Frame
The immutable original question and its descriptive roles.

- `question` — the original question text, never rewritten.
- `question_hash` — stable hash of the original question.
- `answer_target` — a short natural-language description of what the answer
  must identify (e.g. "the first director of Lumen Observatory").
- `roles` — descriptive role list, natural language (e.g. "person", "office",
  "date range"). **Not** formal property equations.
- `amendments` — append-only record of explicit task amendments. An amendment
  records `old`, `new`, `basis`, and `affected_tasks`. It is the *only* way
  the frame changes, and it is always auditable.

**Boundary:** An ordinary evidence update (a `source_statement` judgment) never
mutates the frame. `answer_target` and `question_hash` are stable across the
entire episode. This is tested by `test_frame_answer_target_stable_and_not_rewritten_by_evidence`.

### 2.2 Evaluation
Sourced, scoped, correctable judgments.

Each judgment records:
- `task_id` — which local task it bears on.
- `source_ref` — the delivered evidence window (e.g. `e1`). Must be in the
  current decision's received-reference scope; an undelivered ref is rejected
  with `unreceived_reference`.
- `quote` — the exact phrase from that window. The program checks the quote
  actually occurs in the evidence window text; a fabricated or snippet-approximate
  quote is rejected with `quote_not_found`.
- `subject`, `relation`, `value`, `state`, `scope`, `kind`.

**Constraint states** (the `state` field):
- `unknown` — the source does not establish this fact.
- `supported` — the source text supports this fact.
- `contradicted` — the source text contradicts this fact.
- `disputed` — sources conflict; both sides delivered.
- `identity_unknown` — the subject identity is unclear (e.g. the passage is
  about a different role than assumed).

**Evidence kinds:**
- `question_given` — a task/reference condition from the question itself. It is
  **not** candidate support and never makes routing `answer_ready`.
- `navigation_lead` — a search/find result that locates a source. It is
  navigation, not citable evidence; it cannot carry `state=supported`.
- `source_statement` — a citable statement extracted from a delivered window.
- `hypothesis` — an inference, kept separate from source statements.

**Corrections:** `evaluation.correct(task_id, judgment_index, new_state, ...)`
applies a `CorrectionPatch` that supersedes a prior judgment. An uncertain or
wrong extraction is **not** a permanent ban; the candidate is recoverable. This
is tested by `test_correction_recovers_state_without_permanent_ban`.

### 2.3 Task
The one current natural-language local question. Single gap carrier.

- `id` — program-generated, deterministic per-episode (`t1`, `t2`, …).
- `question`, `clause`, `candidate` — natural language.
- `entry_points` — research entries, each may carry `depends_on` (a
  `subject|relation` key).
- `attempts` — incremented by `bump_attempt()`.
- `voided`, `void_reason` — a dependent ticket is voided when its dependency
  is refuted.
- `routing` — `open | check_conflict | inactive | answer_ready`.
- `renames` — `rename()` appends the old question; **attempt history is not
  reset**. Tested by `test_task_rename_keeps_attempt_history`.

## 3. Two Model Task Kinds

### 3.1 Interpret
Runs when new evidence has been delivered for the current task. The model
explains what the delivered passage says *for the current task only*. The
program validates source delivery and quote existence, then calls
`evaluation.add()` + `reduce()`.

The program performs the deterministic reduction; the model only proposes the
judgment. `semantic_status: "not_automatically_verified"` is returned — the
program does not claim the model's semantic support judgment is correct, only
that it was structurally valid and reduced.

### 3.2 Choose
Runs to pick the next research entry. The model may:
- `answer` + `refs` → the program maps to `finish` (terminal submission).
- `query` → the program dispatches a real `search` via `harness._dispatch`.
  The query parameter is `controller_planned` (program-generated parameter),
  but the search backend is the native retriever.
- `read_hit_dN` / `choice_id` → the program emits a `controller_planned` read.
- `exit` → records no suitable option; the episode continues.

## 4. Phase Alternation

`advance_phase(delivered_new_evidence)`:
- If the active task's routing is `answer_ready` → `PHASE_FINISH`.
- If new evidence was just delivered and phase is not already INTERPRET →
  `PHASE_INTERPRET`.
- Otherwise → `PHASE_CHOOSE`.

One phase per model call. The phase determines which tools are available
(Interpret phase: `interpret` + `finish`; Choose phase: `choose` + native
`search`/`read`/`find`/`recall`/`finish`).

## 5. Deterministic vs Semantic Boundary

**Program (deterministic, no model):**
- Source-ref delivery check.
- Quote-in-window existence check.
- Boolean/date/quantity comparisons in `reduce()`.
- Routing transitions (`answer_ready` structural preconditions).
- Dependent-ticket voiding.
- Phase alternation.
- Budget accounting.

**Model (semantic, not verified by program):**
- Whether a passage *supports* or *contradicts* a fact.
- Subject identity disambiguation.
- Which entry to choose next.
- Whether the answer is ready to submit.

The program never claims the model's semantic judgment is correct. It only
enforces structural validity and deterministic routing consequences.

## 6. Reverse Boundaries (the negative invariants)

These are the core safety properties; each is tested:

1. **A missing fact is not a contradiction.** `state=unknown` routes to `open`,
   not `inactive`. (`test_unknown_does_not_inactivate_candidate`)
2. **An uncertain extraction is not a permanent ban.** A correction can
   recover a candidate. (`test_correction_recovers_state_without_permanent_ban`)
3. **The original question is not rewritten to fit a candidate.** The frame's
   `answer_target` and `question_hash` are stable across evidence updates.
   (`test_frame_answer_target_stable_and_not_rewritten_by_evidence`)
4. **A local refutation does not ban a name forever.** A contradiction voids
   only *dependent* tickets (those whose `depends_on` matches the refuted
   `subject|relation`); independent tasks are retained.
   (`test_contradiction_voids_dependent_tasks_not_independent`)
5. **Navigation is a lead, not a source statement.** A `navigation_lead`
   cannot carry `state=supported`.
   (`test_navigation_lead_cannot_be_source_statement`)
6. **The question's own conditions are not candidate evidence.**
   `question_given` records a condition but never makes routing `answer_ready`.
   (`test_question_given_is_not_candidate_evidence`)
7. **Identity uncertainty routes to check_conflict, not inactivate.**
   (`test_identity_unknown_routes_to_check_conflict_not_inactivate`)
8. **Integer/string answer contracts preserved.** Integers become decimal
   text; strings stay exact. (`test_integer_answer_contract_preserved`)

## 7. Three Data Dependencies

The profile fixes three data dependencies that the old gap carrier left
implicit:

1. **Original question → current local task.** The frame's `answer_target`
   drives the auto-created first task. The question is never rewritten.
2. **Delivered observations → sourced, scoped, correctable judgments.** Every
   judgment must cite a delivered `source_ref` and an exact `quote`. Judgments
   are scoped to a task and correctable.
3. **Updated judgments → available research options → real tool execution.**
   `reduce()` updates routing; `choose(query)` reaches the real search backend
   via `harness._dispatch`; `choose(read_hit_dN)` emits a real read. The model
   never issues a `search`/`read` that the program fakes — the program
   dispatches the real native tool.

## 8. Archive Integration

- `local_state_commit` — appended after each round's `commit()`, records
  `round`, `phase`, `view_sha256`.
- `local_interpret` — appended on each `dispatch_interpret`, records the
  judgment + reduction as a content-addressed object.
- `local_state_complete` — appended after each round's `complete()`, records
  `round`, `task_id`, `phase`.

Old archive events are unaffected; the new events are additive. Old profiles
remain fully compatible (`test_baseline_profile_still_works_unchanged`).

## 9. Budget

- `max_model_calls` from `Config` bounds the episode.
- Format repair: max 1 per response, ≤2 per episode, all counted.
- Every program-generated action (controller_planned search/read) records its
  cause (the `choose` call) and the ticket (`task_id`).

## 10. What This Is Not

- Not a logic engine. No formal property equations, no triples, no DSL.
- Not a semantic verifier. The program does not check whether the model's
  support judgment is semantically correct.
- Not a parallel state machine. It plugs into the existing
  `decision_protocol` machinery: `engine._dispatch`, `engine._step`,
  `context.build`, `archive`. All budget, provider, and dispatch
  infrastructure is reused.
- Not a replacement for the retriever. The native search backend is used
  unchanged; only the *parameter* (the query) is `controller_planned`.
