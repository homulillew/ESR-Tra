# Workflow v1 validation contract

This branch preserves the existing source/ref/budget/integrity protections and adds mechanism tests for the new workflow. Validation is split into mechanical properties and model-behavior properties.

## Mechanical properties

- enabled tool descriptions contain all six sections and schemas match execution;
- `read(ref)` remains sufficient to open a document;
- goal/start are mutually exclusive; eN replay stays exact;
- goal-read returns a contiguous substring of the frozen source with original offsets; no-match creates no evidence;
- same-query reuse only applies after delivery, never to withheld/unseen results;
- same document with a different snippet/result fingerprint is not silently collapsed;
- gap updates validate refs, preserve no-op semantics, journal history and never grant evidence rights;
- duplicate-search guard cannot poison an independent finish; prior critical errors still block finish;
- bounded recovery consumes a finite number of decisions and cannot loop indefinitely through prose/errors;
- integer/text answer behavior, native tool IDs, archive verification and read-only replay remain compatible.

## Local pre-push validation

The implementation was developed against the locally available a3 historical test subset plus new workflow tests. Scripted scenarios preserved the three-decision `search -> read -> finish` path, demonstrated compact repeat reuse and bounded loop termination, and demonstrated a recovery path that switched from repeated search to read before finish. These are reachability checks, not model-quality evidence.

A bounded loop that stops earlier is still a failed task. Full mode also adds prompt bytes/tokens, so any efficiency claim must include that cost. The real experiment must measure correctness, evidence acquisition, policy/tool/backend calls, tokens and elapsed time together.

## Real experiment

Use `CODEX_PROMPT.md`. The first natural experiment compares legacy vs full on q775/q774 and then runs q771/q778 as short-path controls. It is an exposed-development experiment, not a general BC+ score. Preserve failures and do not tune online after seeing the first arm.
