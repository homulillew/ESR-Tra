# Discovery-04 q774 middle-history sealed-slot audit

## Scope and integrity

Only q774-middle-history-v1-r1 was examined after the seal notice. All 80 SEALED.json-listed file hashes passed. Read-only archive verification passed for 469 events, head cd7bc8af4ed3e8a47c243b927b4ba12237414b6cd74e3649991b77edea97dc0f. No current baseline, controls, gold or other questions read; no API or frozen-file modification.

There are exactly 16 model requests and 16 history_projection events. For every round, captured request.body JSON equals the archived request object; captured request/saved-response metadata SHA256 values match actual bytes where supplied. Rebuilt each projection from the original round_end group objects using the specified first/latest rounds. The resulting audit fields, message digests, removal hashes/counts and changes list exactly equal the recorded event payload, excluding target round. The complete projected history subsequence equals actual wire messages after standard removal of internal serializer fields such as _error. This comparison includes exact tool-call argument strings, IDs, order, and complete tool receipt content strings.

For every original completed group, assistant content equals its historical raw response.body content and each tool call ID/function/argument string agrees. The original archived prose is intact; only next-request visible assistant content is projected. Final archive verification passed again. The audit's machine-readable table is discovery04-q774-projection-checks.json.

## Actual per-request projection

Columns below list target round, retained completed source rounds, source rounds whose prose becomes null, total omitted characters for this request, ordinary rolling compaction flag, and FINAL flag.

| Target | Retained | Prose omitted | Characters | Compacted | FINAL |
|---|---|---|---:|---|---|
| 1 | [] | [] | 0 | False | False |
| 2 | [1] | [] | 0 | False | False |
| 3 | [1, 2] | [] | 0 | False | False |
| 4 | [1, 2, 3] | [2] | 265 | False | False |
| 5 | [1, 2, 3, 4] | [2, 3] | 425 | False | False |
| 6 | [1, 2, 3, 4, 5] | [2, 3, 4] | 756 | False | False |
| 7 | [3, 4, 5, 6] | [3, 4, 5] | 971 | True | False |
| 8 | [5, 6, 7] | [5, 6] | 774 | True | False |
| 9 | [6, 7, 8] | [6, 7] | 736 | True | False |
| 10 | [7, 8, 9] | [7, 8] | 856 | True | False |
| 11 | [8, 9, 10] | [8, 9] | 626 | True | False |
| 12 | [9, 10, 11] | [9, 10] | 455 | True | False |
| 13 | [10, 11, 12] | [10, 11] | 506 | True | False |
| 14 | [11, 12, 13] | [11, 12] | 487 | True | False |
| 15 | [12, 13, 14] | [12, 13] | 525 | True | False |
| 16 | [13, 14, 15] | [13, 14] | 598 | True | True |

The first completed group is R1. It is preserved while present (through input R6). At R7 it has been evicted by rolling compaction; it is not restored, and surviving R3 is correctly treated as a middle group whose prose is omitted. Every latest group R-1 is preserved. Inputs R1-R3 correctly remove nothing; R4 first removes R2 prose. R16 applies the same rule while FINAL. Summed removals over all request views equal 7980 characters; this is repeated-history transmission removed, not 7980 unique characters deleted from the archive. There are no extra projection events from preflight rendering. Anthropic-specific behavior is unobserved in this GLM/OpenAI-compatible slot.

## Research behavior and earliest substantive failures

R1 correctly parses three or four marriages and searches. Input R2 has the Screen Rant siblings lead d1. The model promptly reads d1 at R2 [0,3000), e1, then R3 [3000,9000), e2. The first window is general article introduction/other families; e2 contains the Jessica And Richard Harmon section, explicitly maps Jessica to Niylah and Richard to John Murphy, and says the real-life siblings play unrelated characters. This source attribution is grounded once e2 is delivered.

At R4 the model selects Jessica/Niylah for further checking. The source supports both siblings but does not determine which could satisfy the remaining conditions. Treating Jessica as a test candidate is legitimate; treating the sibling relation as strong support for the complete identification is not. R4 also asserts 2014 premiere and seven seasons without a read source for those dates/counts. No later source reading is performed, so marriage count, surviving child, height and full series-timing verification remain unresolved.

R5 notices uncertainty about Niylah and genuinely widens queries to the marriage/child condition; R6-R8 try generic or familiar-show routes. At R7/R8 it narrows the inequality to 'so 3 times', dropping four despite the original question and preserved R1 prose. R9 returns to Jessica/Niylah, then R10-R15 repeatedly searches that candidate and page names. R11 introduces Ilian/Kane as possible husbands and Hope as a possible daughter inside queries without a source-backed relationship. These are unsupported query hypotheses, not evidence or established facts.

