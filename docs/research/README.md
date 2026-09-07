# Research Notes Index

This directory contains model-readable Markdown versions of the earlier research-analysis and experiment-plan artifacts.

## Read order

1. [`../harness/DESIGN.md`](../harness/DESIGN.md) — current Harness v2 forward contract.
2. [`../harness/VALIDATION.md`](../harness/VALIDATION.md) — what Harness v2 has and has not validated.
3. [`../harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md`](../harness/HARNESS_ACCEPTANCE_AUTOMATION_PROMPT.md) — executable all-automatic forward acceptance protocol for the server-side strong model.
4. [`ESR_GRPO_4B_RESEARCH_REVIEW.md`](ESR_GRPO_4B_RESEARCH_REVIEW.md) — repository audit, bad-case mechanisms, simplified ESR hypothesis, SFT/RL reasoning.
5. [`ESR_GRPO_4B_EXPERIMENT_PLAN.md`](ESR_GRPO_4B_EXPERIMENT_PLAN.md) — Markdown conversion of the earlier YAML-style experiment plan.

## Status conventions

- **Historical fact**: observed in repository code/reports under the referenced historical implementation.
- **Harness v2 addressed**: a mechanical issue now covered by the new forward implementation/tests; this does not prove semantic model quality.
- **Proposed**: experiment or hyperparameter not yet executed.
- **Acceptance prerequisite**: SFT/RL should not begin until the forward acceptance report reaches PASS or a carefully justified CONDITIONAL PASS.

## Why Markdown is the source format

These research documents intentionally use Markdown instead of DOCX/YAML because the main consumers are repository agents and server-side coding/research models. Markdown keeps:

- headings and experiment order explicit;
- assumptions next to parameters;
- links resolvable inside the repository;
- tables readable without document rendering;
- proposed values distinguishable from executed results;
- diffs reviewable in Git.

DOCX or structured configs can still be generated later for presentation/execution, but they should not become the canonical reasoning source.
