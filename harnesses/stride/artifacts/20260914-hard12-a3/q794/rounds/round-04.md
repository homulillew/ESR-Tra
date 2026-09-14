# Round 4

[Actual request](../http/004/request.body) · [Actual response](../http/004/response.body) · [All interaction](../FULL_INTERACTION.md)

## Input visibility

```json
{
  "capacity": 57803,
  "compacted": false,
  "counter": {
    "calibrated_provider_tokens": false,
    "kind": "utf8_bytes"
  },
  "evidence_shelf": [],
  "final": false,
  "output_reservation": 4096,
  "request": "3e0b92229007f74101223732da9d0a727cbe4775d87f42df90b9a597acf23535",
  "round": 4,
  "shelf_evicted_for_capacity": [],
  "visible_documents": [
    "d1",
    "d2",
    "d3",
    "d4",
    "d5",
    "d6",
    "d7",
    "d8",
    "d9",
    "d10",
    "d11",
    "d12",
    "d13",
    "d14",
    "d15",
    "d16",
    "d17"
  ],
  "visible_evidence": []
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
        "content": "Let me search for snooker referees who became international referees in December, and look at detailed match scorecards with frame-by-frame breaks.",
        "role": "assistant",
        "tool_calls": [
          {
            "function": {
              "arguments": "{\"queries\": [\"snooker referee international referee December 2014 2015 2016 2017 2018 2019 2020 2021\", \"snooker referee became international referee December year\", \"snooker referee international qualification December before 2022\"]}",
              "name": "search"
            },
            "id": "call_e04bfbd722614233bdd13111",
            "index": 0,
            "type": "function"
          },
          {
            "function": {
              "arguments": "{\"queries\": [\"snooker match scorecard frame breaks 50 60 70 90 100 century detailed\", \"snooker match two centuries 70s breaks 60s breaks 50s break scorecard\", \"snooker championship match detailed frame scores breaks list\"]}",
              "name": "search"
            },
            "id": "call_a97922f1f95b4e9aa99f5650",
            "index": 1,
            "type": "function"
          }
        ]
      }
    }
  ],
  "created": 1789382424,
  "id": "chatcmpl-4240c056-55c1-9bd4-9707-ebb812d82b86",
  "model": "glm-5.2",
  "object": "chat.completion",
  "usage": {
    "prompt_tokens": 14885,
    "completion_tokens": 157,
    "reasoning_tokens": 0,
    "total_tokens": 15042,
    "cached_tokens": 9728,
    "prompt_tokens_details": {
      "cached_tokens": 9728
    },
    "prompt_cost": 0.0,
    "completion_cost": 0.0,
    "cache_cost": 0.0
  }
}
```

## Executed action: search

