# Discovery-02 q774 fresh paired audit

## Scope and accounting

Verified every listed SEALED.json file in q774-baseline-r1 and q774-search-pivot-v1-r1 before inspecting actual requests, responses, evidence and events. No control slots, gold, other-eight questions or APIs accessed; no tracked file edits.

Both arms used 16 model calls and legally abstained at R16. Baseline: 69 query executions, 70 backend requests, two reads/windows from one document; prompt/completion/total tokens 278713/3899/282612. Pivot: 49 queries, 43 backend requests, three reads/windows from two documents; tokens 297550/2700/300250. Thus fewer backend requests does not imply fewer total tokens: pivot used 17638 more total tokens. Elapsed seconds were 350.64 versus 257.24.

R1 request bytes are identical, SHA256 fe019b884af954cf8777f10448535ff340cb76bb43e9ff9bfcb87c4cc5b7cdcd. R1 outputs already differ in query count/content and top_k. Pivot reads at R2/R3, before its first intervention at R6. Its earlier reading must not be attributed to the later trigger.

## Trigger verification and actual next actions

Baseline has zero search_pivot events. Pivot has exactly two: R6 from completed source rounds [4,5], and R8 from [6,7]. Each pair searched without a new raw passage. Each event payload excluding round exactly equals the actual Current control state.search_pivot object in the respective request; instruction hash c521caeb6fa64abda3716807ed6881fcb50e6c8f8ae4b82e0eb0d50320d5ee84. This validates delivery and the two-trigger bound.

Neither response meaningfully follows the independent-clue instruction. R6 queries Richard Harmon, The 100 and John Murphy; R8 does the same via height, marriage and series Wikipedia terms. All remain bound to the existing candidate/show; there is no candidate-free query investigating a fresh relation. Those attributes were already pursued before the trigger. Successful event emission is not a successful behavioral pivot.

## Reading and source attribution

Both discover the Screen Rant relatives lead at input R2 and mention the Harmon siblings. Baseline waits until R10 to read d14 [0,3000), then R14 to read [3000,6000). Pivot reads the same page as d1 at R2 and R3. Its R2 head window e1 contains the general article introduction and other families, not the Harmon section. Its e2, like baseline e2, contains an explicit heading 'Jessica And Richard Harmon', the statement that the siblings play unrelated characters in The 100, and the mapping Jessica->Niylah, Richard->John Murphy.

This is a correctly grounded partial relation once e2 is delivered. References to e1/e2 jointly confirming the Harmons are overbroad: e1 alone does not support that relation. However, e2 does contain both names and roles, unlike q775's Farooqi window that lost the subject antecedent. Do not count a broad two-ref citation as wholly unsupported when one of its refs genuinely supports the claim.

Pivot R9 also reads d159 [0,898), e3. The complete short episode-list text says the series premiered March 19, 2014 and lists seasons 1 through 7, with season 7 in 2020. This genuinely supports the show timeline and more-than-three-seasons requirement as of 2023. Together with e2's statement that Richard was recurring in the first two seasons, it supports the character's early appearance. e3 alone is about the show, not the actor's debut.

Baseline repeatedly says at R5/R7 that Murphy's marriages/children do not fit, yet never sources that alleged mismatch and eventually describes these conditions as unverified. These are model judgments, not raw-text refutations. After R10 it recommits to Richard as a strong lead. Both arms confuse one supported relation with a 'core answer' even while the most discriminating conditions remain unresolved.

## Earliest errors, missing conditions, and ending

Pivot R1 compresses 'more than 2 but less than 5' to 'so 3 times', improperly dropping four. Later text recovers the original inequality, so this is an initial parsing defect, not a demonstrated cause of the final outcome. Both begin with a useful lead but then overcommit to it. Pivot reads promptly yet R4 onward searches almost exclusively to confirm Richard/Murphy. Baseline spends R2-9 cycling through remembered show candidates rather than reading its available relation source.

At finish, both still lack raw verification of fictional marriage count, only one surviving child, and the actor's height in the open interval (1.65,1.70). Baseline also lacks a read source for the series season count; pivot obtains it in e3. Neither has evidence tying all clues to this candidate. Neither should be scored as correct merely because the sibling clue is true.

Both R16 responses use finish(abstain=true), so this pair does not reproduce q775's FINAL action-compliance failure or the previous discovery-01 q774 length degeneration. Their reason is insufficient candidate verification after repetitive retrieval, not tool-schema failure. No gold-based answer judgment is made.

## Combined next mechanism hypothesis

Across q775 and q774, test a bounded action executor that requires one next step to address an explicitly named unresolved relation, uses a received relevant page with enough context to identify its subject when available, and constrains FINAL to a legal finish action; measure executed relation changes and candidate corrections rather than emitted reminders.

This is a hypothesis for fresh validation, not proof a harder gate will improve correctness. The present intervention reaches the model but is ignored at the action level; prompt delivery tests alone cannot validate its proposed behavioral benefit.