The earliest persistent failure is failure to convert the already supported partial relation into a discriminating test of the other conditions. It is not failure to receive or read any useful source. Prose omission does not prevent anchoring: the unchanged raw source remains relevant to the sibling clue and the latest assistant text continues restating the same candidate. The intervention retains tool calls and receipts as designed, so it also retains candidate-specific search history. This is an observed limitation, not a reason to assert the projection implementation malfunctioned.

## Ending and accounting

Sixteen model decisions, 39 query-execution events, 36 backend requests, two raw windows from one document, 212 navigation documents. R16 explicitly admits that only the relative clue and Niylah's season-3 appearance are source-supported, with marriage count, surviving child and height unverified. It nevertheless issues another search while the actual request is FINAL. The result is final_only, executed=false, action_slot_charged=false, followed by model_budget and empty answer. The proposed last search never reaches retrieval.

The visible-history projection is faithful in this execution; it does not establish a behavioral or correctness benefit. The current baseline has not been read, so no paired treatment-effect claim is made. Like previously sealed q774 examples, one true relation keeps an unverified candidate active, but this observation is qualitative history only. The failure to choose legal finish is separable from source verification and from projection integrity.


## Addendum: current discovery-04 baseline paired audit

The newly sealed current q774-baseline-r1 has now been read and seal-verified. Its archive passes verification with 431 events and head cab9f31ac95e9d647c03d39b0a20c3bc994ea8cfda214dbefc31a07248f6487f. It has zero history_projection events, as required. No historical baseline substitutes for this comparison, and no current control/gold was read.

Both R1 request bodies have identical SHA256 fe019b884af954cf8777f10448535ff340cb76bb43e9ff9bfcb87c4cc5b7cdcd. Yet baseline R1 generates different, broader marriage/child queries, while treatment R1 asks explicitly about unrelated real-life relatives and height. Baseline R2 pursues soap-opera candidates and emits malformed queries as a string; treatment R2 reads the Harmon lead. Baseline R3 corrects its query formatting; treatment R3 reads the next source window. The first actual prose omission is only treatment input R4. Thus the early candidate and reading divergence predates any visible projection change and cannot be credited to that change.

| Quantity | Current baseline | Middle history | Difference |
|---|---:|---:|---:|
| Model requests | 16 | 16 | 0 |
| Declared tool calls / action-result events | 16 | 16 | 0 |
| Query-execution events | 42 | 39 | -3 |
| Backend requests | 35 | 36 | +1 |
| Read actions | 0 | 2 (R2,R3) | +2 |
| Find actions | 0 | 0 | 0 |
| Raw evidence windows | 0 | 2 | +2 |
| Registered navigation documents | 193 | 212 | +19 |
| Provider prompt tokens | 277784 | 274729 | -3055 |
| Provider completion tokens | 2446 | 1882 | -564 |
| Provider total tokens | 280230 | 276611 | -3619 |
| Provider cached tokens | 84736 | 72320 | -12416 |
| Elapsed seconds | 154.18 | 173.80 | +19.62 |

Token values are summed original response usage fields. The measured 7980 characters removed from repeated treatment request views are not a paired token-saving estimate: trajectories, tool outputs and cache histories differ. Treatment uses slightly fewer total tokens but one additional backend request and more wall time in this pair; these are observations, not isolated causal effects.

Baseline never reads any source. It cycles through soap-opera guesses, Callie Torres/Sara Ramirez, Hope Brady, Sharon Newman/Phyllis Summers, Jane Villanueva/Gina Rodriguez and La Usurpadora. Its R6 and R9-15 prose repeatedly returns to the same telenovela hypothesis while queries sometimes change. There is no grounded subject/role chain comparable to treatment's genuinely supported Harmon-siblings relation. Its query mentioning La Usurpadora 1998 at R15 is a warning that its proposed show may conflict with the requested period, but an unexecuted/unchecked query hypothesis is not itself verified source evidence.

The baseline's first local contract error is R2: queries is a string rather than the required array; R3 acknowledges the formatting issue and retries. This costs a decision but does not explain all subsequent non-reading behavior. The persistent research failure is remaining at navigation/guessing for the entire episode. Treatment improves source access in this particular trajectory but still leaves marriage count, surviving child, height and full timing unverified and anchors to Jessica/Niylah.

Both fail identically at the final interface: R16 issues search while only finish is permitted. The returned final_only error is executed=false and action_slot_charged=false; both then terminate model_budget with empty answers. Baseline does not turn missing evidence into a legal abstention; treatment explicitly states its missing conditions yet also fails to abstain. Neither R16 search reaches the backend.

The fresh paired result is therefore two empty submissions, no demonstrated task-success gain. Projection integrity passed in treatment, but the pair cannot establish that projection caused its earlier reading or reduced tokens because generation already diverged before R4. Semantic anchoring and FINAL compliance remain unresolved in both arms, in different candidate paths.
