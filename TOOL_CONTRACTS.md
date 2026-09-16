# Tool Contracts — constraint-state-v1

Two model task kinds: **interpret** and **choose**. Both are native tools
dispatched through `engine._dispatch`; their schemas are bounded jsonschema
(no arbitrary `Patch`/`Patch[]` fields). The program validates, reduces, and
routes; the model only proposes.

---

## interpret

**When:** INTERPRET phase, after new evidence has been delivered for the
current task.

**Purpose:** Explain what the delivered passage says *for the current task
only*. The program validates source delivery and quote existence, records the
judgment, and deterministically reduces routing.

### Schema (bounded)

```jsonc
{
  "task_id": "t1",              // must equal the active task id
  "source_ref": "e1",           // must be in this decision's received-reference scope
  "quote": "exact phrase",      // must occur in the evidence window text
  "statement": "what the source says",
  "subject": "Ada Rowan",
  "relation": "first_director",
  "value": "Ada Rowan",
  "state": "supported",         // unknown | supported | contradicted | disputed | identity_unknown
  "exit": ""                    // optional: "propose_amendment" + amendment field
}
```

### Six-part contract

| Part | Detail |
|------|--------|
| **Name** | `interpret` |
| **When available** | INTERPRET phase only (new evidence delivered) |
| **Required inputs** | `task_id`, `source_ref`, `quote`, `statement`, `subject`, `relation`, `state` |
| **Program checks (deterministic)** | (1) `task_id` == active task; (2) `source_ref` in received-reference scope; (3) `quote` occurs in evidence window text |
| **Program does NOT check** | Whether the passage semantically supports/contradicts the claim. `semantic_status: "not_automatically_verified"` is returned. |
| **Effect** | `evaluation.add()` + `reduce()` → routing update; `local_interpret` archived |

### Rejections (ContractError codes)

- `task_mismatch` — `task_id` ≠ active task.
- `unreceived_reference` — `source_ref` not in `binding["evidence"]`.
- `quote_not_found` — `quote` not a substring of the evidence window text.

### Exit / amendment

If `exit == "propose_amendment"` and `amendment` is supplied, the program
calls `frame.amend()` — the only audited path that changes the frame. The
amendment records `old`, `new`, `basis`, `affected_tasks`.

---

## choose

**When:** CHOOSE phase (no new evidence pending, or after an interpret).

**Purpose:** Select the next research entry, or finish if the answer target
is supported.

### Schema (bounded)

```jsonc
{
  "task_id": "t1",
  // exactly one of:
  "answer": "Ada Rowan", "refs": ["e1"],   // → finish (terminal)
  "query": "Lumen Observatory first director",  // → program dispatches search
  "choice_id": "read_hit_d1",              // → program emits controller_planned read
  "exit": "no_suitable_option"             // → records exit, episode continues
}
```

### Six-part contract

| Part | Detail |
|------|--------|
| **Name** | `choose` |
| **When available** | CHOOSE phase (and FINISH if routing is `answer_ready`) |
| **Required inputs** | `task_id` + exactly one of `answer`/`query`/`choice_id`/`exit` |
| **Program checks** | `task_id` == active task; exactly one branch; `answer` requires `refs` ⊆ delivered evidence |
| **Program does NOT check** | Whether the answer is semantically correct; whether the query is "good" |
| **Effect** | `answer`→finish; `query`→real `search` dispatch; `choice_id`→real `read`; `exit`→no dispatch |

### Dispatch mapping

- **`answer` + `refs`** → the program maps to a native `finish` call. The
  answer is submitted through the existing answer-contract path
  (`string-integer-v1`: integers → decimal text, strings exact). Terminal.
- **`query`** → the program calls `harness._dispatch("search", {"queries":
  [query], "top_k": 5}, binding)`. The query parameter is
  `controller_planned` (program-generated), but the search backend is the
  native retriever (CPU FTS5 / BM25). The result is returned to the model with
  `controller_planned_query` labelled.
- **`choice_id` (`read_hit_dN`)** → the program emits a `controller_planned`
  read at the referenced position. The read is a real native `read` dispatch;
  only the *choice* is controller_planned, not forged as a native policy action.
- **`exit`** → records no suitable option; no dispatch; episode continues
  until budget or finish.

### Rejections

- `task_mismatch` — `task_id` ≠ active task.
- `unreceived_reference` — `answer` refs not all in delivered evidence.
- `answer_not_ready` — `answer` supplied but routing is not `answer_ready`.

---

## Online short versions (≤88 request budget)

For online validation the schemas are identical; only the *episode budget*
shrinks. The contracts do not change between offline and online. The model
sees the same NL view and the same tool schemas; the program enforces the same
structural checks. Online runs use the existing authorized model and CPU index
config; no key/account/model switch on failure.

### Phase-tool availability (online = same as offline)

| Phase | Tools available |
|-------|-----------------|
| INTERPRET | `interpret`, `finish` |
| CHOOSE | `choose`, `search`, `read`, `find`, `recall`, `finish` |
| FINISH | `choose` (answer branch), `finish` |

### Budget binding (online)

- Stage A: up to 3 versions × 4 slots × ≤6 requests = ≤72
- Stage B: one natural pairing ≤88
- Stage C: ≤8 judge
- **Total cap: 168 new model HTTP requests.**
- All requests including format repairs count toward budget.
- No empty ledger created to reset; historical 357/844 balances are not current.

---

## controller_planned labelling

Every program-generated action records:
- **cause** — the `choose` call that triggered it.
- **ticket** — the `task_id` of the active task.

A `controller_planned` read is **not** forged as a native policy action: the
archive records it as `controller_planned`, and the model's `choose` call is
the audited origin. Tested by `test_controller_planned_read_labelled_not_forged`.