```json
{
  "arguments": "{\"queries\": [\"snooker referee international referee December 2014 2015 2016 2017 2018 2019 2020 2021\", \"snooker referee became international referee December year\", \"snooker referee international qualification December before 2022\"]}",
  "documents": [
    "d12",
    "d8",
    "d4",
    "d16",
    "d3",
    "d8",
    "d2",
    "d9",
    "d10",
    "d11",
    "d3",
    "d8",
    "d2",
    "d4",
    "d18"
  ],
  "evidence": [],
  "executed": true,
  "result": {
    "action_slot_charged": true,
    "executed": true,
    "ok": true,
    "results": [
      {
        "cached": false,
        "hits": [
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d12",
            "snippet": " ... 2015–16 season | 824 |\n| 2016 European Masters | 2 |\n| 2016 English Open | 1 |\n| 2016 International Championship | 2 |\n| 2016 Champion of Champions | 6 |\n| 2016 Northern Ireland Open | 6 |\n| 2016 UK Championship | 10 |\n| 2016 Scottish Open | 4 |\n| 2017 Masters | 3 |\n| 2017 German Masters | 1 |\n| 2017 World Grand Prix | 2 |\n| 2017 Welsh ... ",
            "title": "https://en.wikipedia.org/wiki/Maximum_and_century_breaks_made_by_Ronnie_O%27Sullivan"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d8",
            "snippet": " ... referee European and international matches. In 2015, he officiated the Football League Cup final at Wembley Stadium when Chelsea defeated Tottenham Hotspur 2–0. Taylor returned to Wembley later that year to officiate the Community Shield as Arsenal beat Chelsea 1–0. He refereed the 2017 and 2020 ... ",
            "title": "https://pantheon.world/profile/occupation/referee/country/united-kingdom"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d4",
            "snippet": " ... maximum breaks order:\n\n| Year | 147s |\n\n|---|---|\n\n| 2024 | 14 |\n\n| 2018 | 12 |\n\n| 2022 | 11 |\n\n| 2012 | 11 |\n\n| 2023 | 11 |\n\n| 2016 | 10 |\n\n| 1999 | 10 |\n\n| 2025 | 9 |\n\n| 2020 | 9 |\n\n| 2019 | 9 |\n\n| 2011 | 9 |\n\n| 2021 | 8 |\n\n| 2017 | 8 |\n\n| 2014 | 8 |\n\n| 2010 | 7 |\n\n| 2008 | 7 |\n\n| 2000 | 7 |\n\n| 2015 | 6 |\n\n| 2013 | 6 |\n\n| 2007 | 6 |\n\n| 1992 | 5 |\n\n| 2001 ... ",
            "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d16",
            "snippet": " ... 1) | Rob Spencer (4) | 2017 |\n\n| 133 | Kyren Wilson (1) | International Championship | Martin Gould (2) | Shen Yifei (1) | 2017 |\n\n| 134 | Cao Yupeng (1) | Scottish Open | Andrew Higginson (1) | Rob Spencer (5) | 2017 |\n\n| 135 | Martin Gould (1) | Championship League | Li Hang (1) | Brendan Moore (7) | 2018 |\n\n| 136 | Luca Brecel (1 ... ",
            "title": "https://wpbsa.com/about-us/history/147-breaks/"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d3",
            "snippet": " ... 2022 World Snooker Championship - Wikipedia\ndate: 2021-05-03\n---\ntournament_name: 2022 Betfred World Snooker Championship\nlogo: World Snooker Championship 2015 Logo.png\ndates: 16 April 2022\nvenue: Crucible Theatre\nlocation: Sheffield\ncountry: England\norganisation: World Snooker Tour\nformat: Ranking event\ntotal prize fund: £2, 395, 000\nwinners ... ",
            "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
          }
        ],
        "query": "snooker referee international referee December 2014 2015 2016 2017 2018 2019 2020 2021"
      },
      {
        "cached": true,
        "hits": [
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d8",
            "snippet": " ... She qualified in 2001 to referee on the World Snooker Tour and was the sport's highest profile female referee for the next 14 years. She became the first woman to officiate at a professional ranking snooker tournament at the 2002 Welsh Open, and the first woman to ... ",
            "title": "https://pantheon.world/profile/occupation/referee/country/united-kingdom"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d2",
            "snippet": " ... The event's referees wore suits tailored by McCann Bespoke, as part of the London tailor's new partnership with the World Snooker Tour that is intended to restyle the appearance of referees and players.\n\nThe tournament was broadcast live in the United Kingdom by BBC Sport, as ... ",
            "title": "https://en.wikipedia.org/wiki/2022_Masters_(snooker)"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d9",
            "snippet": " ... This is to prevent the score difference from decreasing too much, at the referee's discretion.\n# If it is physically impossible to play a legal shot (the snooker is truly inescapable, as judged by the referee). The player must still put sufficient strength into the shot so that ... ",
            "title": "https://en.wikipedia.org/wiki/Rules_of_snooker"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d10",
            "snippet": " ... I think it probably goes back a couple hundred years, to before Snooker even became a thing and the players played the \"pool\" games: pyramid pool, life pool, black pool. These were usually more than two players and were centered on the bets that were placed and the ... ",
            "title": "https://www.snookerisland.com/forum/viewtopic.php?f=468&t=6542"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d11",
            "snippet": " ... Snookered After a Foul\n\nAfter a foul, if the cue-ball is snookered, the referee shall state FREE BALL (see Section 2, Rule 16).\n\n(a) If the player next in turn elects to play the next stroke,\n\n(I) he may nominate any ball as the ball on, and ... ",
            "title": "https://club-snooker.web.cern.ch/club-snooker/rules.html"
          }
        ],
        "query": "snooker referee became international referee December year"
      },
      {
        "cached": false,
        "hits": [
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d3",
            "snippet": " ... At the end of the year, the World Snooker Tour ranked the semi-final between Trump and Williams in second place on its \"Top Ten Matches of 2022\" list.\n\nO'Sullivan and Higgins met at the Crucible for a sixth time. Before the semi-final, O'Sullivan led ... ",
            "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d8",
            "snippet": " ... since June 2022.\n\n8. Michaela Tabb (b. 1967)\n\nWith an HPI of 44.26, Michaela Tabb is the 8th most famous British Referee. Her biography has been translated into 15 different languages.\n\nMichaela Tabb (born 11 December 1967) is a Scottish snooker and pool referee. She established significant ... ",
            "title": "https://pantheon.world/profile/occupation/referee/country/united-kingdom"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d2",
            "snippet": " ... 2022 Masters (snooker) - Wikipedia\ndate: 2021-04-15\n---\ntournament_name: 2022 Cazoo Masters\nlogo: 270px\nalt: Masters Snooker event promotional logo\ndates: 9 January 2022\nvenue: Alexandra Palace\nlocation: London\ncountry: England\norganisation: World Snooker Tour\nformat: Non-ranking event\ntotal prize fund: £725, 000\nwinners_share: £250 ... ",
            "title": "https://en.wikipedia.org/wiki/2022_Masters_(snooker)"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d4",
            "snippet": " ... Who made the 100th 147 Break in Snooker?\n\nMark Selby was the player to make the 100th 147 break in snooker at the UK championship on 7th December 2013 against Ricky Walden. Selby's 2nd maximum followed his first on 5th June 2009 against Joe Perry in the ... ",
            "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": false,
            "ref": "d18",
            "snippet": " ... international visitors\" in China. The races were supposed to be held 19–21 March, and would have acted as a dress rehearsal for the upcoming 2022 Winter Olympics in Beijing. The FIS said they would be looking for a replacement host for the races.\n\nOn 9 December, the ... ",
            "title": "https://en.wikipedia.org/wiki/Impact_of_the_COVID-19_pandemic_on_sports"
          }
        ],
        "query": "snooker referee international qualification December before 2022"
      }
    ]
  },
  "round": 4,
  "tool": "search",
  "tool_call_id": "call_e04bfbd722614233bdd13111"
}
```

## Executed action: search

