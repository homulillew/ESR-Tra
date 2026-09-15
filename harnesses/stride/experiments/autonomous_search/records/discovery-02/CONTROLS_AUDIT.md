# Discovery-02 sealed short-control audit

## Scope and checks

Verified every SEALED.json-listed file in the four q771/q778 baseline/search-pivot slots, then read actual final tool calls, terminal basis, and raw evidence in requests. No gold or judge input accessed, no API requests, and no tracked edits. This audit checks support independently of the reported judge scores.

All four finish at R4 and submit legally. All four have zero search_pivot events. For these four-call episodes the trigger requiring two completed search rounds and at least three remaining model calls cannot activate after those first two rounds; only two calls would remain. They therefore test the inactive-protocol path, not recovery effectiveness.

For each question the two R1 request bodies are byte-identical:

- q771 SHA256 a61deeac7f2debefea800747f21cf59eb495c83b3fe63081feaef2c7a704fe3b
- q778 SHA256 7c3b4de711393e1eb56749a873d6860c113e222b59f4a83f8c44136a147268b7

No control path difference should be attributed to pivot triggers, because there are none.

## q771: supported answer, with a narrower citation caveat

Baseline finish: answer='Vakkorama', refs=['e1','e2']. Both windows come from d1, the Vitali Hakko biography, [0,3000) and [3000,6000).

The e1 passage names Vitali as the child born in 1913 in Istanbul's Yedikule district, with railroad-worker father and housewife mother, and says he opened Sen Sapka in 1934. The e2 passage explains the Vakko name from Vitali/Albert initials and surname letters, scarf production, Ankara/Izmir expansion in the seventies, then directly states that in 1982 he 'created a new brand together with his son Cem. Called Vakkorama, this chic new youth trademark'. This binds the answer, father/son relation, year, and younger market to the correct subject. Baseline's actual cited raw text supports the essential requested chain.

Pivot finish: answer='Vakkorama', refs=['e1','e2','e3']. e1 is the same biography head window. e2 is d12/Vakko Wikipedia [0,3000), naming founder Vitali, son Cem, 1934 hat shop, brother Albert, subsequent scarves, Ankara 1973 and Izmir 1979. e3 is the next [3000,6000) window and directly says 'In 1982, Vakkorama, one of Turkey's first youth stores, opened in Taksim, Istanbul.' Therefore Vakkorama as the 1982 youth-oriented brand is directly supported.

However, the pivot assistant overstates two exact attributions: e3 does not say Vitali created Vakkorama together with Cem; it states the opening/year/youth positioning only. e2 establishes Cem as Vitali's son but does not establish their joint creation of this brand. The explicit joint-creation sentence is in the baseline biography's second window, which the pivot did not cite/read. Similarly its initials explanation is not explicit in pivot e2. These gaps do not negate the direct answer support, but 'every clue verified by these exact refs' would be too strong. No cited window in either arm independently verifies the city tower's 1340s date; it remains an unused locating clue.

## q778: directly supported integer and correct person/date binding

Both finish calls use JSON integer answer=21 with refs=['e1']. The terminal stores decimal string '21' and records input_type='integer', input_value=21, operation='decimal'. No answer-type coercion ambiguity.

Baseline calls the article d41; pivot calls it d16. Both e1 windows are the exact same [0,3000) raw text, SHA256 bc0d510dbd6cde0530cf08684de455d82ec1943c0ba50cab130ae01990cc24b8. It names Riette Nel, formerly van Deventer, her mother Riana, and the claim that Errol Musk was also Riette's father. The birth-certificate paragraph says Riette was born Mariette van Deventer on August 8, 1975, immediately followed by 'Her mother was 21 when she gave birth'. Pronoun and parent/child ownership are explicit in adjacent sentences; this age is not Grimes's or another relative's age.

The same delivered window contains 'Sept. 17 2021, Published 2:29 p.m. ET', supporting the early-2020s article date despite the scraped metadata date being 2025-01-01. Both model answers preserve that this was an alleged relationship/claim; the text does not independently prove paternity. The requested reported maternal age is supported without treating the allegation as established fact.

## Conclusion

The submitted answer strings Vakkorama and 21 have direct source support in both arms. q778's final age attribution is fully clear; q771 pivot's explanatory claim about joint creation with Cem exceeds its exact cited windows. These controls show preserved short-path submissions with an inactive intervention. They establish neither an active recovery benefit nor complete verification of every locating clue.
