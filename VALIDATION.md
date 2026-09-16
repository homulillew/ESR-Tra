# Validation — constraint-state-v1

## 1. Offline acceptance

**Command:**
```
python -m pytest harnesses/stride/tests/test_constraint_state.py --basetemp=".pytest_tmp" -q
```

**Result:** `19 passed in 3.15s`

### Test inventory (all pass)

| # | Test | Acceptance criterion |
|---|------|---------------------|
| 1 | `test_frame_answer_target_stable_and_not_rewritten_by_evidence` | Original question/roles not rewritten by evidence |
| 2 | `test_task_amendment_records_old_new_and_affected` | Amendment is audited (old/new/affected) |
| 3 | `test_interpret_rejects_undelivered_source_ref` | Source actually delivered (`unreceived_reference`) |
| 4 | `test_interpret_rejects_quote_not_in_window` | Quote/sentence location (`quote_not_found`) |
| 5 | `test_interpret_accepts_exact_quote_in_window` | Exact quote accepted → `answer_ready` |
| 6 | `test_contradiction_voids_dependent_tasks_not_independent` | Local refutation not expanded; dependent voided, independent kept |
| 7 | `test_unknown_does_not_inactivate_candidate` | Missing info ≠ contradiction (`open`, not `inactive`) |
| 8 | `test_identity_unknown_routes_to_check_conflict_not_inactivate` | Identity/source conflict → `check_conflict` |
| 9 | `test_correction_recovers_state_without_permanent_ban` | Same-source correction recoverable |
| 10 | `test_task_rename_keeps_attempt_history` | Rename keeps attempt history |
| 11 | `test_reduce_does_not_promote_on_missing_identity` | Deterministic comparison does not promote on missing identity |
| 12 | `test_full_loop_choose_query_triggers_real_search_dispatch` | **Full execution:** choose(query)→search→read→interpret→answer_ready→submit "Ada Rowan" |
| 13 | `test_full_loop_interpret_changes_routing_before_next_dispatch` | Interpret changes routing before next dispatch |
| 14 | `test_integer_answer_contract_preserved` | Integer → decimal text (`42` → `"42"`) |
| 15 | `test_baseline_profile_still_works_unchanged` | Old archive/profile compatible |
| 16 | `test_controller_planned_read_labelled_not_forged` | controller_planned labelled, cause+ticket recorded |
| 17 | `test_choose_with_exit_records_no_dispatch` | Exit records no dispatch |
| 18 | `test_navigation_lead_cannot_be_source_statement` | Navigation is a lead, not source_statement |
| 19 | `test_question_given_is_not_candidate_evidence` | question_given is not candidate evidence |

### Full execution test (criterion 12, the required end-to-end)

`test_full_loop_choose_query_triggers_real_search_dispatch` verifies the
required chain:

> 原文 → 模型fixture输出局部判断 → 状态更新 → 旧任务失效/独立任务保留 → 新任务确实进入底层工具

Concretely:
1. `choose(query="Lumen Observatory first director")` → the program calls
   `harness._dispatch("search", ...)` — the **real** search backend runs
   (navigation recorded in `h.navigation_history`).
2. `read(ref="d1")` → real read dispatch, evidence `e1` delivered.
3. `interpret(source_ref="e1", quote="first director was Ada Rowan",
   state="supported")` → program validates delivery + quote, records judgment,
   `reduce()` sets routing to `answer_ready`.
4. `choose(answer="Ada Rowan", refs=["e1"])` → program maps to `finish`,
   submits `"Ada Rowan"`.

Terminal outcome: `submitted`, answer `"Ada Rowan"`. The search backend was
actually called (`len(h.navigation_history) >= 1`). This is not a state-label
assertion — it hits real dispatch.

## 2. First failures and fixes

During test development, three issues were found and fixed:

### Fix 1: Task ID counter was class-level (test isolation hazard)
**Failure:** Tests after the first failed with `'NoneType' object has no
attribute 'routing'` or `task_mismatch` because `Task._counter` was a
class-level counter shared across all `LocalState` instances. Task IDs drifted
(`t3`, `t4`, …) as tests accumulated, so `task_id="t1"` no longer matched.

**Fix:** Moved the counter to be per-`LocalState` instance (`self._task_seq`),
passed as `seq` to `Task.__init__`. Each episode (fresh `Harness` → fresh
`LocalState`) now starts at `t1`. This also makes task IDs deterministic per
episode, which is correct for archive replay.

### Fix 2: Frame not initialized outside `project()`
**Failure:** Tests inspecting `h.local_state.frame` directly failed with
`'NoneType' object has no attribute 'answer_target'` because `init_frame()`
was only called inside `project()`, which runs during `context.build()`.

**Fix:** The `_harness` test helper calls `h.local_state.init_frame(h.question)`
after construction. In production, `project()` still initializes the frame on
first call (idempotent guard).

### Fix 3: Evidence not exposed without a third action
**Failure:** Tests running `search + read` (2 scripted actions) found
`h.exposed` empty because evidence exposure requires the round to complete
through delivery-preflight, which needs the model to issue a third action.

**Fix:** Added a third scripted action (`finish`) to deliver `e1` into the
exposed shelf. The run still terminates with `model_transport` (scripted model
exhausted), but `e1` is exposed and the active task is `t1`, which is all the
tests need.

## 3. Full suite regression

**Command:**
```
python -m pytest harnesses/stride/tests/ --basetemp=".pytest_tmp" -q
```

**Result:** `574 passed in 178.15s` (555 existing + 19 new, 0 failures)

No existing test was modified. The new profile is additive: the engine,
context, and decision_protocol changes are guarded by
`decision_protocol == "constraint-state-v1"` checks and are inert for all
other profiles.

## 4. Untested scope

- **Real model semantic judgments:** All tests use `ScriptedModel` fixtures.
  They verify that the *program* correctly validates, reduces, and routes —
  not that a real model would produce the right judgment. This is by design:
  the program does not verify semantics. Online validation (Stages A/B/C) is
  where real model output is exercised.
- **Online budget pressure:** The 168-request cap is not exercised offline.
  Offline tests use small `max_model_calls` configs.
- **Multi-task episodes:** Most tests use a single active task. The
  dependent-voiding test covers multi-task dependency, but full multi-task
  research episodes with task switching are left to online validation.

## 5. Online validation status

**Not yet run.** Online validation (Stages A/B/C, ≤168 requests) proceeds only
after offline acceptance passes — which it now does. The campaign plan, frozen
inputs, and budget rules are in `CAMPAIGN_PLAN.json`. Online runs will use the
existing authorized model and CPU index config; results will be recorded in
`RESULTS.md`.
