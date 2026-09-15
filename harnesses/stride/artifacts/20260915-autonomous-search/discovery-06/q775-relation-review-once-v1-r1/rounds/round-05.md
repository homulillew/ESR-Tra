# Round 5

[Actual request](../http/005/request.body) · [Actual response](../http/005/response.body) · [All interaction](../FULL_INTERACTION.md)

## Input visibility

```json
{
  "capacity": 74750,
  "compacted": true,
  "counter": {
    "calibrated_provider_tokens": false,
    "kind": "utf8_bytes"
  },
  "evidence_shelf": [],
  "final": false,
  "output_reservation": 4096,
  "request": "946e382c5ce51a11755e62302b08f0d027d1f69d3bfb1b595c0757a4c25409e4",
  "round": 5,
  "shelf_evicted_for_capacity": [],
  "visible_documents": [
    "d33",
    "d34",
    "d35",
    "d36",
    "d37",
    "d38",
    "d39",
    "d40",
    "d41",
    "d42",
    "d43",
    "d44",
    "d45",
    "d46",
    "d47",
    "d48",
    "d5",
    "d25",
    "d3",
    "d26",
    "d6",
    "d27",
    "d28",
    "d19",
    "d29",
    "d30",
    "d31",
    "d32",
    "d49",
    "d50",
    "d51",
    "d52"
  ],
  "visible_evidence": [
    "e1"
  ],
  "workflow_view": {
    "active_gap_not_verified": null,
    "available_pages_not_ranked_for_relevance": [
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d52"
        },
        "ref": "d52",
        "snippet": " ... Prophet Song by Paul Lynch + Book Club Discussion Guide\n\nBooker International Prize\n\nA counterpart to the Booker Prize, the International Booker Prize is a",
        "title": "https://bookclubs.com/blog/2023-2024-book-awards-and-book-prize-winners"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d51"
        },
        "ref": "d51",
        "snippet": " ... Each prize is a site where agents can convert different kinds of capital: sponsors swap cash for goodwill, winners can translate the glory of the prize int",
        "title": "https://giramondopublishing.com/heat/archive/beth-driscoll-how-prizes-work-in-the-literary-economy/"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d50"
        },
        "ref": "d50",
        "snippet": " ... for New Writing North's Read Regional campaign 2017 and won the Saboteur Award for Best Novella 2016. My first novel, Sealed (2017), is a work of eco-horro",
        "title": "https://www.durham.ac.uk/staff/naomi-r-booth/"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d49"
        },
        "ref": "d49",
        "snippet": " ... It was also shortlisted for the 2018 Saroyan Prize and longlisted for the 2018 PEN/Robert Bingham Prize for Debut Fiction and the 2017 Story Prize. Her nov",
        "title": "https://artsandsciences.syracuse.edu/english-department/creative-writing-mf-program/raymond-carver-reading-series/previous-raymond-carver-reading-series/"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d48"
        },
        "ref": "d48",
        "snippet": " ... That it was ever even published – earning the first of her two Booker shortlistings, in 2012 – owed to the disillusionment of former Amazon employee Stefan",
        "title": "https://www.theguardian.com/books/2023/jul/16/uk-indie-publishing-mavericks-shook-up-books-booker-nobel-fitzcarraldo-sort-of-books-daunt"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d47"
        },
        "ref": "d47",
        "snippet": " ... San Clemente Literary Prize\n*2011: David Cohen Prize for Literature\n*2011: Man Booker Prize, winner, The Sense of an Ending\n*2011 Costa Book Awards, shortl",
        "title": "https://en.wikipedia.org/wiki/Julian_Barnes"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d46"
        },
        "ref": "d46",
        "snippet": " ... Man Booker Prize (shortlist)\n* 2019 Pulitzer Prize for Fiction\n* 2019 PEN Oakland Josephine Miles Literary Award for The Overstory\n* 2020 William Dean Howe",
        "title": "https://en.wikipedia.org/wiki/Richard_Powers"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d45"
        },
        "ref": "d45",
        "snippet": " ... I, a great new African writer is asking these questions in a spare yet extraordinary novel about this bloody stain on human history.\"\n\n–Chigozie Obioma (Th",
        "title": "https://lithub.com/the-award-winning-novels-of-2021/"
      }
    ],
    "consecutive_repeat_rounds": 0,
    "contract": {
      "enabled": true,
      "gap_state": true,
      "guided_read": true,
      "recovery_rounds": 2,
      "repeat_threshold": 2,
      "repetition": "bounded",
      "reuse_results": true,
      "version": "gap-workflow-v1"
    },
    "instruction": "Use the current missing relation to choose a real next action. Page-name search is not page reading; cached is not proof of progress.",
    "last_new_navigation_source_round": 4,
    "last_new_raw_source_round": 3,
    "previous_gap_judgments_not_verified": [],
    "recovery_decisions_used": 0,
    "stage": "normal"
  }
}
```

