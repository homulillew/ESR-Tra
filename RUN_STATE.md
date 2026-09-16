# RUN_STATE — session handoff

**Profile:** constraint-state-v1
**NL view:** natural-language-local-v1
**Branch:** research/stride-local-state-nl-20260916T104031Z
**Base commit:** 0f34e9006b38be1e7119d934f39b151581f2dd18
**Date:** 2026-09-16

## Current state

**Phase: Offline acceptance COMPLETE. Online validation NOT STARTED.**

### Completed

- [x] Core implementation: `local_state.py` (LocalState, Frame, Evaluation, Task,
      dispatch_interpret, dispatch_choose, PROTOCOL, schemas, identity)
- [x] Engine integration: `_dispatch` interpret/choose, `_step` commit/complete,
      validate_call bypass for local tools, final-phase allow choose/interpret
- [x] Context integration: NL view injection, phase-tool availability,
      local_state_projection in return dict
- [x] decision_protocol: `constraint-state-v1` in PROTOCOLS, identity() branch
- [x] Formal regression tests: `test_constraint_state.py` (19 tests, all pass)
- [x] Full suite regression: 574 passed (0 failures)
- [x] DESIGN.md
- [x] TOOL_CONTRACTS.md
- [x] CAMPAIGN_PLAN.json
- [x] VALIDATION.md
- [x] RESULTS.md (offline portion; online TBD)
- [x] IMPLEMENTATION_PLAN.md (from earlier session)

### Pending

- [ ] Commit frozen implementation
- [ ] Push branch `research/stride-local-state-nl-20260916T104031Z`, verify remote ref
- [ ] Online Stage A (≤72 requests): near-end mechanism, 3 versions × 4 slots × ≤6
- [ ] Online Stage B (≤88 requests): one natural pairing
- [ ] Online Stage C (≤8 requests): judge
- [ ] Update RESULTS.md with online results
- [ ] Final report: three dependencies fixed, offline/online results, cost,
      failures, remote branch + full SHA

## Key files

| File | Role |
|------|------|
| `harnesses/stride/src/stride_search/local_state.py` | Core module: LocalState, Frame, Evaluation, Task, dispatch fns, PROTOCOL, schemas, identity |
| `harnesses/stride/src/stride_search/decision_protocol.py` | PROTOCOLS entry + identity() branch |
| `harnesses/stride/src/stride_search/engine.py` | _dispatch/_step integration |
| `harnesses/stride/src/stride_search/context.py` | NL view injection, phase tools |
| `harnesses/stride/tests/test_constraint_state.py` | 19 offline acceptance tests |
| `DESIGN.md` | Architecture: three objects, two tasks, boundaries |
| `TOOL_CONTRACTS.md` | Six-part contracts for interpret/choose |
| `CAMPAIGN_PLAN.json` | Frozen inputs, sequence, limits, promotion criteria |
| `VALIDATION.md` | Actual tests, first failures + fixes, untested scope |
| `RESULTS.md` | Offline results; online TBD |

## Fixes applied during test development

1. **Task ID counter** moved from class-level to per-LocalState-instance
   (`_task_seq`) for test isolation and deterministic per-episode IDs.
2. **Frame init** — `_harness` helper calls `init_frame()` for tests that
   inspect state without running a full episode.
3. **Evidence exposure** — tests needing `e1` exposed add a third scripted
   action (`finish`) to complete delivery-preflight.

## How to resume

```bash
cd C:\Users\wushuhong\Desktop\zip\ESR-Tra-local-state-nl-20260916T104031Z
python -m pytest harnesses/stride/tests/test_constraint_state.py --basetemp=".pytest_tmp" -q
```

Then commit, push, and proceed to online validation per `CAMPAIGN_PLAN.json`.
