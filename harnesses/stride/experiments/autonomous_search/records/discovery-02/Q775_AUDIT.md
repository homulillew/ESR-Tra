# Discovery-02 q775 search-pivot audit

## Scope and observed result

Only discovery-02/q775-search-pivot-v1-r1 was inspected, after verifying all SEALED.json file hashes. Earlier sealed discovery-01 q775 findings are used only as qualitative history, never as the current comparison arm. No current baseline, other unsealed slot, gold, or other-eight content was read. No model call or frozen-file modification.

Observed terminal: model_budget, empty answer, 16 decisions, 41 query executions, 34 backend requests, 135 navigation documents, two evidence windows from one document. Compression: R4/5/7/9/10/11/14.

## Trigger delivery and compliance

Two search_pivot events exist: R3 after source_rounds [1,2], and R5 after [3,4]. Those completed rounds issued searches and delivered no raw source passage. Both trigger timestamps precede the corresponding request. Programmatically compared each event payload excluding round with the actual request's Current control state.search_pivot: exact equality for R3 and R5. The instruction hash is c521caeb6fa64abda3716807ed6881fcb50e6c8f8ae4b82e0eb0d50320d5ee84; remaining model calls were 14 and 12. The trigger cap of two was respected.

The intended independent-clue action did not follow either trigger. Before R3, R2 had already considered both Man Asian Literary Prize and Jan Michalski Prize and searched translation counts and author-city relations. R3 searches the same two award names plus 'book translated into 26 languages shortlisted Man Asian Literary Prize'. It neither introduces a new identifying relation nor supplies a candidate-free query; changing a translation count to 26 does not create an independent clue. The Jan Michalski query omits Man Asian, but Jan Michalski was already an active candidate in R2 and keeps the same award-winner approach.

R5 is clearer noncompliance: both queries contain Man Asian Literary Prize and seek its Wikipedia page or winners/shortlists. R6-9 continue this path. Trigger instrumentation worked; action-level adoption failed. It would be incorrect to count two emitted trigger events as two successful search pivots.

## Available leads and reading delay

Award discovery works at R2: the model selects plausible awards created in the requested decade. By input R3 there are already inspectable document refs, including d44 and the d58 Oxbelly author page in control navigation. These are possible leads, not verified answers. The model's R4 commentary notices a Mohsin Hamid translation/shortlist clue but still chooses page-name searches rather than reading.

The earliest observed specific contender lead for the eventually selected book is input R6, d93, a Literary Hub page. The navigation snippet says 'Between Clay and Dust, was shortlisted for The Man Asian Literary Prize 2012' and includes Farooqi; read_action={ref:d93}, raw_ranges_delivered=[]. It remains unread until R10, after four additional decisions R6-9. That delay is directly measurable and does not require gold knowledge.

R10 reads d93 [0,3000), e1. The document is 53,433 characters and begins with an Olympics introduction and the Morocco/Fouad Laroui section. The window does not contain the selected Farooqi biography. R11 correctly switches to find('Between Clay and Dust'); R12 reads [23300,23700), e2. This is a real navigation improvement, but consumes three decisions to reach the relevant passage after the initial delay.

## Entity and relation errors after reading

The narrow e2 starts 'He was born in 1968 in Hyderabad, Pakistan' and later mentions the book and 'Farooqi'. It excludes the subject's full name. R11 had already guessed 'Omar Shahid Hamid (or Farooqi?)'; R13 invents 'Shahbano Bilal Farooqi'. R14 corrects the name to Musharraf Ali Farooqi after another search. The passage selection lost the pronoun's antecedent, so having a relevant exact window did not establish a complete subject binding.

R13-14 also treat Hyderabad as where the author grew up, while e2 only establishes birthplace and current residence between Toronto and Karachi. The required childhood-city relation remains unverified. Translation into more than 25 languages remains unverified too; R13 mentions it, R14 drops it from the immediate checklist, and R16 finally restores it as a reason to reconsider the candidate. There is no verified winning-book/author chain.

## Why the episode ends

R16 explicitly recognizes that the translation-count clue does not clearly fit Between Clay and Dust and proposes broader searches. This is a late conceptual pivot, not compliance with the earlier R3/R5 interventions. The actual R16 request is FINAL, so search is rejected with action_result.code=final_only, executed=false and action_slot_charged=false. The terminal is then model_budget. There is no R16 retrieval failure because the search was never executed, and no HTTP length degeneration like discovery-01 q774.