## Complete model response

```json
{
  "choices": [
    {
      "finish_reason": "tool_calls",
      "index": 0,
      "message": {
        "content": "Let me reconsider the puzzle. The key constraint is \"the award itself was created in the 2000s.\" The Man Booker International Prize was created in 2005. Let me look at the International Booker Prize winners in the 2010s and find a book translated into 25+ languages that was a contender.\n\nLet me read the Booker Prize page to understand the International Booker Prize structure and winners.",
        "role": "assistant",
        "tool_calls": [
          {
            "function": {
              "arguments": "{\"ref\": \"d5\", \"start\": 0, \"length\": 6000}",
              "name": "read"
            },
            "id": "call_b50dfb22305142ac8de0873b",
            "index": 0,
            "type": "function"
          }
        ]
      }
    }
  ],
  "created": 1789475071,
  "id": "chatcmpl-b6535769-9b07-9947-b6b6-60e6a28ab7bb",
  "model": "glm-5.2",
  "object": "chat.completion",
  "usage": {
    "prompt_tokens": 17895,
    "completion_tokens": 105,
    "reasoning_tokens": 0,
    "total_tokens": 18000,
    "cached_tokens": 3328,
    "prompt_tokens_details": {
      "cached_tokens": 3328
    },
    "prompt_cost": 0.0,
    "completion_cost": 0.0,
    "cache_cost": 0.0
  }
}
```

## Executed action: read