```json
{
  "arguments": "{\"queries\": [\"snooker match scorecard frame breaks 50 60 70 90 100 century detailed\", \"snooker match two centuries 70s breaks 60s breaks 50s break scorecard\", \"snooker championship match detailed frame scores breaks list\"]}",
  "documents": [
    "d1",
    "d2",
    "d4",
    "d3",
    "d17",
    "d2",
    "d3",
    "d1",
    "d5",
    "d12",
    "d4",
    "d2",
    "d3",
    "d12",
    "d7"
  ],
  "evidence": [],
  "executed": true,
  "result": {
    "action_slot_charged": true,
    "executed": true,
    "ok": true,
    "results": [
      {
        "cached": false,
        "hits": [
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d1",
            "snippet": " ... Pages\n\n-\n\nPlayer Profile\n\nTournament Record\n\nMost Frequent Opponents\n\nRounds Reached\n\nCentury Frequency\n\nCenturies per Season Graph\n\nRanking History\n\nPrize Money History\n\nBreaks\n\n| 50s | 60s | 70s | 80s | 90s | 100s | Total | |\n\n|---|---|---|---|---|---|---|---|\n\n| Breaks | 35 | 23 | 31 | 16 | 11 | 23 | 139 |\n\n| Frame rate | 15.46 | 23.52 | 17.45 | 33.81 | 49 ... ",
            "title": "https://cuetracker.net/players/julien-leclercq/career-total-statistics"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d2",
            "snippet": " ... 100,000\n* Semi-finals: £60,000\n* Quarter-finals: £30,000\n* Last 16: £15,000\n* Highest break: £15,000\n* Total: £725,000\n\nSummary\n\nFirst round\n\nThe first round was played between 9 and 12 January 2022 as the best-of-11 frames. In the opening afternoon's match, defending ... ",
            "title": "https://en.wikipedia.org/wiki/2022_Masters_(snooker)"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d4",
            "snippet": " ... 90s\n\n7 of the Best Snooker Matches of the 80's & 90's\n\nEvery Competitive 147 in Snooker History\n\nIf you have got this far you must love your snooker, and to save you going off to find evermore detail, we have a list of every 147 break ... ",
            "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d3",
            "snippet": " ... The match featured five centuries and 12 more breaks over 50. Before his match with Vafaei, 2019 champion Judd Trump stated that he had not been enjoying his snooker and did not have high expectations for the World Championship. The scores were tied at 3–3, but Trump ... ",
            "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d17",
            "snippet": " ... The match was drawn. Scorecard | Birmingham | 1994 |\n\nMost runs in a career\n\nQualification: 40,000.\n\n**Table 8**\n\n| Runs | Player | Innings | Matches | Average | Career span |\n|---|---|---|---|---|---|\n| 61,760 | Jack Hobbs (Surrey and England) | 1,325 | 834 | 50.70 | from 1905 to 1934 |\n| 58,959 | Frank Woolley (Kent and England) | 1 ... ",
            "title": "https://en.wikipedia.org/wiki/List_of_first-class_cricket_records"
          }
        ],
        "query": "snooker match scorecard frame breaks 50 60 70 90 100 century detailed"
      },
      {
        "cached": true,
        "hits": [
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d2",
            "snippet": " ... Robertson compiled two centuries and six other breaks of 50 or more in the final, while Hawkins made just two breaks over 50. Hawkins acknowledged that his performance in the final had been substandard, saying: \"I made too many mistakes today and you can't do that against ... ",
            "title": "https://en.wikipedia.org/wiki/2022_Masters_(snooker)"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d3",
            "snippet": " ... The match featured five centuries and 12 more breaks over 50. Before his match with Vafaei, 2019 champion Judd Trump stated that he had not been enjoying his snooker and did not have high expectations for the World Championship. The scores were tied at 3–3, but Trump ... ",
            "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d1",
            "snippet": " ... as professional: | 3 |\n\nAdditional Pages\n\n-\n\nPlayer Profile\n\nTournament Record\n\nMost Frequent Opponents\n\nRounds Reached\n\nCentury Frequency\n\nCenturies per Season Graph\n\nRanking History\n\nPrize Money History\n\nBreaks\n\n| 50s | 60s | 70s | 80s | 90s | 100s | Total | |\n\n|---|---|---|---|---|---|---|---|\n\n| Breaks | 35 | 23 | 31 | 16 | 11 | 23 | 139 |\n\n| Frame rate | 15.46 | 23.52 | 17 ... ",
            "title": "https://cuetracker.net/players/julien-leclercq/career-total-statistics"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d5",
            "snippet": " ... Coventry\n\n- Snooker Idol: Hendry and Trump\n\n- Highest Break: 30\n\n- Walk-On: Simple Minds- Glittering Prize\n\n-\n\nby Pink Ball » 15 Apr 2022 Read\n\nThe honourable mentions, the matches that didn't make the top 50:\n\n54.Classic final 1985: Jimmy White 13-12 Cliff Thorburn (6 points)\n\n55. World ... ",
            "title": "https://www.snookerisland.com/forum/viewtopic.php?f=25&t=11961"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d12",
            "snippet": " ... O'Sullivan had made 773 century breaks at the start of 2015. On 13 January, in the first round of the 2015 Masters, he made two centuries to equal Stephen Hendry's record of 775. Two days later, in his second-round match, he made his 776th century ... ",
            "title": "https://en.wikipedia.org/wiki/Maximum_and_century_breaks_made_by_Ronnie_O%27Sullivan"
          }
        ],
        "query": "snooker match two centuries 70s breaks 60s breaks 50s break scorecard"
      },
      {
        "cached": true,
        "hits": [
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d4",
            "snippet": " ... Best Snooker Matches of the 80's & 90's\n\nEvery Competitive 147 in Snooker History\n\nIf you have got this far you must love your snooker, and to save you going off to find evermore detail, we have a list of every 147 break made in snooker history ... ",
            "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d2",
            "snippet": " ... The World Snooker Tour ranked the match as number one on its \"Top Ten Matches of 2022\" list.\n\nHawkins played Trump in the second semi-final. Hawkins won the opening frame after a prolonged safety battle, but Trump levelled the scores with a break of 86. Trump also ... ",
            "title": "https://en.wikipedia.org/wiki/2022_Masters_(snooker)"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d3",
            "snippet": " ... breaks over 50. Before his match with Vafaei, 2019 champion Judd Trump stated that he had not been enjoying his snooker and did not have high expectations for the World Championship. The scores were tied at 3–3, but Trump won seven of the next eight frames for ... ",
            "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d12",
            "snippet": " ... round match against Hossein Vafaei at the 2023 World Snooker Championship. At the 2022 Scottish Open, O'Sullivan scored a century in 3 minutes 34 seconds — just 3 seconds slower than the fastest televised century break, which was made by Tony Drago in 1996.\n\nPartial list\n\nSince the ... ",
            "title": "https://en.wikipedia.org/wiki/Maximum_and_century_breaks_made_by_Ronnie_O%27Sullivan"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d7",
            "snippet": " ... Snooker Championship, Selby defeated Mark Allen 17–15 in a semi-final that lasted for over 13 and a half hours in total, with the final session ending at 12:48 a.m. In frame 16 of the final against Luca Brecel, Selby scored a maximum break, his ... ",
            "title": "https://en.wikipedia.org/wiki/Mark_Selby"
          }
        ],
        "query": "snooker championship match detailed frame scores breaks list"
      }
    ]
  },
  "round": 4,
  "tool": "search",
  "tool_call_id": "call_a97922f1f95b4e9aa99f5650"
}
```

## Full event records for this request interval

