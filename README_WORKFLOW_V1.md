# ESR-Tra: STRIDE Gap-driven ReAct Workflow v1

Base: `9ac875aed9f3d7acd369cb913f0bfc3b768ca8f6`. Package remains `0.1.0a3` for compatibility with the existing a3 regression suite. Feature identity: `gap-workflow-v1`.

This branch iterates the existing STRIDE forward harness without modifying legacy ESR/GRPO artifacts. It keeps the CPU SQLite FTS5 retrieval path, the `string-integer-v1` answer contract, exact evidence windows, archive integrity checks and explicit finish semantics.

Main changes:
- all native tools use six-part descriptions: FUNCTION / USE WHEN / AVOID / INPUT / OUTPUT / WORKFLOW;
- `read(ref=dN, goal=...)` provides deterministic CPU page-local lexical selection while returning exact contiguous raw text;
- search cards explicitly separate navigation-seen vs raw-ranges-delivered and expose a concrete `read_action`;
- optional `update_gap` stores one sparse, fallible research gap plus bounded history;
- exact delivered search repeats can return compact reuse metadata rather than replaying full snippets;
- bounded repetition recovery can redirect to read/new search/recall/finish and eventually terminate as `stalled_no_submission` rather than looping indefinitely.

The workflow does **not** auto-verify semantics, auto-select correct pages, promote navigation to evidence, or treat early failure as improved accuracy.

See `harnesses/stride/docs/workflow_v1/` for the full design, tool contracts, validation notes and Codex experiment prompt.
