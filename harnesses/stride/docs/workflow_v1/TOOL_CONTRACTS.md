# Workflow v1 tool contract summary

The exact model-visible descriptions are generated from `stride_search.workflow_contract.TOOL_PARTS`; this file is a human review summary.

| Tool | Function | Use when | Avoid | Key input | Output | Workflow |
|---|---|---|---|---|---|---|
| search | locate candidate documents | no suitable page is known or a new relation/entity needs locating | page-name search when the intent is to read an existing dN; treating snippets as proof | 1-3 query strings, optional top_k; full mode also `replay` | navigation refs/snippets + cache/observation metadata | inspect dN, then read or change a discriminating clue |
| read | open raw document text or replay eN | a candidate page may resolve current gap | guessed handles, citing unread output | `ref`; optional start/length; full mode optional goal on dN | exact raw eN and offsets, or explicit no-match for goal-read | compare raw text, then continue/read/search/finish |
| find | literal page-local position lookup | known page, known literal anchor | treating zero match as factual absence | dN, text, optional start/case mode | positions/excerpts only, not evidence | find -> read matched range |
| recall | recover already delivered material | known lead left active context | treating recall excerpt as new evidence | lexical query | eN/dN/note navigation | replay eN or open dN |
| notes | optional scratchpad | reusable alias/rejected route/bridge clue | per-page summaries or verified-fact storage | put/delete | non-verified note state | optional alongside normal actions |
| finish | submit or abstain | answer sufficiently supported or task unresolved | claiming all clues verified, changing relation/time semantics | answer+refs or abstain+reason | explicit terminal | last call; only already-delivered eN can be cited |
| update_gap | replace active research gap | candidate/relation/rejection/conflict/next action changed | using prior guesses as evidence; updating every turn | subject/question/kind/status/refs/next_action/basis | bounded `agent_judgment_not_verified` state | observe -> update useful gap -> read/search/finish |

All source text, snippets and notes remain untrusted data. Navigation never becomes citable evidence merely because it is repeated or stored in workflow state.