```json
[
  {
    "seq": 103,
    "kind": "model_request",
    "payload": {
      "capacity": 57803,
      "compacted": false,
      "counter": {
        "calibrated_provider_tokens": false,
        "kind": "utf8_bytes"
      },
      "evidence_shelf": [],
      "final": false,
      "output_reservation": 4096,
      "request": "3e0b92229007f74101223732da9d0a727cbe4775d87f42df90b9a597acf23535",
      "round": 4,
      "shelf_evicted_for_capacity": [],
      "visible_documents": [
        "d1",
        "d2",
        "d3",
        "d4",
        "d5",
        "d6",
        "d7",
        "d8",
        "d9",
        "d10",
        "d11",
        "d12",
        "d13",
        "d14",
        "d15",
        "d16",
        "d17"
      ],
      "visible_evidence": []
    },
    "previous": "82a4f1b6f0421a7af5150b1c75ab16e1da5888b0ede7d96b5a5bbcc4af33c472",
    "hash": "b8943ef2dd7a098ea43a9b4496e511834f743b3aaf8c2435a9a1f3d1059de13c"
  },
  {
    "seq": 104,
    "kind": "model_response",
    "payload": {
      "elapsed_seconds": 4.367112300009467,
      "output_charged": 157,
      "raw": "9f0e3c3c2577fb91a530e6d2053774527a72d2b4848ec3e14cc1cdd9a852cc89",
      "response_model": "glm-5.2",
      "round": 4,
      "usage": {
        "cache_read_tokens": 9728,
        "input_tokens": 14885,
        "output_tokens": 157
      }
    },
    "previous": "b8943ef2dd7a098ea43a9b4496e511834f743b3aaf8c2435a9a1f3d1059de13c",
    "hash": "ad12c3f5dbe5cdc22cd5b95b9e35cacb432e52dcede74acd000eeec5d9bf71f4"
  },
  {
    "seq": 105,
    "kind": "delivery_ack",
    "payload": {
      "documents": [
        "d1",
        "d2",
        "d3",
        "d4",
        "d5",
        "d6",
        "d7",
        "d8",
        "d9",
        "d10",
        "d11",
        "d12",
        "d13",
        "d14",
        "d15",
        "d16",
        "d17"
      ],
      "evidence": [],
      "round": 4
    },
    "previous": "ad12c3f5dbe5cdc22cd5b95b9e35cacb432e52dcede74acd000eeec5d9bf71f4",
    "hash": "a93c4029eb41b8de48b6e117c829033e4f5fc5c2f7bb6562ca7fa94576ab6407"
  },
  {
    "seq": 106,
    "kind": "navigation_ack",
    "payload": {
      "object": "9ebe21fd6e4e99120af7f9ff510cfafb37ec2593fb8dd482c2e6a772445723a9",
      "round": 4,
      "source_round": 3
    },
    "previous": "a93c4029eb41b8de48b6e117c829033e4f5fc5c2f7bb6562ca7fa94576ab6407",
    "hash": "f5d62c998f6a20b4564d9904fed7710b69c1545822c304d9d8cdd31017a6a478"
  },
  {
    "seq": 107,
    "kind": "query_execution",
    "payload": {
      "cache_key": "169e668828050ea6c90fd6399ccee54c5b8b5c12e9c07371c881782fa07ba240",
      "cached": false,
      "compiled": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"referee\" OR \"international\" OR \"december\" OR \"2014\" OR \"2015\" OR \"2016\" OR \"2017\" OR \"2018\" OR \"2019\" OR \"2020\" OR \"2021\"",
        "terms": [
          "snooker",
          "referee",
          "international",
          "december",
          "2014",
          "2015",
          "2016",
          "2017",
          "2018",
          "2019",
          "2020",
          "2021"
        ]
      },
      "equivalence_key": "939a7470fb3d3ac984bca7b2bded2255c1392efa2b832f43daceb081225326bb",
      "query": "snooker referee international referee December 2014 2015 2016 2017 2018 2019 2020 2021",
      "round": 4,
      "top_k": 5
    },
    "previous": "f5d62c998f6a20b4564d9904fed7710b69c1545822c304d9d8cdd31017a6a478",
    "hash": "f64c9f9b4bf259bcb979060efb45585937a428540aa4bef77613bde6d592f14f"
  },
  {
    "seq": 108,
    "kind": "backend_request",
    "payload": {
      "arguments": {
        "query": "snooker referee international referee December 2014 2015 2016 2017 2018 2019 2020 2021",
        "top_k": 5
      },
      "kind": "search",
      "number": 19
    },
    "previous": "f64c9f9b4bf259bcb979060efb45585937a428540aa4bef77613bde6d592f14f",
    "hash": "81309bb0d86cefaa54c7c9aba3a4f6a33347e58aa3a2118b931b517157097e7a"
  },
  {
    "seq": 109,
    "kind": "backend_response",
    "payload": {
      "elapsed_seconds": 0.5869609999936074,
      "kind": "search",
      "object": "d7bb20d04ee6ce033ebf38dc2bc8f2fde15c72da1211ab43e433ff56f51fd415",
      "raw_wire": "d7bb20d04ee6ce033ebf38dc2bc8f2fde15c72da1211ab43e433ff56f51fd415",
      "wire_request": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"referee\" OR \"international\" OR \"december\" OR \"2014\" OR \"2015\" OR \"2016\" OR \"2017\" OR \"2018\" OR \"2019\" OR \"2020\" OR \"2021\"",
        "kind": "local_sql",
        "query": "snooker referee international referee December 2014 2015 2016 2017 2018 2019 2020 2021",
        "terms": [
          "snooker",
          "referee",
          "international",
          "december",
          "2014",
          "2015",
          "2016",
          "2017",
          "2018",
          "2019",
          "2020",
          "2021"
        ],
        "top_k": 5
      }
    },
    "previous": "81309bb0d86cefaa54c7c9aba3a4f6a33347e58aa3a2118b931b517157097e7a",
    "hash": "f4d6e5c85da09d6cb069c466274225dc0b518b8f0d56e900dee54e83b5f025e5"
  },
  {
    "seq": 110,
    "kind": "query_execution",
    "payload": {
      "cache_key": "14f5b35067d37cb77c12c527520873b4a0765f1ec0a0fb8a802afaf15fdb7ea9",
      "cached": true,
      "compiled": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"referee\" OR \"became\" OR \"international\" OR \"december\" OR \"year\"",
        "terms": [
          "snooker",
          "referee",
          "became",
          "international",
          "december",
          "year"
        ]
      },
      "equivalence_key": "5ae2c42bf307ee337df54ff83a1dfcb9a316053aae3f8679461ae095819e6a21",
      "query": "snooker referee became international referee December year",
      "round": 4,
      "top_k": 5
    },
    "previous": "f4d6e5c85da09d6cb069c466274225dc0b518b8f0d56e900dee54e83b5f025e5",
    "hash": "9db99ba6a6a4c71ff752fe290a2dd09d6411d39c50c1900322707c2a1f750b89"
  },
  {
    "seq": 111,
    "kind": "query_execution",
    "payload": {
      "cache_key": "7590a40e63e698106772858f5951ea2a15c6cbc38864e0d7d6d4a73524292918",
      "cached": false,
      "compiled": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"referee\" OR \"international\" OR \"qualification\" OR \"december\" OR \"before\" OR \"2022\"",
        "terms": [
          "snooker",
          "referee",
          "international",
          "qualification",
          "december",
          "before",
          "2022"
        ]
      },
      "equivalence_key": "b180f1868aaf487d822f5ab53a4a32c4ec85293d2530f441ee055e8d4b350c1b",
      "query": "snooker referee international qualification December before 2022",
      "round": 4,
      "top_k": 5
    },
    "previous": "9db99ba6a6a4c71ff752fe290a2dd09d6411d39c50c1900322707c2a1f750b89",
    "hash": "1ad5213e1ad24a3a2656dbeb588aaa165aded443678f858c9b9fed3c006c9828"
  },
  {
    "seq": 112,
    "kind": "backend_request",
    "payload": {
      "arguments": {
        "query": "snooker referee international qualification December before 2022",
        "top_k": 5
      },
      "kind": "search",
      "number": 20
    },
    "previous": "1ad5213e1ad24a3a2656dbeb588aaa165aded443678f858c9b9fed3c006c9828",
    "hash": "3474ae4da28172543ea24cccebe34b6c7dd50f49967cd50ffacdcaa005976bef"
  },
  {
    "seq": 113,
    "kind": "backend_response",
    "payload": {
      "elapsed_seconds": 0.49921769998036325,
      "kind": "search",
      "object": "37bd542d79689c2c0ed2505ca526e4155eb1efc0e4f3da79a4272fa19511e20b",
      "raw_wire": "37bd542d79689c2c0ed2505ca526e4155eb1efc0e4f3da79a4272fa19511e20b",
      "wire_request": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"referee\" OR \"international\" OR \"qualification\" OR \"december\" OR \"before\" OR \"2022\"",
        "kind": "local_sql",
        "query": "snooker referee international qualification December before 2022",
        "terms": [
          "snooker",
          "referee",
          "international",
          "qualification",
          "december",
          "before",
          "2022"
        ],
        "top_k": 5
      }
    },
    "previous": "3474ae4da28172543ea24cccebe34b6c7dd50f49967cd50ffacdcaa005976bef",
    "hash": "89ba46ab4607378a28271216b2cd3ff63a1c8d1085f2b2a83a7b7dfb1ecdd460"
  },
  {
    "seq": 114,
    "kind": "document_registered",
    "payload": {
      "backend": "98375",
      "ref": "d18",
      "title": "https://en.wikipedia.org/wiki/Impact_of_the_COVID-19_pandemic_on_sports"
    },
    "previous": "89ba46ab4607378a28271216b2cd3ff63a1c8d1085f2b2a83a7b7dfb1ecdd460",
    "hash": "03e5924325a6b699b6f0e2c593d125e8e0fdba0494a567525caae907146518b2"
  },
  {
    "seq": 115,
    "kind": "action_execution",
    "payload": {
      "object": "ae74994bed1ad4886535e2f452014c56cee75590a974014d60dbd69a615c818c",
      "round": 4,
      "tool_call_id": "call_e04bfbd722614233bdd13111"
    },
    "previous": "03e5924325a6b699b6f0e2c593d125e8e0fdba0494a567525caae907146518b2",
    "hash": "c7ceee58455d20e67cabba6d96fe261c7df91bdbd00a3a3419bb6617e2094bfd"
  },
  {
    "seq": 116,
    "kind": "query_execution",
    "payload": {
      "cache_key": "fb98f8d32d35e218a0ea024370520a721adff9bcd016652711b0f4c5ceefd9f9",
      "cached": false,
      "compiled": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"match\" OR \"scorecard\" OR \"frame\" OR \"breaks\" OR \"50\" OR \"60\" OR \"70\" OR \"90\" OR \"100\" OR \"century\" OR \"detailed\"",
        "terms": [
          "snooker",
          "match",
          "scorecard",
          "frame",
          "breaks",
          "50",
          "60",
          "70",
          "90",
          "100",
          "century",
          "detailed"
        ]
      },
      "equivalence_key": "fbdb3f860ecc67131425e9b4a8c12c356f52156afee6ad6681f7bf27bedda7ba",
      "query": "snooker match scorecard frame breaks 50 60 70 90 100 century detailed",
      "round": 4,
      "top_k": 5
    },
    "previous": "c7ceee58455d20e67cabba6d96fe261c7df91bdbd00a3a3419bb6617e2094bfd",
    "hash": "352d32fbc6ec223f5a26c871c35aaf4367140f4388551ab7ad5f1e04c43fa8f6"
  },
  {
    "seq": 117,
    "kind": "backend_request",
    "payload": {
      "arguments": {
        "query": "snooker match scorecard frame breaks 50 60 70 90 100 century detailed",
        "top_k": 5
      },
      "kind": "search",
      "number": 21
    },
    "previous": "352d32fbc6ec223f5a26c871c35aaf4367140f4388551ab7ad5f1e04c43fa8f6",
    "hash": "c4d1a15b2dfedfe9aae659c39fd35d92d5a2c75f8005ce75f6b7957588bb9466"
  },
  {
    "seq": 118,
    "kind": "backend_response",
    "payload": {
      "elapsed_seconds": 0.6652188999869395,
      "kind": "search",
      "object": "5502f98fb07c40a92c45bf47f300096d22dd478fedacf723c698d847efe89794",
      "raw_wire": "5502f98fb07c40a92c45bf47f300096d22dd478fedacf723c698d847efe89794",
      "wire_request": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"match\" OR \"scorecard\" OR \"frame\" OR \"breaks\" OR \"50\" OR \"60\" OR \"70\" OR \"90\" OR \"100\" OR \"century\" OR \"detailed\"",
        "kind": "local_sql",
        "query": "snooker match scorecard frame breaks 50 60 70 90 100 century detailed",
        "terms": [
          "snooker",
          "match",
          "scorecard",
          "frame",
          "breaks",
          "50",
          "60",
          "70",
          "90",
          "100",
          "century",
          "detailed"
        ],
        "top_k": 5
      }
    },
    "previous": "c4d1a15b2dfedfe9aae659c39fd35d92d5a2c75f8005ce75f6b7957588bb9466",
    "hash": "291011258b0d10677eec272920eed8e5340c97f863b5f48471e9805f000cedcd"
  },
  {
    "seq": 119,
    "kind": "query_execution",
    "payload": {
      "cache_key": "9b4c10810610b6b208fa56be4bc900ac6a372f88a74b142c28372565deffc143",
      "cached": true,
      "compiled": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"match\" OR \"two\" OR \"centuries\" OR \"70s\" OR \"breaks\" OR \"60s\" OR \"50s\" OR \"break\" OR \"scorecard\"",
        "terms": [
          "snooker",
          "match",
          "two",
          "centuries",
          "70s",
          "breaks",
          "60s",
          "50s",
          "break",
          "scorecard"
        ]
      },
      "equivalence_key": "7be7aecfafc4a874c9a32cea67d8a1b8cb9a3442f60fe420b21222c66c9df732",
      "query": "snooker match two centuries 70s breaks 60s breaks 50s break scorecard",
      "round": 4,
      "top_k": 5
    },
    "previous": "291011258b0d10677eec272920eed8e5340c97f863b5f48471e9805f000cedcd",
    "hash": "f07dbb80377ae9e689c6e7badb1a4124ac25c374b3062aed70446e8893b47d5d"
  },
  {
    "seq": 120,
    "kind": "query_execution",
    "payload": {
      "cache_key": "ae52f487691e158fe2c28aa89c968a2864dcdd60ab9927288f203ac99ecb5ccf",
      "cached": true,
      "compiled": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"championship\" OR \"match\" OR \"detailed\" OR \"frame\" OR \"scores\" OR \"breaks\" OR \"list\"",
        "terms": [
          "snooker",
          "championship",
          "match",
          "detailed",
          "frame",
          "scores",
          "breaks",
          "list"
        ]
      },
      "equivalence_key": "2714dc21be7649bf89c6b46641b0d493982a37117230a33b9f4b3e28ec1e6028",
      "query": "snooker championship match detailed frame scores breaks list",
      "round": 4,
      "top_k": 5
    },
    "previous": "f07dbb80377ae9e689c6e7badb1a4124ac25c374b3062aed70446e8893b47d5d",
    "hash": "933d28728e380d0b46693fc353a126973e0459fd043501be2092660db6692f8c"
  },
  {
    "seq": 121,
    "kind": "action_execution",
    "payload": {
      "object": "707c5ae50fadeaf0dd96efaedfc198b60d8db54c12c3351aa39c63bf93282889",
      "round": 4,
      "tool_call_id": "call_a97922f1f95b4e9aa99f5650"
    },
    "previous": "933d28728e380d0b46693fc353a126973e0459fd043501be2092660db6692f8c",
    "hash": "975103e5b8f2339ef31dbc5ba34add3d25b42946ece6d91952d1d0df3b66bb63"
  },
  {
    "seq": 122,
    "kind": "delivery_preflight",
    "payload": {
      "documents": [
        "d12",
        "d8",
        "d4",
        "d16",
        "d3",
        "d2",
        "d9",
        "d10",
        "d11",
        "d18",
        "d1",
        "d17",
        "d5",
        "d7"
      ],
      "evidence": [],
      "fits": true,
      "phase": "RESEARCH",
      "round": 4
    },
    "previous": "975103e5b8f2339ef31dbc5ba34add3d25b42946ece6d91952d1d0df3b66bb63",
    "hash": "27aebc5200f11a186668909270253eb8df26e8c753399be51439f2554d897770"
  },
  {
    "seq": 123,
    "kind": "action_result",
    "payload": {
      "arguments": "{\"queries\": [\"snooker referee international referee December 2014 2015 2016 2017 2018 2019 2020 2021\", \"snooker referee became international referee December year\", \"snooker referee international qualification December before 2022\"]}",
      "executed": true,
      "result": {
        "action_slot_charged": true,
        "executed": true,
        "ok": true,
        "results": [
          {
            "cached": false,
            "hits": [
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d12",
                "snippet": " ... 2015–16 season | 824 |\n| 2016 European Masters | 2 |\n| 2016 English Open | 1 |\n| 2016 International Championship | 2 |\n| 2016 Champion of Champions | 6 |\n| 2016 Northern Ireland Open | 6 |\n| 2016 UK Championship | 10 |\n| 2016 Scottish Open | 4 |\n| 2017 Masters | 3 |\n| 2017 German Masters | 1 |\n| 2017 World Grand Prix | 2 |\n| 2017 Welsh ... ",
                "title": "https://en.wikipedia.org/wiki/Maximum_and_century_breaks_made_by_Ronnie_O%27Sullivan"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d8",
                "snippet": " ... referee European and international matches. In 2015, he officiated the Football League Cup final at Wembley Stadium when Chelsea defeated Tottenham Hotspur 2–0. Taylor returned to Wembley later that year to officiate the Community Shield as Arsenal beat Chelsea 1–0. He refereed the 2017 and 2020 ... ",
                "title": "https://pantheon.world/profile/occupation/referee/country/united-kingdom"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d4",
                "snippet": " ... maximum breaks order:\n\n| Year | 147s |\n\n|---|---|\n\n| 2024 | 14 |\n\n| 2018 | 12 |\n\n| 2022 | 11 |\n\n| 2012 | 11 |\n\n| 2023 | 11 |\n\n| 2016 | 10 |\n\n| 1999 | 10 |\n\n| 2025 | 9 |\n\n| 2020 | 9 |\n\n| 2019 | 9 |\n\n| 2011 | 9 |\n\n| 2021 | 8 |\n\n| 2017 | 8 |\n\n| 2014 | 8 |\n\n| 2010 | 7 |\n\n| 2008 | 7 |\n\n| 2000 | 7 |\n\n| 2015 | 6 |\n\n| 2013 | 6 |\n\n| 2007 | 6 |\n\n| 1992 | 5 |\n\n| 2001 ... ",
                "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d16",
                "snippet": " ... 1) | Rob Spencer (4) | 2017 |\n\n| 133 | Kyren Wilson (1) | International Championship | Martin Gould (2) | Shen Yifei (1) | 2017 |\n\n| 134 | Cao Yupeng (1) | Scottish Open | Andrew Higginson (1) | Rob Spencer (5) | 2017 |\n\n| 135 | Martin Gould (1) | Championship League | Li Hang (1) | Brendan Moore (7) | 2018 |\n\n| 136 | Luca Brecel (1 ... ",
                "title": "https://wpbsa.com/about-us/history/147-breaks/"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d3",
                "snippet": " ... 2022 World Snooker Championship - Wikipedia\ndate: 2021-05-03\n---\ntournament_name: 2022 Betfred World Snooker Championship\nlogo: World Snooker Championship 2015 Logo.png\ndates: 16 April 2022\nvenue: Crucible Theatre\nlocation: Sheffield\ncountry: England\norganisation: World Snooker Tour\nformat: Ranking event\ntotal prize fund: £2, 395, 000\nwinners ... ",
                "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
              }
            ],
            "query": "snooker referee international referee December 2014 2015 2016 2017 2018 2019 2020 2021"
          },
          {
            "cached": true,
            "hits": [
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d8",
                "snippet": " ... She qualified in 2001 to referee on the World Snooker Tour and was the sport's highest profile female referee for the next 14 years. She became the first woman to officiate at a professional ranking snooker tournament at the 2002 Welsh Open, and the first woman to ... ",
                "title": "https://pantheon.world/profile/occupation/referee/country/united-kingdom"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d2",
                "snippet": " ... The event's referees wore suits tailored by McCann Bespoke, as part of the London tailor's new partnership with the World Snooker Tour that is intended to restyle the appearance of referees and players.\n\nThe tournament was broadcast live in the United Kingdom by BBC Sport, as ... ",
                "title": "https://en.wikipedia.org/wiki/2022_Masters_(snooker)"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d9",
                "snippet": " ... This is to prevent the score difference from decreasing too much, at the referee's discretion.\n# If it is physically impossible to play a legal shot (the snooker is truly inescapable, as judged by the referee). The player must still put sufficient strength into the shot so that ... ",
                "title": "https://en.wikipedia.org/wiki/Rules_of_snooker"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d10",
                "snippet": " ... I think it probably goes back a couple hundred years, to before Snooker even became a thing and the players played the \"pool\" games: pyramid pool, life pool, black pool. These were usually more than two players and were centered on the bets that were placed and the ... ",
                "title": "https://www.snookerisland.com/forum/viewtopic.php?f=468&t=6542"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d11",
                "snippet": " ... Snookered After a Foul\n\nAfter a foul, if the cue-ball is snookered, the referee shall state FREE BALL (see Section 2, Rule 16).\n\n(a) If the player next in turn elects to play the next stroke,\n\n(I) he may nominate any ball as the ball on, and ... ",
                "title": "https://club-snooker.web.cern.ch/club-snooker/rules.html"
              }
            ],
            "query": "snooker referee became international referee December year"
          },
          {
            "cached": false,
            "hits": [
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d3",
                "snippet": " ... At the end of the year, the World Snooker Tour ranked the semi-final between Trump and Williams in second place on its \"Top Ten Matches of 2022\" list.\n\nO'Sullivan and Higgins met at the Crucible for a sixth time. Before the semi-final, O'Sullivan led ... ",
                "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d8",
                "snippet": " ... since June 2022.\n\n8. Michaela Tabb (b. 1967)\n\nWith an HPI of 44.26, Michaela Tabb is the 8th most famous British Referee. Her biography has been translated into 15 different languages.\n\nMichaela Tabb (born 11 December 1967) is a Scottish snooker and pool referee. She established significant ... ",
                "title": "https://pantheon.world/profile/occupation/referee/country/united-kingdom"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d2",
                "snippet": " ... 2022 Masters (snooker) - Wikipedia\ndate: 2021-04-15\n---\ntournament_name: 2022 Cazoo Masters\nlogo: 270px\nalt: Masters Snooker event promotional logo\ndates: 9 January 2022\nvenue: Alexandra Palace\nlocation: London\ncountry: England\norganisation: World Snooker Tour\nformat: Non-ranking event\ntotal prize fund: £725, 000\nwinners_share: £250 ... ",
                "title": "https://en.wikipedia.org/wiki/2022_Masters_(snooker)"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d4",
                "snippet": " ... Who made the 100th 147 Break in Snooker?\n\nMark Selby was the player to make the 100th 147 break in snooker at the UK championship on 7th December 2013 against Ricky Walden. Selby's 2nd maximum followed his first on 5th June 2009 against Joe Perry in the ... ",
                "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": false,
                "ref": "d18",
                "snippet": " ... international visitors\" in China. The races were supposed to be held 19–21 March, and would have acted as a dress rehearsal for the upcoming 2022 Winter Olympics in Beijing. The FIS said they would be looking for a replacement host for the races.\n\nOn 9 December, the ... ",
                "title": "https://en.wikipedia.org/wiki/Impact_of_the_COVID-19_pandemic_on_sports"
              }
            ],
            "query": "snooker referee international qualification December before 2022"
          }
        ]
      },
      "round": 4,
      "tool": "search",
      "tool_call_id": "call_e04bfbd722614233bdd13111"
    },
    "previous": "27aebc5200f11a186668909270253eb8df26e8c753399be51439f2554d897770",
    "hash": "e3ff1a78a0452ae2b67732c284bcb1c08de1d97875eaefe5438327682fc4932f"
  },
  {
    "seq": 124,
    "kind": "action_result",
    "payload": {
      "arguments": "{\"queries\": [\"snooker match scorecard frame breaks 50 60 70 90 100 century detailed\", \"snooker match two centuries 70s breaks 60s breaks 50s break scorecard\", \"snooker championship match detailed frame scores breaks list\"]}",
      "executed": true,
      "result": {
        "action_slot_charged": true,
        "executed": true,
        "ok": true,
        "results": [
          {
            "cached": false,
            "hits": [
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d1",
                "snippet": " ... Pages\n\n-\n\nPlayer Profile\n\nTournament Record\n\nMost Frequent Opponents\n\nRounds Reached\n\nCentury Frequency\n\nCenturies per Season Graph\n\nRanking History\n\nPrize Money History\n\nBreaks\n\n| 50s | 60s | 70s | 80s | 90s | 100s | Total | |\n\n|---|---|---|---|---|---|---|---|\n\n| Breaks | 35 | 23 | 31 | 16 | 11 | 23 | 139 |\n\n| Frame rate | 15.46 | 23.52 | 17.45 | 33.81 | 49 ... ",
                "title": "https://cuetracker.net/players/julien-leclercq/career-total-statistics"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d2",
                "snippet": " ... 100,000\n* Semi-finals: £60,000\n* Quarter-finals: £30,000\n* Last 16: £15,000\n* Highest break: £15,000\n* Total: £725,000\n\nSummary\n\nFirst round\n\nThe first round was played between 9 and 12 January 2022 as the best-of-11 frames. In the opening afternoon's match, defending ... ",
                "title": "https://en.wikipedia.org/wiki/2022_Masters_(snooker)"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d4",
                "snippet": " ... 90s\n\n7 of the Best Snooker Matches of the 80's & 90's\n\nEvery Competitive 147 in Snooker History\n\nIf you have got this far you must love your snooker, and to save you going off to find evermore detail, we have a list of every 147 break ... ",
                "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d3",
                "snippet": " ... The match featured five centuries and 12 more breaks over 50. Before his match with Vafaei, 2019 champion Judd Trump stated that he had not been enjoying his snooker and did not have high expectations for the World Championship. The scores were tied at 3–3, but Trump ... ",
                "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d17",
                "snippet": " ... The match was drawn. Scorecard | Birmingham | 1994 |\n\nMost runs in a career\n\nQualification: 40,000.\n\n**Table 8**\n\n| Runs | Player | Innings | Matches | Average | Career span |\n|---|---|---|---|---|---|\n| 61,760 | Jack Hobbs (Surrey and England) | 1,325 | 834 | 50.70 | from 1905 to 1934 |\n| 58,959 | Frank Woolley (Kent and England) | 1 ... ",
                "title": "https://en.wikipedia.org/wiki/List_of_first-class_cricket_records"
              }
            ],
            "query": "snooker match scorecard frame breaks 50 60 70 90 100 century detailed"
          },
          {
            "cached": true,
            "hits": [
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d2",
                "snippet": " ... Robertson compiled two centuries and six other breaks of 50 or more in the final, while Hawkins made just two breaks over 50. Hawkins acknowledged that his performance in the final had been substandard, saying: \"I made too many mistakes today and you can't do that against ... ",
                "title": "https://en.wikipedia.org/wiki/2022_Masters_(snooker)"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d3",
                "snippet": " ... The match featured five centuries and 12 more breaks over 50. Before his match with Vafaei, 2019 champion Judd Trump stated that he had not been enjoying his snooker and did not have high expectations for the World Championship. The scores were tied at 3–3, but Trump ... ",
                "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d1",
                "snippet": " ... as professional: | 3 |\n\nAdditional Pages\n\n-\n\nPlayer Profile\n\nTournament Record\n\nMost Frequent Opponents\n\nRounds Reached\n\nCentury Frequency\n\nCenturies per Season Graph\n\nRanking History\n\nPrize Money History\n\nBreaks\n\n| 50s | 60s | 70s | 80s | 90s | 100s | Total | |\n\n|---|---|---|---|---|---|---|---|\n\n| Breaks | 35 | 23 | 31 | 16 | 11 | 23 | 139 |\n\n| Frame rate | 15.46 | 23.52 | 17 ... ",
                "title": "https://cuetracker.net/players/julien-leclercq/career-total-statistics"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d5",
                "snippet": " ... Coventry\n\n- Snooker Idol: Hendry and Trump\n\n- Highest Break: 30\n\n- Walk-On: Simple Minds- Glittering Prize\n\n-\n\nby Pink Ball » 15 Apr 2022 Read\n\nThe honourable mentions, the matches that didn't make the top 50:\n\n54.Classic final 1985: Jimmy White 13-12 Cliff Thorburn (6 points)\n\n55. World ... ",
                "title": "https://www.snookerisland.com/forum/viewtopic.php?f=25&t=11961"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d12",
                "snippet": " ... O'Sullivan had made 773 century breaks at the start of 2015. On 13 January, in the first round of the 2015 Masters, he made two centuries to equal Stephen Hendry's record of 775. Two days later, in his second-round match, he made his 776th century ... ",
                "title": "https://en.wikipedia.org/wiki/Maximum_and_century_breaks_made_by_Ronnie_O%27Sullivan"
              }
            ],
            "query": "snooker match two centuries 70s breaks 60s breaks 50s break scorecard"
          },
          {
            "cached": true,
            "hits": [
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d4",
                "snippet": " ... Best Snooker Matches of the 80's & 90's\n\nEvery Competitive 147 in Snooker History\n\nIf you have got this far you must love your snooker, and to save you going off to find evermore detail, we have a list of every 147 break made in snooker history ... ",
                "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d2",
                "snippet": " ... The World Snooker Tour ranked the match as number one on its \"Top Ten Matches of 2022\" list.\n\nHawkins played Trump in the second semi-final. Hawkins won the opening frame after a prolonged safety battle, but Trump levelled the scores with a break of 86. Trump also ... ",
                "title": "https://en.wikipedia.org/wiki/2022_Masters_(snooker)"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d3",
                "snippet": " ... breaks over 50. Before his match with Vafaei, 2019 champion Judd Trump stated that he had not been enjoying his snooker and did not have high expectations for the World Championship. The scores were tied at 3–3, but Trump won seven of the next eight frames for ... ",
                "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d12",
                "snippet": " ... round match against Hossein Vafaei at the 2023 World Snooker Championship. At the 2022 Scottish Open, O'Sullivan scored a century in 3 minutes 34 seconds — just 3 seconds slower than the fastest televised century break, which was made by Tony Drago in 1996.\n\nPartial list\n\nSince the ... ",
                "title": "https://en.wikipedia.org/wiki/Maximum_and_century_breaks_made_by_Ronnie_O%27Sullivan"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d7",
                "snippet": " ... Snooker Championship, Selby defeated Mark Allen 17–15 in a semi-final that lasted for over 13 and a half hours in total, with the final session ending at 12:48 a.m. In frame 16 of the final against Luca Brecel, Selby scored a maximum break, his ... ",
                "title": "https://en.wikipedia.org/wiki/Mark_Selby"
              }
            ],
            "query": "snooker championship match detailed frame scores breaks list"
          }
        ]
      },
      "round": 4,
      "tool": "search",
      "tool_call_id": "call_a97922f1f95b4e9aa99f5650"
    },
    "previous": "e3ff1a78a0452ae2b67732c284bcb1c08de1d97875eaefe5438327682fc4932f",
    "hash": "69a15a906122cadd40eb32e93f47900129f23631aa84d0deaaf13ee3a2cfc11e"
  },
  {
    "seq": 125,
    "kind": "round_end",
    "payload": {
      "group": "c65e22f0215c22b5f4e9d337b4eb7c02f4d9128fd0ffbf3ba4046ebd423b65f3",
      "notes": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
      "remaining": {
        "action_slots": 192,
        "backend_calls": 99,
        "model_calls": 60,
        "output_reservation": 47405
      },
      "round": 4
    },
    "previous": "69a15a906122cadd40eb32e93f47900129f23631aa84d0deaaf13ee3a2cfc11e",
    "hash": "6daaee8ca94ea88c702df21f9238b68e4b1d05a0992f39aa928cab607b0b9018"
  }
]
```
