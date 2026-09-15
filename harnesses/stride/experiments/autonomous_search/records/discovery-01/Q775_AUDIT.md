# Discovery-01 q775: sealed two-arm audit

## Scope and outcome

Inspected only q775-baseline-r1 and q775-constraint-review-v1-r1 under discovery-01. Verified every file listed by each existing SEALED.json before reading. Used actual HTTP request/response bodies, trajectory action results and terminal events. Did not read q774, the other eight questions, or gold; made no model requests. No tracked files changed.

Baseline: 12 decisions, abstained, 27 query executions, 17 backend requests, zero raw evidence windows. Treatment: 16 decisions, model_budget with empty answer, 44 query executions, 34 backend requests, two raw windows. These are observed outcomes, not correctness judgments from gold.

## Earliest substantive failure by stage

**Candidate discovery is partially successful in both arms.** At input R2, baseline d1 and treatment d6 contain the Booker_Prize page navigation snippet: 'In 2007, Man Group plc established the Man Asian Literary Prize'. Both R2 outputs identify that award as a plausible candidate. This is a reasonable lead satisfying one condition, not yet a book/author solution. Neither arm's early failure is simply failure to find any relevant corpus hit.

**The first shared substantive breakdown is choosing repeated page-name search instead of consuming existing leads.** R3 in both arms asks to get the Man Asian prize Wikipedia winners/shortlist page and issues another search. Baseline R4-8 and treatment R4-9 keep pursuing essentially that page-name objective. Baseline R5 even uses site:wikipedia.org despite the declared OR retriever having no site filter. Rephrasing broad award terms adds weakly discriminating OR terms and returns mixed pages; it does not navigate to a named page. This combines policy action choice with a known retrieval interface limitation. It does not show that the desired page or answer is absent from the corpus.

By input R5 both arms have a concrete contender lead with a read_action: baseline d49/treatment d53, a Literary Hub page whose snippet says 'Between Clay and Dust, was shortlisted for The Man Asian Literary Prize 2012' and names Farooqi. Neither reads it. This is not proof it is the correct candidate; it is an available way to test a candidate instead of repeating winner-list searches.

**Baseline never reaches source reading.** Its R2 second search is also malformed: arguments.queries is a string, not the required list; action_result.code=arguments_invalid and executed=false. The first R2 search succeeds, so this schema error is a local wasted action, not the cause of the entire episode. R3 onward resumes valid but repetitive searches. R10 duplicate_query_blocked has blocks_finish=false; R11 uses replay=true and still does not read. R12 abstains, appropriately declining an unsupported answer, but its reason inaccurately says 'actually delivered source windows': there are no evidence_registered events. It is describing navigation information as if source reading occurred.

**Treatment delays reading despite having a candidate page.** d74 Haruki_Murakami navigation is first visible at input R7 with 'The book was longlisted for the Man Asian Literary Prize in 2011' and a read_action. The model repeats page-name searches R7-9, guesses winner names at R10, and only reads d74 at R11. Thus the first raw evidence reaches input R12, leaving four decisions including FINAL.

## Relation verification after treatment finally reads

The R11 read returns e1 on d74, start=0/end=3000/document_chars=54610. Its raw text genuinely contains:

- birth_place: Fushimi-ku, Kyoto, Japan;
- 'Growing up in Ashiya, near Kobe';
- 'his work translated into 50 languages';
- notableworks entries including 1Q84 (2010) and body mention 1Q84 (2009-10).

R12 correctly identifies the birthplace and childhood city, but treats an author-wide translation count as a clue for the requested individual book. At R13 the check list promotes that to '>25' support and claims e1 includes 'longlisted for the Man Asian Literary Prize in 2011'. That phrase is in a navigation snippet, not the delivered e1 [0,3000) window. The English publication year and May 29 date likewise are not established by that raw window. This is the first definite post-read evidence-binding failure: author-level facts, navigation text, and unverified dates are consolidated into a book-level supported chain.

R13 does state the needed relation precisely: the winning author must be born in Ashiya and the other book must be released in 2010 if the selected first-book year is 2011. But R14-15 hypothesize The Rehearsal/Eleanor Catton from memory/navigation without verifying those requirements. R15 reads d89, yielding e2 [0,3000). It explicitly says birth_place 'London, Ontario, Canada', The Rehearsal 'was published in 2008', and The Luminaries won the '2013 Booker Prize'.

At R16 the model repeats London and 2008 yet labels 2008 'the preceding year before 2011'. It does not reject London versus the required Ashiya relation. It notices uncertainty about the award win but focuses on the awards table, overlooking already available city and arithmetic conflicts. This is not merely an omitted checklist: the checklist exists, but its entries are not used to reject the candidate.

R16 then calls read(d89, offset=3000, length=3000) while the actual request is FINAL and only finish is available. action_result.code=final_only, executed=false, action_slot_charged=false; terminal is model_budget with an empty answer. The use of offset rather than start is additionally inconsistent with the normal read interface, but the observed rejection is final_only, not an offset validation failure. No extra read was executed.

## Compression, looping, and causal limits

Baseline compacts at R7 and R10. Its page-name repetition begins R3-4, so compression cannot explain its onset. Treatment compacts at R5/6/7/8/10/11/12/13/14/15. Its page-name fixation also begins before the first compaction. The earlier treatment compaction is consistent with larger prompt/search-result volume (its top_k=10 versus baseline top_k=8 is a policy-chosen difference), but this pair cannot identify which element caused it.

Treatment does eventually change direction and obtain two windows. That is an intermediate improvement in source access, offset by later false evidence attribution, unresolved hard conflicts, and failure to use FINAL correctly. A single pair cannot establish whether the added protocol helps or harms generally. Nor does it justify labeling the entire issue weak prompting: the trace exposes navigation-to-read failure, OR retrieval mismatch, source-scope attribution, arithmetic/relation validation, and terminal action compliance as separable failure points.

## Concrete next experimental targets

1. Measure time from first received contender read_action to actual read, not just new-query or new-hit count. Both arms have testable leads by R5; treatment has d74 by R7 but waits until R11.
2. Require a proposed fact to reference the exact delivered window. An exact-substring check can catch falsely quoted e1 longlisting; it cannot establish book-specific translation scope or semantic entailment by itself.
3. Test whether a candidate is set aside when two already read values violate a required equality/year relation. Merely producing supported/unresolved labels did not enforce this at R16.
4. Keep termination compliance separate: treatment's last request already advertises FINAL. The observed error is a non-finish action, not lack of an abstention option.

These targets can be tested with synthetic fixtures and fresh paired development runs. No answer-specific entity, prize, or year should enter a generic mechanism. Do not treat this audit as a new scored control or use it to tune against unseen questions.
