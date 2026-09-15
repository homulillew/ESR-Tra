# Discovery-03 sealed q775 baseline: provider rejection audit

## Scope and integrity

Audited only discovery-03/q775-baseline-r1 after the explicit sealed-slot notice. No treatment, other slot, gold, API, or public/frozen file was read or changed. No attempt was made to remove or rewrite content to bypass provider inspection.

All 40 files listed by SEALED.json matched their stored SHA256 values. Read-only Archive.verify passed for 246 events, head aae4ac7a2610953afe691a58482337a129da32440bd652fe77e9dc36fcc20358, matching the seal. All six captured request.body JSON objects equal the corresponding archive.load_request(model_request.request). Captured request and saved-response hash fields, where present, matched body bytes.

The archive has six model_request events, five successful model_response events, five completed round_end groups, one model_failure and terminal http_error. Requests 1-5 received HTTP 200. Request 6 received HTTP 400. The original sixth response body contains a provider error whose type/code is data_inspection_failed and whose message says input data may contain inappropriate content. It does not contain a normal assistant completion.

## What changed before request 6

R5's successful assistant response restates the literary puzzle and issues two search calls: two award/Wikipedia queries and three Han Kang/The Vegetarian biography/publication/translation queries. Both tool receipts have ok=true. There is no new read action or raw evidence window in R5. The new material for the next request is assistant prose, its unchanged tool-call arguments, and navigation search-result receipts/snippets, plus ordinary updated control state.

The first receipt points to Booker_Prize and author/book pages such as Eleanor_Catton, Richard_Powers, Girl_Woman_Other, Peter_Carey, Julian_Barnes and Yann_Martel. The second contains literature/biography coverage from The Conversation, The Guardian, TIME, Books+Publishing, Literary Hub and other indexed pages, plus mixed keyword-overlap Korean biography/art/culture pages. Their subjects include Han Kang, translation/publication dates, and literary summaries. Source diversity and imperfect lexical matches are observable; the provider error does not identify which source, phrase, or field caused its decision.

R6 request is 87,642 bytes, compared with R5's 83,622. Ordinary rolling compaction is marked true in R4/R5/R6. R6 retains completed history groups R4 and R5. Their assistant prose, tool-call IDs/names/argument strings, and tool receipt content strings are equal to the archived groups after normal omission of internal serializer fields such as _error. A first overly strict comparison including _error failed; field inspection showed only this known internal-field difference, and the wire-field comparison then passed. This is not source-content editing or the new projection mechanism.

## Baseline and local protocol checks

The header is baseline (no nonbaseline decision_protocol field), and there are zero history_projection events. No middle-history projection is present in R6: retained assistant prose is unchanged. The treatment slot did not execute, so this interruption supplies no online evidence about the treatment's projection correctness or effectiveness.

All six wires have properly paired assistant tool-call IDs and following tool receipts, with no unmatched or duplicate outstanding call during the sequential check. Their schemas include the normal research tools; request 6 is not an invalid attempt to use a nonexistent FINAL tool. Every request agrees with its archived wire. R5's two search results are successful. No local arguments_invalid, final_only, missing tool receipt, or archive/request mismatch was found to explain the rejection.

These checks exclude the inspected local pairing/serialization faults; they cannot prove how the external service evaluates its input. Do not infer a specific banned term, source, category, or bypass from data_inspection_failed alone.

## Outcome interpretation

The harness records model_failure round=6, code=http_error, exception_type=ContractError, then terminal outcome=http_error with an empty answer. The refusal occurs before a sixth normal model response; it is an external input-inspection rejection, not a model-selected wrong answer, abstention, generation-length collapse, or exhausted research budget.

Earlier rounds still show unresolved award/book reasoning and repeated searches, but the stopped run cannot be scored as an ordinary completed research failure without explicitly separating infrastructure rejection. The queued treatment and remaining slots provide no paired comparison because they were not run; no judge ran. Preserve the original rejected request/response and accounting record for review rather than modifying this trace and treating a subsequent run as the same attempt.
