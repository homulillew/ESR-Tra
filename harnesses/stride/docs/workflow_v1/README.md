# Gap-driven ReAct Workflow v1

## Why this exists

Hard-case traces showed two recurring failures: models repeatedly searched without opening already-returned pages, and repeated/noisy observations did not reliably become a concrete next research gap. Successful short cases also showed that the simple `search -> read -> finish` route must remain available.

The design separates operational state maintained by the harness from fallible research state optionally maintained by the policy.

## State

Operational state records which navigation cards and raw windows were actually delivered, exact query/result repetition, latest new navigation/raw evidence and bounded recovery stage. Research state stores one optional active gap plus up to four prior versions. Gap status is always `agent_judgment_not_verified`; provenance checks do not imply entailment.

Gap kinds: `locate/read/relation/disambiguate/conflict/recover`. Status: `open/supported/rejected/conflict`. Supported/rejected/conflict require delivered eN refs, but the harness still does not judge semantic correctness.

## Tool contract

Every enabled tool has six model-visible sections: FUNCTION, USE WHEN, AVOID, INPUT, OUTPUT, WORKFLOW. `search` is navigation only. `read` opens raw text with only a received ref; offsets are optional. `find` is literal page-local navigation. `recall` recovers already-delivered material. `notes` remains optional. `finish` submits or abstains. Full mode adds `update_gap`.

## Goal-directed reading

With `guided_read`, `read({"ref":"dN","goal":"..."})` selects one lexical block inside the frozen document using deterministic CPU term-overlap scoring, preserves original Unicode offsets, and returns exact raw text. A no-match returns `matched=false` and creates no evidence window. This is not a semantic reranker or a replacement for exact `start/length` reads.

## Search-result reuse

With `reuse_results`, only an exact query/top-k/result fingerprint that has already been delivered can return `view=reuse`. It keeps refs/titles/read actions but omits repeated snippets. `replay=true` restores the full cached navigation view. Same document with a different snippet is not silently collapsed; withheld/unreceived results are not treated as seen.

## Bounded repetition recovery

Modes: `off`, `observe`, `bounded`. In bounded mode the default is two exact-repeat search rounds, two recovery decisions, then a finish-only request. Recovery leaves read/find/recall/new search/finish available and blocks only a wholly repeated search batch. If the finish-only request still produces no legal finish, terminal outcome is `stalled_no_submission` with an empty answer, never a fabricated abstention.

The detector is deliberately narrow: paraphrased searches, repeated reads, bad gap updates or semantic stagnation can still escape it. Failing sooner is not automatically better.

## Profiles

- `legacy`: base behavior and old descriptions.
- `interface`: six-part descriptions plus explicit navigation/read metadata.
- `full`: interface + goal-read + gap state + result reuse + bounded repetition recovery.

Direct Python API defaults to legacy for historical reproducibility. CLI `run/schema` default to full. Experimental runners must record `WorkflowConfig.identity()` explicitly.

## Research basis

The implementation borrows design ideas from ReAct, AgentOccam, SLIM and retrieval-interleaved reasoning: observations should drive a concrete next action, search and reading should be distinct, and action/observation interfaces should be usable by the model. It does not claim to reproduce those systems or inherit their scores.

## Known limits

This workflow does not solve semantic contradiction, provenance entailment, source independence, alias-heavy page selection, or all forms of looping. More state and richer tool descriptions increase prompt cost. Natural-task evaluation must report correctness, failure/abstention, actual evidence acquisition and total model/backend/token/time cost together.
