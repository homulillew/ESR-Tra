# Discovery-01 q774 sealed treatment audit

Read only the sealed q774-constraint-review-v1-r1 slot, after verifying every SEALED.json file hash. No gold, other questions, model calls, or tracked edits.

Six model requests; 27 query executions and 27 backend requests; 177 registered navigation documents; no raw evidence windows. Compression at R4, R5, R6. Terminal outcome is incomplete_response, not model_budget.

The first retrieval problem appears at R1: broad relational OR queries return keyword-overlap pages without establishing the requested relation. For example, input R2 d4 is an IMDb death-year list with a snippet about Richard Pryor being married seven times and fathering eight children; d1 is a celebrity deaths gallery, while d20 is Jay North. None of these top examples binds the requested fictional character's marriages/child survival to the actor's real-life relative. These hits do not prove the corpus lacks a suitable source.

R2 explicitly says the results do not directly match, but moves to memory-suggested Grey's Anatomy/Private Practice/Shonda Rhimes. R3 guesses This Is Us/Yellowstone. There is no source-backed candidate established before those targeted searches. R4 reasons through several shows and R5 rejects parts of its own remembered candidates, yet still reads no actual page. The earliest substantive policy failure is replacing a failed relation query with familiar-show guessing without checking a received source or establishing a candidate relation. This precedes compression at R4.

R5 prose already revisits Outlander, Yellowstone, This Is Us, and The Walking Dead. R6 expands this into genuine within-response generation degeneration: HTTP 200, requested EB-GLM-5.2, returned glm-5.2, finish_reason=length, completion_tokens=4096, reasoning_tokens=0, and no tool_calls. Exact paragraph counting finds the Walking Dead paragraph 30 times and one This Is Us paragraph 15 times. This is not a display artifact or repeated tool delivery: those repetitions are in the original http/006/response.body assistant.content.

The harness records incomplete_response and executes no R6 action. Budget remains available; the queue stop is an infrastructure/response-validity stop under the runner's policy, not exhaustion of the 1000-attempt authorization. Compression co-occurs but a single response cannot identify its causal role. The evidence separates early retrieval/candidate failure from later output degeneration; neither should be summarized solely as a weak checklist prompt.

For a future falsifiable intervention, measure candidate grounding and navigation-to-reading before R4 independently from within-response repetition and finish_reason. Shortening prose or enforcing a bounded action-bearing response might address degeneration, but requires fresh paired validation rather than asserting success from this trace.