## Interpretation boundaries

The first substantive failure is not missing intervention delivery: exact control matching confirms delivery. It is continuing the award-name search strategy despite received instructions and candidate read_actions. Later failures are delayed source access, an evidence window without the subject antecedent, substituting birthplace for childhood city, and non-finish action selection at FINAL.

Earlier sealed q775 runs show qualitatively similar page-name loops and final_only behavior; that historical resemblance is useful for hypothesis generation only. The current baseline is not part of this audit, so no treatment effect or improvement claim is justified. The new mechanism can currently claim that it triggers and reaches the wire, not that it causes independent-clue exploration.


## Addendum: fresh discovery-02 baseline now sealed

The current q775-baseline-r1 has now been independently seal-verified and reviewed. This section is the fresh within-stage pair, replacing no historical records. Other slots remain outside scope.

The first actual request.body is byte-identical in both arms: SHA256 f04ab436073f1d8df23d07c19d6249d5305d80faa99f820cf8b53b35eb4a8b16. Nevertheless R1 outputs differ: the pivot arm adds the token prize to its first query, while baseline does not; R2 follows different award candidates before the first intervention at R3. Thus candidate-path differences before R3 are observed model-generation variability, not an effect of the pivot intervention. Temperature zero does not make these executions identical.

| Observed quantity | Fresh baseline | Search pivot | Pivot minus baseline |
|---|---:|---:|---:|
| Model decisions | 14 | 16 | +2 |
| Query execution events | 44 | 41 | -3 |
| Backend requests | 40 | 34 | -6 |
| Read actions | 2 (R5,R7) | 2 (R10,R12) | 0 |
| Find actions | 0 | 1 (R11) | +1 |
| Raw evidence windows | 2 | 2 | 0 |
| Source documents actually read | 2 | 1 | -1 |
| Registered navigation documents | 180 | 135 | -45 |
| Provider prompt tokens | 240647 | 274952 | +34305 |
| Provider completion tokens | 10339 | 2030 | -8309 |
| Provider total tokens | 250986 | 276982 | +25996 |
| Provider cached tokens | 85248 | 113408 | +28160 |
| Elapsed seconds | 264.60 | 120.50 | -144.10 |

Tokens are sums of actual response usage fields, not byte-counter estimates. Both provider reasoning-token totals are zero. Cost is not inferred from the returned zero price fields. Both terminal answers are empty: baseline stalled_no_submission; pivot model_budget. This pair establishes no correctness gain. Shorter prose/latency in the pivot execution is descriptive and cannot be isolated causally from the pre-trigger path divergence.

Baseline has an Obioma d90 navigation lead at input R4 with the two titles, years, Booker shortlist, translation-count snippet and read_action. It reads this at R5, earlier than the pivot's eventual d93 reading. R7 reads d143, a Guardian article on the 2015 International Booker winner. Baseline repeatedly notices that Obioma's novels were shortlisted for the ordinary Booker rather than International Booker, and later notices Kingston versus Akure does not match. However, it keeps revisiting the same candidate instead of acting on those conflicts.

### Why bounded-workflow FINAL still fails in baseline

R9 chooses a three-query Marlon James/Obioma batch. R10 and R11 repeat it. Actual controls show R11 normal with consecutive_repeat_rounds=1; R12 recover with repeat count 2 and recovery_decisions_used=0; R13 recover with count 3 and used=1. R12 and R13 repeat the same batch again and receive duplicate_query_blocked with blocks_finish=false. Those errors explicitly allow legal finish and use no backend calls.

Input R14 is unambiguously phase=FINAL, workflow.stage=final, repeat count 4, recovery_decisions_used=2, and still has three model calls remaining. The supplied tool list contains only finish. The response nevertheless emits the same search batch, following another long reconsideration of award/history/city conflicts. action_result is final_only, executed=false, action_slot_charged=false, blocks_finish=true. The runner terminates stalled_no_submission with detail 'No legal finish in bounded recovery final decision'.

Therefore this is not global or episode call exhaustion, an absent finish tool, or a failed backend search. Bounded recovery correctly reaches its terminal interface, but the policy fails to select its sole legal action. The pivot execution exhibits the corresponding action-compliance failure at its budget-reserved R16 FINAL instead. Reading twice and articulating contradictions did not guarantee either candidate correction or valid termination.