```json
{
  "arguments": "{\"ref\": \"d5\", \"start\": 0, \"length\": 6000}",
  "documents": [],
  "evidence": [
    "e2"
  ],
  "executed": true,
  "result": {
    "action_slot_charged": true,
    "evidence": {
      "document": "d5",
      "document_chars": 27249,
      "end": 6000,
      "kind": "raw_evidence",
      "ref": "e2",
      "sha256": "3118b0cf3188b2c1bc346ebd555c23bd711d0976812419b78083850e13d790ea",
      "snapshot": "25e42c9d9629a06063929aefe4e8f050cac2c095d797b7476410c1a6fe277c5a",
      "start": 0,
      "text": "---\ntitle: Booker Prize - Wikipedia\nauthor: Authority control databases National Germany United States France BnF data Czech Republic Israel\ndate: 2001-10-18\n---\nname: The Booker Prize\nawarded_for: Best work of sustained fiction of the year, written in English and published in the UK or Ireland\nreward: £50, 000\npresenter: Booker, McConnell Ltd (1969–2001), Man Group (2002–2019), Crankstart (2019 onwards)\nlocation: Somerset House, Strand, London, England\nyear: 1969\nimagesize: 150px\n\nThe Booker Prize, formerly the Booker Prize for Fiction (1969–2001) and the Man Booker Prize (2002–2019), is a prestigious literary award conferred each year for the best single work of sustained fiction written in the English language, which was published in the United Kingdom or Ireland. The winner of the Booker Prize receives , as well as international publicity that usually leads to a significant sales boost. When the prize was created, only novels written by Commonwealth, Irish and South African (and later Zimbabwean) citizens were eligible to receive the prize; in 2014, eligibility was widened to any English-language novel—a change that proved controversial.\n\nA five-person panel consisting of authors, publishers and journalists, as well as politicians, actors, artists and musicians, is appointed by the Booker Prize Foundation each year to choose the winning book. Gaby Wood has been the chief executive of the Booker Prize Foundation since 2015.Gaby Wood at The Booker Prizes.Jennifer (20 April 2015), \"Booker Prize Foundation Hints at New Direction with Appointment of Gaby Wood as Literary Director\", Books Live, Sunday Times (South Africa).\n\nA high-profile literary award in British culture, the Booker Prize is greeted with anticipation and fanfare around the world. Literary critics have noted that it is a mark of distinction for authors to be selected for inclusion in the shortlist or to be nominated for the \"longlist\".\n\nA sister prize, the International Booker Prize, is awarded for a work of fiction translated into English and published in the United Kingdom or Ireland. Unlike the Booker Prize, short story collections are eligible for the International Booker Prize. The £50,000 prize money is split evenly between the author and translator of the winning novel.\n\nHistory and administration\n\nThe prize was established as the \"Booker Prize for Fiction\" after the company Booker, McConnell Ltd began sponsoring the event in 1969; it became commonly known as the \"Booker Prize\" or the \"Booker\". Jock Campbell, Charles Tyrrell and Tom Maschler were instrumental in establishing the prize.\n\nWhen administration of the prize was transferred to the Booker Prize Foundation in 2002, the title sponsor became the investment company Man Group, which opted to retain \"Booker\" as part of the official title of the prize. The foundation is an independent registered charity funded by the entire profits of Booker Prize Trading Ltd, of which it is the sole shareholder. The prize money awarded with the Booker Prize was originally £5,000. It doubled in 1978 to £10,000 and was subsequently raised to £50,000 in 2002 under the sponsorship of the Man Group, making it one of the world's richest literary prizes. Each of the shortlisted authors receives £2,500 and a specially bound edition of their book.\n\nThe original Booker Prize trophy was designed by the artist Jan Pieńkowski and the design was revived for the 2023 prize.\n\n1969–1979\n\nThe first winner of the Booker Prize was P. H. Newby in 1969 for his novel Something to Answer For. W. L. Webb, The Guardians Literary Editor, was chair of the inaugural set of judges, which included Rebecca West, Stephen Spender, Frank Kermode and David Farrer.\n\nIn 1970, the prize's second year, Bernice Rubens became the first woman to win the Booker Prize, for The Elected Member.Kidd, James (5 March 2006), \"A Brief History of The Man Booker Prize\", South China Morning Post.\n\nThe rules of the Booker changed in 1971; previously, it had been given retrospectively, to books published in the year prior to each award. In 1971, eligibility was changed to make the year of a novel's publication the same as the year of the award, which was made in November; in effect, this meant that books published in 1970 were not considered for the Booker in either year. Forty years later, the Booker Prize Foundation announced in January 2010 the creation of a special award called the \"Lost Man Booker Prize\", with the winner chosen from a longlist of 22 novels published in 1970. The prize was won by J. G. Farrell for Troubles, though the author had died in 1979.\n\nIn 1972, winning writer John Berger, known for his Marxist worldview, protested during his acceptance speech against Booker McConnell. He blamed Booker's 130 years of sugar production in the Caribbean for the region's modern poverty.\"John Berger on the Booker Prize (1972)\", YouTube. Berger donated half of his £5,000 prize to the British Black Panther movement, because it had a socialist and revolutionary perspective in agreement with his own. p. 11.Speech by John Berger on accepting the Booker Prize for Fiction at the Café Royal in London on 23 November 1972. The Booker Prizes, 24 November 2022.\n\n1980–1999\n\nIn 1980, Anthony Burgess, writer of Earthly Powers, refused to attend the ceremony unless it was confirmed to him in advance whether he had won. His was one of two books considered likely to win, the other being Rites of Passage by William Golding. The judges decided only 30 minutes before the ceremony, giving the prize to Golding. Both novels had been seen as favourites to win leading up to the prize, and the dramatic \"literary battle\" between two senior writers made front-page news. p. 1.\n\nAlice Munro's The Beggar Maid was shortlisted in 1980, and remains the only short-story collection to be shortlisted.\n\nIn 1981, nominee John Banville wrote a letter to The Guardian requesting that the prize be given to him so that he could use the money to buy every copy of the longli"
    },
    "executed": true,
    "next_start": 6000,
    "ok": true,
    "previously_received": false
  },
  "round": 5,
  "tool": "read",
  "tool_call_id": "call_b50dfb22305142ac8de0873b"
}
```

## Full event records for this request interval

```json
[
  {
    "seq": 128,
    "kind": "model_request",
    "payload": {
      "capacity": 74750,
      "compacted": true,
      "counter": {
        "calibrated_provider_tokens": false,
        "kind": "utf8_bytes"
      },
      "evidence_shelf": [],
      "final": false,
      "output_reservation": 4096,
      "request": "946e382c5ce51a11755e62302b08f0d027d1f69d3bfb1b595c0757a4c25409e4",
      "round": 5,
      "shelf_evicted_for_capacity": [],
      "visible_documents": [
        "d33",
        "d34",
        "d35",
        "d36",
        "d37",
        "d38",
        "d39",
        "d40",
        "d41",
        "d42",
        "d43",
        "d44",
        "d45",
        "d46",
        "d47",
        "d48",
        "d5",
        "d25",
        "d3",
        "d26",
        "d6",
        "d27",
        "d28",
        "d19",
        "d29",
        "d30",
        "d31",
        "d32",
        "d49",
        "d50",
        "d51",
        "d52"
      ],
      "visible_evidence": [
        "e1"
      ],
      "workflow_view": {
        "active_gap_not_verified": null,
        "available_pages_not_ranked_for_relevance": [
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d52"
            },
            "ref": "d52",
            "snippet": " ... Prophet Song by Paul Lynch + Book Club Discussion Guide\n\nBooker International Prize\n\nA counterpart to the Booker Prize, the International Booker Prize is a",
            "title": "https://bookclubs.com/blog/2023-2024-book-awards-and-book-prize-winners"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d51"
            },
            "ref": "d51",
            "snippet": " ... Each prize is a site where agents can convert different kinds of capital: sponsors swap cash for goodwill, winners can translate the glory of the prize int",
            "title": "https://giramondopublishing.com/heat/archive/beth-driscoll-how-prizes-work-in-the-literary-economy/"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d50"
            },
            "ref": "d50",
            "snippet": " ... for New Writing North's Read Regional campaign 2017 and won the Saboteur Award for Best Novella 2016. My first novel, Sealed (2017), is a work of eco-horro",
            "title": "https://www.durham.ac.uk/staff/naomi-r-booth/"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d49"
            },
            "ref": "d49",
            "snippet": " ... It was also shortlisted for the 2018 Saroyan Prize and longlisted for the 2018 PEN/Robert Bingham Prize for Debut Fiction and the 2017 Story Prize. Her nov",
            "title": "https://artsandsciences.syracuse.edu/english-department/creative-writing-mf-program/raymond-carver-reading-series/previous-raymond-carver-reading-series/"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d48"
            },
            "ref": "d48",
            "snippet": " ... That it was ever even published – earning the first of her two Booker shortlistings, in 2012 – owed to the disillusionment of former Amazon employee Stefan",
            "title": "https://www.theguardian.com/books/2023/jul/16/uk-indie-publishing-mavericks-shook-up-books-booker-nobel-fitzcarraldo-sort-of-books-daunt"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d47"
            },
            "ref": "d47",
            "snippet": " ... San Clemente Literary Prize\n*2011: David Cohen Prize for Literature\n*2011: Man Booker Prize, winner, The Sense of an Ending\n*2011 Costa Book Awards, shortl",
            "title": "https://en.wikipedia.org/wiki/Julian_Barnes"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d46"
            },
            "ref": "d46",
            "snippet": " ... Man Booker Prize (shortlist)\n* 2019 Pulitzer Prize for Fiction\n* 2019 PEN Oakland Josephine Miles Literary Award for The Overstory\n* 2020 William Dean Howe",
            "title": "https://en.wikipedia.org/wiki/Richard_Powers"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d45"
            },
            "ref": "d45",
            "snippet": " ... I, a great new African writer is asking these questions in a spare yet extraordinary novel about this bloody stain on human history.\"\n\n–Chigozie Obioma (Th",
            "title": "https://lithub.com/the-award-winning-novels-of-2021/"
          }
        ],
        "consecutive_repeat_rounds": 0,
        "contract": {
          "enabled": true,
          "gap_state": true,
          "guided_read": true,
          "recovery_rounds": 2,
          "repeat_threshold": 2,
          "repetition": "bounded",
          "reuse_results": true,
          "version": "gap-workflow-v1"
        },
        "instruction": "Use the current missing relation to choose a real next action. Page-name search is not page reading; cached is not proof of progress.",
        "last_new_navigation_source_round": 4,
        "last_new_raw_source_round": 3,
        "previous_gap_judgments_not_verified": [],
        "recovery_decisions_used": 0,
        "stage": "normal"
      }
    },
    "previous": "430e60cb55b31f92fd9371b02b06c7fd0e93e4ab0ff3d45670214cb6be5fd8b8",
    "hash": "4fc4690f081bfcc6577fce0d53cac88278f7afc852b42a8b3b33eea41c120873"
  },
  {
    "seq": 129,
    "kind": "model_response",
    "payload": {
      "elapsed_seconds": 4.782344400009606,
      "output_charged": 105,
      "raw": "32cc2c3bd87775412506c27e51349fbf0e93e81e15d9d8b54515dfe7b5b0bda5",
      "response_model": "glm-5.2",
      "round": 5,
      "usage": {
        "cache_read_tokens": 3328,
        "input_tokens": 17895,
        "output_tokens": 105
      }
    },
    "previous": "4fc4690f081bfcc6577fce0d53cac88278f7afc852b42a8b3b33eea41c120873",
    "hash": "89ec2a787fdd43d4dcdef75d9278f66de145fcd81c4dca030e2a1487888b5ae2"
  },
  {
    "seq": 130,
    "kind": "delivery_ack",
    "payload": {
      "documents": [
        "d33",
        "d34",
        "d35",
        "d36",
        "d37",
        "d38",
        "d39",
        "d40",
        "d41",
        "d42",
        "d43",
        "d44",
        "d45",
        "d46",
        "d47",
        "d48",
        "d5",
        "d25",
        "d3",
        "d26",
        "d6",
        "d27",
        "d28",
        "d19",
        "d29",
        "d30",
        "d31",
        "d32",
        "d49",
        "d50",
        "d51",
        "d52"
      ],
      "evidence": [
        "e1"
      ],
      "round": 5
    },
    "previous": "89ec2a787fdd43d4dcdef75d9278f66de145fcd81c4dca030e2a1487888b5ae2",
    "hash": "b17a9aa0b4c332a59a3a077ef72cc8d0afb05433b4e84dea49efb936cc5ace4a"
  },
  {
    "seq": 131,
    "kind": "navigation_ack",
    "payload": {
      "object": "2af5feffddb90fc2e645dafcfc5e8ce69caf5b46ad6e80046127e366b1ef9871",
      "round": 5,
      "source_round": 4
    },
    "previous": "b17a9aa0b4c332a59a3a077ef72cc8d0afb05433b4e84dea49efb936cc5ace4a",
    "hash": "e512d8eef116b660071d4fde053e729a2e74a2703f82ab16991d03a8e5e5a739"
  },
  {
    "seq": 132,
    "kind": "backend_request",
    "payload": {
      "arguments": {
        "docid": "3002"
      },
      "kind": "get_document",
      "number": 14
    },
    "previous": "e512d8eef116b660071d4fde053e729a2e74a2703f82ab16991d03a8e5e5a739",
    "hash": "d9286b5dbfc0d49fc201ab3a3a7dc055369a0b6320e88b5ec3ba8508e0f23f85"
  },
  {
    "seq": 133,
    "kind": "backend_response",
    "payload": {
      "elapsed_seconds": 0.003402700007427484,
      "kind": "get_document",
      "object": "4f85c91a574746f8d58a8d5113167c456d9638def82bdcb3c6ecca939f58408e",
      "raw_wire": "4f85c91a574746f8d58a8d5113167c456d9638def82bdcb3c6ecca939f58408e",
      "wire_request": {
        "docid": "3002",
        "kind": "local_sql"
      }
    },
    "previous": "d9286b5dbfc0d49fc201ab3a3a7dc055369a0b6320e88b5ec3ba8508e0f23f85",
    "hash": "7b2a828b59465f474176832abc29f809afbe1c3d40c7bba1a0f137c08dee5355"
  },
  {
    "seq": 134,
    "kind": "snapshot",
    "payload": {
      "characters": 27249,
      "document": "d5",
      "object": "25e42c9d9629a06063929aefe4e8f050cac2c095d797b7476410c1a6fe277c5a"
    },
    "previous": "7b2a828b59465f474176832abc29f809afbe1c3d40c7bba1a0f137c08dee5355",
    "hash": "d7e3d31fcbdc0edff2dc9e9952bccdb30423344ba6ae14c738409d069185cdc4"
  },
  {
    "seq": 135,
    "kind": "evidence_registered",
    "payload": {
      "document": "d5",
      "end": 6000,
      "ref": "e2",
      "sha256": "3118b0cf3188b2c1bc346ebd555c23bd711d0976812419b78083850e13d790ea",
      "snapshot": "25e42c9d9629a06063929aefe4e8f050cac2c095d797b7476410c1a6fe277c5a",
      "start": 0
    },
    "previous": "d7e3d31fcbdc0edff2dc9e9952bccdb30423344ba6ae14c738409d069185cdc4",
    "hash": "1ceb4ff31a802aaf0b4676578f66d65fb4ebac76874c069d87f47d7a80ffa70d"
  },
  {
    "seq": 136,
    "kind": "action_execution",
    "payload": {
      "object": "f04bdb9aa02326e86e3a8bef0551803f34c730fcd4b3d43bb8124fc9cc812994",
      "round": 5,
      "tool_call_id": "call_b50dfb22305142ac8de0873b"
    },
    "previous": "1ceb4ff31a802aaf0b4676578f66d65fb4ebac76874c069d87f47d7a80ffa70d",
    "hash": "b3bab9b653407dd0bcaf4a00bba8604195c97f4ff9e850a02cbc41abfac76222"
  },
  {
    "seq": 137,
    "kind": "delivery_preflight",
    "payload": {
      "documents": [],
      "evidence": [
        "e2"
      ],
      "fits": true,
      "phase": "RESEARCH",
      "round": 5
    },
    "previous": "b3bab9b653407dd0bcaf4a00bba8604195c97f4ff9e850a02cbc41abfac76222",
    "hash": "4c9d821b07b1f20d070d7cea68d563df3a0fbb8499f5a4682c9cd3d21d50fffd"
  },
  {
    "seq": 138,
    "kind": "action_result",
    "payload": {
      "arguments": "{\"ref\": \"d5\", \"start\": 0, \"length\": 6000}",
      "executed": true,
      "result": {
        "action_slot_charged": true,
        "evidence": {
          "document": "d5",
          "document_chars": 27249,
          "end": 6000,
          "kind": "raw_evidence",
          "ref": "e2",
          "sha256": "3118b0cf3188b2c1bc346ebd555c23bd711d0976812419b78083850e13d790ea",
          "snapshot": "25e42c9d9629a06063929aefe4e8f050cac2c095d797b7476410c1a6fe277c5a",
          "start": 0,
          "text": "---\ntitle: Booker Prize - Wikipedia\nauthor: Authority control databases National Germany United States France BnF data Czech Republic Israel\ndate: 2001-10-18\n---\nname: The Booker Prize\nawarded_for: Best work of sustained fiction of the year, written in English and published in the UK or Ireland\nreward: £50, 000\npresenter: Booker, McConnell Ltd (1969–2001), Man Group (2002–2019), Crankstart (2019 onwards)\nlocation: Somerset House, Strand, London, England\nyear: 1969\nimagesize: 150px\n\nThe Booker Prize, formerly the Booker Prize for Fiction (1969–2001) and the Man Booker Prize (2002–2019), is a prestigious literary award conferred each year for the best single work of sustained fiction written in the English language, which was published in the United Kingdom or Ireland. The winner of the Booker Prize receives , as well as international publicity that usually leads to a significant sales boost. When the prize was created, only novels written by Commonwealth, Irish and South African (and later Zimbabwean) citizens were eligible to receive the prize; in 2014, eligibility was widened to any English-language novel—a change that proved controversial.\n\nA five-person panel consisting of authors, publishers and journalists, as well as politicians, actors, artists and musicians, is appointed by the Booker Prize Foundation each year to choose the winning book. Gaby Wood has been the chief executive of the Booker Prize Foundation since 2015.Gaby Wood at The Booker Prizes.Jennifer (20 April 2015), \"Booker Prize Foundation Hints at New Direction with Appointment of Gaby Wood as Literary Director\", Books Live, Sunday Times (South Africa).\n\nA high-profile literary award in British culture, the Booker Prize is greeted with anticipation and fanfare around the world. Literary critics have noted that it is a mark of distinction for authors to be selected for inclusion in the shortlist or to be nominated for the \"longlist\".\n\nA sister prize, the International Booker Prize, is awarded for a work of fiction translated into English and published in the United Kingdom or Ireland. Unlike the Booker Prize, short story collections are eligible for the International Booker Prize. The £50,000 prize money is split evenly between the author and translator of the winning novel.\n\nHistory and administration\n\nThe prize was established as the \"Booker Prize for Fiction\" after the company Booker, McConnell Ltd began sponsoring the event in 1969; it became commonly known as the \"Booker Prize\" or the \"Booker\". Jock Campbell, Charles Tyrrell and Tom Maschler were instrumental in establishing the prize.\n\nWhen administration of the prize was transferred to the Booker Prize Foundation in 2002, the title sponsor became the investment company Man Group, which opted to retain \"Booker\" as part of the official title of the prize. The foundation is an independent registered charity funded by the entire profits of Booker Prize Trading Ltd, of which it is the sole shareholder. The prize money awarded with the Booker Prize was originally £5,000. It doubled in 1978 to £10,000 and was subsequently raised to £50,000 in 2002 under the sponsorship of the Man Group, making it one of the world's richest literary prizes. Each of the shortlisted authors receives £2,500 and a specially bound edition of their book.\n\nThe original Booker Prize trophy was designed by the artist Jan Pieńkowski and the design was revived for the 2023 prize.\n\n1969–1979\n\nThe first winner of the Booker Prize was P. H. Newby in 1969 for his novel Something to Answer For. W. L. Webb, The Guardians Literary Editor, was chair of the inaugural set of judges, which included Rebecca West, Stephen Spender, Frank Kermode and David Farrer.\n\nIn 1970, the prize's second year, Bernice Rubens became the first woman to win the Booker Prize, for The Elected Member.Kidd, James (5 March 2006), \"A Brief History of The Man Booker Prize\", South China Morning Post.\n\nThe rules of the Booker changed in 1971; previously, it had been given retrospectively, to books published in the year prior to each award. In 1971, eligibility was changed to make the year of a novel's publication the same as the year of the award, which was made in November; in effect, this meant that books published in 1970 were not considered for the Booker in either year. Forty years later, the Booker Prize Foundation announced in January 2010 the creation of a special award called the \"Lost Man Booker Prize\", with the winner chosen from a longlist of 22 novels published in 1970. The prize was won by J. G. Farrell for Troubles, though the author had died in 1979.\n\nIn 1972, winning writer John Berger, known for his Marxist worldview, protested during his acceptance speech against Booker McConnell. He blamed Booker's 130 years of sugar production in the Caribbean for the region's modern poverty.\"John Berger on the Booker Prize (1972)\", YouTube. Berger donated half of his £5,000 prize to the British Black Panther movement, because it had a socialist and revolutionary perspective in agreement with his own. p. 11.Speech by John Berger on accepting the Booker Prize for Fiction at the Café Royal in London on 23 November 1972. The Booker Prizes, 24 November 2022.\n\n1980–1999\n\nIn 1980, Anthony Burgess, writer of Earthly Powers, refused to attend the ceremony unless it was confirmed to him in advance whether he had won. His was one of two books considered likely to win, the other being Rites of Passage by William Golding. The judges decided only 30 minutes before the ceremony, giving the prize to Golding. Both novels had been seen as favourites to win leading up to the prize, and the dramatic \"literary battle\" between two senior writers made front-page news. p. 1.\n\nAlice Munro's The Beggar Maid was shortlisted in 1980, and remains the only short-story collection to be shortlisted.\n\nIn 1981, nominee John Banville wrote a letter to The Guardian requesting that the prize be given to him so that he could use the money to buy every copy of the longli"
        },
        "executed": true,
        "next_start": 6000,
        "ok": true,
        "previously_received": false
      },
      "round": 5,
      "tool": "read",
      "tool_call_id": "call_b50dfb22305142ac8de0873b"
    },
    "previous": "4c9d821b07b1f20d070d7cea68d563df3a0fbb8499f5a4682c9cd3d21d50fffd",
    "hash": "90caed62c9e938f089a670ae8aef1d1ce3d5f0e4e5a55d80d245661fa18f355c"
  },
  {
    "seq": 139,
    "kind": "round_end",
    "payload": {
      "group": "1ccdcd51a1ba8b58c01f4d56809a25c39793d15c06ead0b89ecc0c7c43f565bb",
      "notes": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
      "remaining": {
        "action_slots": 194,
        "backend_calls": 106,
        "model_calls": 11,
        "output_reservation": 46996
      },
      "round": 5
    },
    "previous": "90caed62c9e938f089a670ae8aef1d1ce3d5f0e4e5a55d80d245661fa18f355c",
    "hash": "9b68abcbeeafffd12af0fe490de9bf1f0ceee1160d42f33c483a47e019957694"
  }
]
```
