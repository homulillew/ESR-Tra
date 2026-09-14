# Round 25

[Actual request](../http/025/request.body) · [Actual response](../http/025/response.body) · [All interaction](../FULL_INTERACTION.md)

## Input visibility

```json
{
  "capacity": 74262,
  "compacted": true,
  "counter": {
    "calibrated_provider_tokens": false,
    "kind": "utf8_bytes"
  },
  "evidence_shelf": [],
  "final": false,
  "output_reservation": 4096,
  "request": "8db5fc580ec41a1887565deb43f1ca2311c815f1446bd8a4109c99ac049297d2",
  "round": 25,
  "shelf_evicted_for_capacity": [],
  "visible_documents": [
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
    "d17",
    "d18",
    "d2"
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
              "arguments": "{\"queries\": [\"snooker referee became international referee December\", \"snooker referee international qualification December before 2022\", \"snooker referee international referee December 2013 2014 2015 2016 2017 2018 2019 2020 2021\"]}",
              "name": "search"
            },
            "id": "call_b136fd8d60484ed5ac2959ad",
            "index": 0,
            "type": "function"
          },
          {
            "function": {
              "arguments": "{\"queries\": [\"snooker player turned professional 2011 2012 2013 2014 2015 2016 list\", \"snooker players turned professional between 2011 2016\", \"snooker professional debut year 2012 2013 2014 2015\"]}",
              "name": "search"
            },
            "id": "call_5515005bccdf48ccaf67b3a6",
            "index": 1,
            "type": "function"
          }
        ]
      }
    }
  ],
  "created": 1789382514,
  "id": "chatcmpl-d9ace1a2-b4b2-9442-abf7-0532a95665ed",
  "model": "glm-5.2",
  "object": "chat.completion",
  "usage": {
    "prompt_tokens": 20198,
    "completion_tokens": 165,
    "reasoning_tokens": 0,
    "total_tokens": 20363,
    "cached_tokens": 19968,
    "prompt_tokens_details": {
      "cached_tokens": 19968
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
  "arguments": "{\"queries\": [\"snooker referee became international referee December\", \"snooker referee international qualification December before 2022\", \"snooker referee international referee December 2013 2014 2015 2016 2017 2018 2019 2020 2021\"]}",
  "documents": [
    "d8",
    "d2",
    "d9",
    "d10",
    "d11",
    "d3",
    "d8",
    "d2",
    "d4",
    "d18",
    "d12",
    "d8",
    "d4",
    "d16",
    "d3"
  ],
  "evidence": [],
  "executed": true,
  "result": {
    "action_slot_charged": true,
    "executed": true,
    "ok": true,
    "results": [
      {
        "cached": true,
        "hits": [
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d8",
            "snippet": " ... In 2010, he was promoted to the list of Select Group Referees who officiate primarily in the Premier League, and in 2013 became a listed referee for FIFA allowing him to referee European and international matches. In 2015, he officiated the Football League Cup final at Wembley Stadium ... ",
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
        "query": "snooker referee became international referee December"
      },
      {
        "cached": true,
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
            "previously_received": true,
            "ref": "d18",
            "snippet": " ... international visitors\" in China. The races were supposed to be held 19–21 March, and would have acted as a dress rehearsal for the upcoming 2022 Winter Olympics in Beijing. The FIS said they would be looking for a replacement host for the races.\n\nOn 9 December, the ... ",
            "title": "https://en.wikipedia.org/wiki/Impact_of_the_COVID-19_pandemic_on_sports"
          }
        ],
        "query": "snooker referee international qualification December before 2022"
      },
      {
        "cached": true,
        "hits": [
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d12",
            "snippet": " ... 2013–14 season | 748 |\n| 2014 Paul Hunter Classic | 3 |\n| 2014 Shanghai Masters | 1 |\n| 2014 International Championship | 4 |\n| 2014 Champion of Champions | 8 |\n| 2014 UK Championship | 6 |\n| 2015 Masters | 4 |\n| 2015 Championship League | 4 |\n| 2015 German Masters | 6 |\n| 2015 Welsh Open | 1 |\n| 2015 World Grand Prix | 1 |\n| 2015 China ... ",
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
            "snippet": " ... breaks order:\n\n| Year | 147s |\n\n|---|---|\n\n| 2024 | 14 |\n\n| 2018 | 12 |\n\n| 2022 | 11 |\n\n| 2012 | 11 |\n\n| 2023 | 11 |\n\n| 2016 | 10 |\n\n| 1999 | 10 |\n\n| 2025 | 9 |\n\n| 2020 | 9 |\n\n| 2019 | 9 |\n\n| 2011 | 9 |\n\n| 2021 | 8 |\n\n| 2017 | 8 |\n\n| 2014 | 8 |\n\n| 2010 | 7 |\n\n| 2008 | 7 |\n\n| 2000 | 7 |\n\n| 2015 | 6 |\n\n| 2013 | 6 |\n\n| 2007 | 6 |\n\n| 1992 | 5 |\n\n| 2001 | 3 ... ",
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
        "query": "snooker referee international referee December 2013 2014 2015 2016 2017 2018 2019 2020 2021"
      }
    ]
  },
  "round": 25,
  "tool": "search",
  "tool_call_id": "call_b136fd8d60484ed5ac2959ad"
}
```

## Executed action: search

```json
{
  "arguments": "{\"queries\": [\"snooker player turned professional 2011 2012 2013 2014 2015 2016 list\", \"snooker players turned professional between 2011 2016\", \"snooker professional debut year 2012 2013 2014 2015\"]}",
  "documents": [
    "d4",
    "d12",
    "d6",
    "d7",
    "d13",
    "d4",
    "d12",
    "d6",
    "d7",
    "d3",
    "d12",
    "d7",
    "d4",
    "d3",
    "d2"
  ],
  "evidence": [],
  "executed": true,
  "result": {
    "action_slot_charged": true,
    "executed": true,
    "ok": true,
    "results": [
      {
        "cached": true,
        "hits": [
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d4",
            "snippet": " ... Championship 2011/2012 – Event 12 | 2011 | |\n\n| 8 | Ding Junhui | Players Tour Championship 2011/2012 – Event 11 | 2011 | |\n\n| 9 | Andy Hicks | UK Championship | 2012 | |\n\n| 10 | Shaun Murphy | European Tour 2013/2014 – Event 8 | 2014 | |\n\n| 11 | Ronnie O'Sullivan | Welsh Open | 2014 | |\n\n| 12 | Ryan Day | Asian Tour 2014/2015 – Event ... ",
            "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d12",
            "snippet": " ... Players Tour Championship 2010/2011 – Event 4 which was played from 14 to 16 August 2010, making his 600th century during the tournament. He had made 695 century breaks at the start of the 2013–14 snooker season. He made four in the European Tour 2013/2014 – Event ... ",
            "title": "https://en.wikipedia.org/wiki/Maximum_and_century_breaks_made_by_Ronnie_O%27Sullivan"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d6",
            "snippet": " ... a snooker star, was broadcast on Chinese television in 2010.\n\nPerformance and rankings timeline\n\n**Table 1**\n\n| Tournaments | 2003/04 | 2003/04 | 2004/05 | 2005/06 | 2006/07 | 2007/08 | 2008/09 | 2009/10 | 2010/11 | 2011/12 | 2012/13 | 2013/14 | 2014/15 | 2015/16 | 2016/17 | 2017 ... ",
            "title": "https://en.wikipedia.org/wiki/Ding_Junhui"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d7",
            "snippet": " ... list of competition results for professional seasons starting from 1999.\n\n**Table 1**\n\n| Tournament | 1999/00 | 2000/01 | 2001/02 | 2002/03 | 2003/04 | 2004/05 | 2005/06 | 2006/07 | 2007/08 | 2008/09 | 2009/10 | 2010/11 | 2011/12 | 2012/13 | 2013/14 | 2014/15 | 2015/16 | 2016 ... ",
            "title": "https://en.wikipedia.org/wiki/Mark_Selby"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d13",
            "snippet": " ... 2003/04 | 2003/04 | 2004/05 | 2005/06 | 2006/07 | 2007/08 | 2008/09 | 2009/10 | 2010/11 | 2011/12 | 2012/13 | 2013/14 | 2014/15 | 2015/16 | 2016/17 | 2017/18 | 2018/19 | 2019/20 | 2020/21 | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 ... ",
            "title": "https://en.wikipedia.org/wiki/Mark_Williams_%28snooker_player%29"
          }
        ],
        "query": "snooker player turned professional 2011 2012 2013 2014 2015 2016 list"
      },
      {
        "cached": true,
        "hits": [
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d4",
            "snippet": " ... Fun 147 Snooker Fact\n\nMost 147 Breaks in Snooker\n\nTo date, Ronnie O Sullivan has made more professional 147 breaks in snooker than any other player amassing 15 maxis so far. His first came on 21st April 1997, aged 21 years and 137 Days against Mark Price in ... ",
            "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d12",
            "snippet": " ... By the start of the 2010–11 snooker season, O'Sullivan had made 597 century breaks. He made one century in the Players Tour Championship 2010/2011 – Event 1, and four during the Players Tour Championship 2010/2011 – Event 4 which was played from 14 to 16 August ... ",
            "title": "https://en.wikipedia.org/wiki/Maximum_and_century_breaks_made_by_Ronnie_O%27Sullivan"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d6",
            "snippet": " ... He has twice reached the final of the Masters, winning once in 2011. In 2016, he became the first Asian player to reach the final of the World Championship.\n\nDing began playing snooker at age nine and rose to international prominence in 2002 after winning the Asian Under ... ",
            "title": "https://en.wikipedia.org/wiki/Ding_Junhui"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d7",
            "snippet": " ... 2014, 2016, 2017, 2021\n\nMark Anthony Selby (born 19 June 1983) is an English professional snooker player. Ranked world number one on multiple occasions, he has won a total of 24 ranking titles, placing him eighth on the all-time list of ranking tournament winners. He is a ... ",
            "title": "https://en.wikipedia.org/wiki/Mark_Selby"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d3",
            "snippet": " ... O'Sullivan, Higgins, and Williams, collectively known as the Class of '92 having all turned professional in 1992, all reached the quarter-finals for the first time since 2011. \"I think it's incredible that it's been 30 years and the three of us are better players ... ",
            "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
          }
        ],
        "query": "snooker players turned professional between 2011 2016"
      },
      {
        "cached": true,
        "hits": [
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d12",
            "snippet": " ... He had made 695 century breaks at the start of the 2013–14 snooker season. He made four in the European Tour 2013/2014 – Event 1 to take his century total to 699. His first-round match in the European Tour 2013/2014 – Event 3 was against Lyu ... ",
            "title": "https://en.wikipedia.org/wiki/Maximum_and_century_breaks_made_by_Ronnie_O%27Sullivan"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d7",
            "snippet": " ... Leicester, England\nprofessional: 1999–present\nhigh ranking: 1 (Sep 2011–Nov 2012, Dec 2012–Feb 2013, Apr–Jun 2013, May–Jul 2014, Aug–Dec 2014, Feb 2015–Mar 2019, Aug–Oct 2021, Nov 2021–Apr 2022)\nofficial maximums: 6\nranking wins: 24\nminor wins: 7\nworld champ: 2014 ... ",
            "title": "https://en.wikipedia.org/wiki/Mark_Selby"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d4",
            "snippet": " ... The year 2018 had the highest number of 147 breaks with 12, closely followed by 2012 with 11.\n\n💯 Consistency was seen in the years 2011, 2016, and 2019, with 9 maximum breaks each.\n\n| Year | 147s |\n\n|---|---|\n\n| 2010 | 7 |\n\n| 2011 | 9 |\n\n| 2012 | 11 |\n\n| 2013 | 6 |\n\n| 2014 | 8 |\n\n| 2015 | 6 |\n\n| 2016 ... ",
            "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d3",
            "snippet": " ... 2023\n\nThe 2022 World Snooker Championship (officially the 2022 Betfred World Snooker Championship) was a professional snooker tournament that took place from 16 April to 2 May 2022 at the Crucible Theatre in Sheffield, England, the 46th consecutive year the World Snooker Championship was held at the venue ... ",
            "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
          },
          {
            "kind": "navigation_not_evidence",
            "previously_received": true,
            "ref": "d2",
            "snippet": " ... It was Robertson's sixth Triple Crown title, following his world title in 2010, his previous Masters victory in 2012, and his three UK Championship wins in 2013, 2015, and 2020. Robertson compiled two centuries and six other breaks of 50 or more in the final, while Hawkins ... ",
            "title": "https://en.wikipedia.org/wiki/2022_Masters_(snooker)"
          }
        ],
        "query": "snooker professional debut year 2012 2013 2014 2015"
      }
    ]
  },
  "round": 25,
  "tool": "search",
  "tool_call_id": "call_5515005bccdf48ccaf67b3a6"
}
```

## Full event records for this request interval

```json
[
  {
    "seq": 446,
    "kind": "model_request",
    "payload": {
      "capacity": 74262,
      "compacted": true,
      "counter": {
        "calibrated_provider_tokens": false,
        "kind": "utf8_bytes"
      },
      "evidence_shelf": [],
      "final": false,
      "output_reservation": 4096,
      "request": "8db5fc580ec41a1887565deb43f1ca2311c815f1446bd8a4109c99ac049297d2",
      "round": 25,
      "shelf_evicted_for_capacity": [],
      "visible_documents": [
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
        "d17",
        "d18",
        "d2"
      ],
      "visible_evidence": []
    },
    "previous": "0e99d00999e753ade350fa40510b6090f23f2bd4569bc09a4424b8eaa81750e2",
    "hash": "e01e3ddab403d26f29e7c83d78564e79c61b1847c8a977200e8b01827e1363f9"
  },
  {
    "seq": 447,
    "kind": "model_response",
    "payload": {
      "elapsed_seconds": 3.4565440000151284,
      "output_charged": 165,
      "raw": "0cdb5c90412f518c644af3c8f5186a3727a20f5e07a84a0fcaa76263a64c379e",
      "response_model": "glm-5.2",
      "round": 25,
      "usage": {
        "cache_read_tokens": 19968,
        "input_tokens": 20198,
        "output_tokens": 165
      }
    },
    "previous": "e01e3ddab403d26f29e7c83d78564e79c61b1847c8a977200e8b01827e1363f9",
    "hash": "79a4fd5f35cc9a59629ad2f8024ae31235c8a51d68a74fd39f6bfc8bd26a9610"
  },
  {
    "seq": 448,
    "kind": "delivery_ack",
    "payload": {
      "documents": [
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
        "d17",
        "d18",
        "d2"
      ],
      "evidence": [],
      "round": 25
    },
    "previous": "79a4fd5f35cc9a59629ad2f8024ae31235c8a51d68a74fd39f6bfc8bd26a9610",
    "hash": "a07adb8f011417976eb00ee1d121b48c6beb38ec0845c9557d7093bfd113db29"
  },
  {
    "seq": 449,
    "kind": "navigation_ack",
    "payload": {
      "object": "db5b4c82fc179aed302bfbf60d6bccedd9a6a0a151868de6a3a632c9ff56acc0",
      "round": 25,
      "source_round": 24
    },
    "previous": "a07adb8f011417976eb00ee1d121b48c6beb38ec0845c9557d7093bfd113db29",
    "hash": "4d10507cea726d73ea7f3b41746fd91e10c62e54309e4c9ac32baf646349ed31"
  },
  {
    "seq": 450,
    "kind": "query_execution",
    "payload": {
      "cache_key": "9e902d39d34940b9a14059694cd176e1e2d831ae07ff53287268a9bfc10b63aa",
      "cached": true,
      "compiled": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"referee\" OR \"became\" OR \"international\" OR \"december\"",
        "terms": [
          "snooker",
          "referee",
          "became",
          "international",
          "december"
        ]
      },
      "equivalence_key": "a38a3e85748e743e46ce50a85ee2153484a24ffb7eb8a9ce57cdaa5b65b2f96d",
      "query": "snooker referee became international referee December",
      "round": 25,
      "top_k": 5
    },
    "previous": "4d10507cea726d73ea7f3b41746fd91e10c62e54309e4c9ac32baf646349ed31",
    "hash": "0aa5d6e5745d059f2284df66db8fbe3e00ceaa9c0f1cb8a6c36d444cd58fd8d4"
  },
  {
    "seq": 451,
    "kind": "query_execution",
    "payload": {
      "cache_key": "7590a40e63e698106772858f5951ea2a15c6cbc38864e0d7d6d4a73524292918",
      "cached": true,
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
      "round": 25,
      "top_k": 5
    },
    "previous": "0aa5d6e5745d059f2284df66db8fbe3e00ceaa9c0f1cb8a6c36d444cd58fd8d4",
    "hash": "fcc30a5fd68229e85373a18858680e62a516249dab64fd2da91df1422a21d4e2"
  },
  {
    "seq": 452,
    "kind": "query_execution",
    "payload": {
      "cache_key": "91bb35351755e51a2ffed243cd6738b8ad78fdd10ca893dd00d46c94b15645cf",
      "cached": true,
      "compiled": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"referee\" OR \"international\" OR \"december\" OR \"2013\" OR \"2014\" OR \"2015\" OR \"2016\" OR \"2017\" OR \"2018\" OR \"2019\" OR \"2020\" OR \"2021\"",
        "terms": [
          "snooker",
          "referee",
          "international",
          "december",
          "2013",
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
      "equivalence_key": "4b685c903b962b3b2d34590e45d8cbe69dd66488592f575e42ad277be57fe276",
      "query": "snooker referee international referee December 2013 2014 2015 2016 2017 2018 2019 2020 2021",
      "round": 25,
      "top_k": 5
    },
    "previous": "fcc30a5fd68229e85373a18858680e62a516249dab64fd2da91df1422a21d4e2",
    "hash": "565cae7ee7e1b15b5cdd47fc32b6e8055a0b5eb48efcc1070a08e9de15329723"
  },
  {
    "seq": 453,
    "kind": "action_execution",
    "payload": {
      "object": "2718fbd92ebfc40d60fe8d95cf45d91eccca743a8641cb32809f73caa4a8edf8",
      "round": 25,
      "tool_call_id": "call_b136fd8d60484ed5ac2959ad"
    },
    "previous": "565cae7ee7e1b15b5cdd47fc32b6e8055a0b5eb48efcc1070a08e9de15329723",
    "hash": "f6932d1441d2d484566fc0597900d79141247ff7d9f3e16c0fa58843d2cdee24"
  },
  {
    "seq": 454,
    "kind": "query_execution",
    "payload": {
      "cache_key": "9914bc69c5b6aa028747929dacaf42159820566d1bb2a287aebadb821404d718",
      "cached": true,
      "compiled": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"player\" OR \"turned\" OR \"professional\" OR \"2011\" OR \"2012\" OR \"2013\" OR \"2014\" OR \"2015\" OR \"2016\" OR \"list\"",
        "terms": [
          "snooker",
          "player",
          "turned",
          "professional",
          "2011",
          "2012",
          "2013",
          "2014",
          "2015",
          "2016",
          "list"
        ]
      },
      "equivalence_key": "71341f085ced924788fccede595a843bcd215c0c3618a19cacbf4e79db8c280a",
      "query": "snooker player turned professional 2011 2012 2013 2014 2015 2016 list",
      "round": 25,
      "top_k": 5
    },
    "previous": "f6932d1441d2d484566fc0597900d79141247ff7d9f3e16c0fa58843d2cdee24",
    "hash": "2c58f30582f8499e08a90aef13f8ff50798ab05d8f89e0204cde406deb3b1a22"
  },
  {
    "seq": 455,
    "kind": "query_execution",
    "payload": {
      "cache_key": "9dfdedb194c035af4a328fd90bbdee2e3e3821434faca9e2e1e8aedf9e9a16b9",
      "cached": true,
      "compiled": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"players\" OR \"turned\" OR \"professional\" OR \"between\" OR \"2011\" OR \"2016\"",
        "terms": [
          "snooker",
          "players",
          "turned",
          "professional",
          "between",
          "2011",
          "2016"
        ]
      },
      "equivalence_key": "77587d4c63fdeecc04cf69f5317c4d25dc18641b8a834d60a3de20512c343348",
      "query": "snooker players turned professional between 2011 2016",
      "round": 25,
      "top_k": 5
    },
    "previous": "2c58f30582f8499e08a90aef13f8ff50798ab05d8f89e0204cde406deb3b1a22",
    "hash": "ab94e89a2d90e2f66945c5ad9ec52c8de0686c445754d7805ff2f87251aec8ea"
  },
  {
    "seq": 456,
    "kind": "query_execution",
    "payload": {
      "cache_key": "4849507f6410d20d06320539663154f5c76d55c482171269c9415ac06d62f084",
      "cached": true,
      "compiled": {
        "compiler": "cpu-or-1",
        "expression": "\"snooker\" OR \"professional\" OR \"debut\" OR \"year\" OR \"2012\" OR \"2013\" OR \"2014\" OR \"2015\"",
        "terms": [
          "snooker",
          "professional",
          "debut",
          "year",
          "2012",
          "2013",
          "2014",
          "2015"
        ]
      },
      "equivalence_key": "adad89afe46def2a0d2c315458becec224aa002d195aafa1f610f813dcccb01a",
      "query": "snooker professional debut year 2012 2013 2014 2015",
      "round": 25,
      "top_k": 5
    },
    "previous": "ab94e89a2d90e2f66945c5ad9ec52c8de0686c445754d7805ff2f87251aec8ea",
    "hash": "e33ece3e3755d2bbaa69d250755c3c58fdf81de9130a5dfdbf4cb2ecba914df8"
  },
  {
    "seq": 457,
    "kind": "action_execution",
    "payload": {
      "object": "1e9f97624db6d1d78c3d7899ff51296d370e69ba97ab40f65d5093aea2e643e0",
      "round": 25,
      "tool_call_id": "call_5515005bccdf48ccaf67b3a6"
    },
    "previous": "e33ece3e3755d2bbaa69d250755c3c58fdf81de9130a5dfdbf4cb2ecba914df8",
    "hash": "1e84b39bc0eeba118e9578125b0e0e327ebdb7789234fddc8270e32670da44b8"
  },
  {
    "seq": 458,
    "kind": "delivery_preflight",
    "payload": {
      "documents": [
        "d8",
        "d2",
        "d9",
        "d10",
        "d11",
        "d3",
        "d4",
        "d18",
        "d12",
        "d16",
        "d6",
        "d7",
        "d13"
      ],
      "evidence": [],
      "fits": true,
      "phase": "RESEARCH",
      "round": 25
    },
    "previous": "1e84b39bc0eeba118e9578125b0e0e327ebdb7789234fddc8270e32670da44b8",
    "hash": "6025598158320ce1ad8954c9fb072619639a7ab016afcd4f574cffeb6caf2dc3"
  },
  {
    "seq": 459,
    "kind": "action_result",
    "payload": {
      "arguments": "{\"queries\": [\"snooker referee became international referee December\", \"snooker referee international qualification December before 2022\", \"snooker referee international referee December 2013 2014 2015 2016 2017 2018 2019 2020 2021\"]}",
      "executed": true,
      "result": {
        "action_slot_charged": true,
        "executed": true,
        "ok": true,
        "results": [
          {
            "cached": true,
            "hits": [
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d8",
                "snippet": " ... In 2010, he was promoted to the list of Select Group Referees who officiate primarily in the Premier League, and in 2013 became a listed referee for FIFA allowing him to referee European and international matches. In 2015, he officiated the Football League Cup final at Wembley Stadium ... ",
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
            "query": "snooker referee became international referee December"
          },
          {
            "cached": true,
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
                "previously_received": true,
                "ref": "d18",
                "snippet": " ... international visitors\" in China. The races were supposed to be held 19–21 March, and would have acted as a dress rehearsal for the upcoming 2022 Winter Olympics in Beijing. The FIS said they would be looking for a replacement host for the races.\n\nOn 9 December, the ... ",
                "title": "https://en.wikipedia.org/wiki/Impact_of_the_COVID-19_pandemic_on_sports"
              }
            ],
            "query": "snooker referee international qualification December before 2022"
          },
          {
            "cached": true,
            "hits": [
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d12",
                "snippet": " ... 2013–14 season | 748 |\n| 2014 Paul Hunter Classic | 3 |\n| 2014 Shanghai Masters | 1 |\n| 2014 International Championship | 4 |\n| 2014 Champion of Champions | 8 |\n| 2014 UK Championship | 6 |\n| 2015 Masters | 4 |\n| 2015 Championship League | 4 |\n| 2015 German Masters | 6 |\n| 2015 Welsh Open | 1 |\n| 2015 World Grand Prix | 1 |\n| 2015 China ... ",
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
                "snippet": " ... breaks order:\n\n| Year | 147s |\n\n|---|---|\n\n| 2024 | 14 |\n\n| 2018 | 12 |\n\n| 2022 | 11 |\n\n| 2012 | 11 |\n\n| 2023 | 11 |\n\n| 2016 | 10 |\n\n| 1999 | 10 |\n\n| 2025 | 9 |\n\n| 2020 | 9 |\n\n| 2019 | 9 |\n\n| 2011 | 9 |\n\n| 2021 | 8 |\n\n| 2017 | 8 |\n\n| 2014 | 8 |\n\n| 2010 | 7 |\n\n| 2008 | 7 |\n\n| 2000 | 7 |\n\n| 2015 | 6 |\n\n| 2013 | 6 |\n\n| 2007 | 6 |\n\n| 1992 | 5 |\n\n| 2001 | 3 ... ",
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
            "query": "snooker referee international referee December 2013 2014 2015 2016 2017 2018 2019 2020 2021"
          }
        ]
      },
      "round": 25,
      "tool": "search",
      "tool_call_id": "call_b136fd8d60484ed5ac2959ad"
    },
    "previous": "6025598158320ce1ad8954c9fb072619639a7ab016afcd4f574cffeb6caf2dc3",
    "hash": "f382ecfc6173d8729cf177df5297047d94614f2ab10ab85a9af234559e517ddc"
  },
  {
    "seq": 460,
    "kind": "action_result",
    "payload": {
      "arguments": "{\"queries\": [\"snooker player turned professional 2011 2012 2013 2014 2015 2016 list\", \"snooker players turned professional between 2011 2016\", \"snooker professional debut year 2012 2013 2014 2015\"]}",
      "executed": true,
      "result": {
        "action_slot_charged": true,
        "executed": true,
        "ok": true,
        "results": [
          {
            "cached": true,
            "hits": [
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d4",
                "snippet": " ... Championship 2011/2012 – Event 12 | 2011 | |\n\n| 8 | Ding Junhui | Players Tour Championship 2011/2012 – Event 11 | 2011 | |\n\n| 9 | Andy Hicks | UK Championship | 2012 | |\n\n| 10 | Shaun Murphy | European Tour 2013/2014 – Event 8 | 2014 | |\n\n| 11 | Ronnie O'Sullivan | Welsh Open | 2014 | |\n\n| 12 | Ryan Day | Asian Tour 2014/2015 – Event ... ",
                "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d12",
                "snippet": " ... Players Tour Championship 2010/2011 – Event 4 which was played from 14 to 16 August 2010, making his 600th century during the tournament. He had made 695 century breaks at the start of the 2013–14 snooker season. He made four in the European Tour 2013/2014 – Event ... ",
                "title": "https://en.wikipedia.org/wiki/Maximum_and_century_breaks_made_by_Ronnie_O%27Sullivan"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d6",
                "snippet": " ... a snooker star, was broadcast on Chinese television in 2010.\n\nPerformance and rankings timeline\n\n**Table 1**\n\n| Tournaments | 2003/04 | 2003/04 | 2004/05 | 2005/06 | 2006/07 | 2007/08 | 2008/09 | 2009/10 | 2010/11 | 2011/12 | 2012/13 | 2013/14 | 2014/15 | 2015/16 | 2016/17 | 2017 ... ",
                "title": "https://en.wikipedia.org/wiki/Ding_Junhui"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d7",
                "snippet": " ... list of competition results for professional seasons starting from 1999.\n\n**Table 1**\n\n| Tournament | 1999/00 | 2000/01 | 2001/02 | 2002/03 | 2003/04 | 2004/05 | 2005/06 | 2006/07 | 2007/08 | 2008/09 | 2009/10 | 2010/11 | 2011/12 | 2012/13 | 2013/14 | 2014/15 | 2015/16 | 2016 ... ",
                "title": "https://en.wikipedia.org/wiki/Mark_Selby"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d13",
                "snippet": " ... 2003/04 | 2003/04 | 2004/05 | 2005/06 | 2006/07 | 2007/08 | 2008/09 | 2009/10 | 2010/11 | 2011/12 | 2012/13 | 2013/14 | 2014/15 | 2015/16 | 2016/17 | 2017/18 | 2018/19 | 2019/20 | 2020/21 | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 ... ",
                "title": "https://en.wikipedia.org/wiki/Mark_Williams_%28snooker_player%29"
              }
            ],
            "query": "snooker player turned professional 2011 2012 2013 2014 2015 2016 list"
          },
          {
            "cached": true,
            "hits": [
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d4",
                "snippet": " ... Fun 147 Snooker Fact\n\nMost 147 Breaks in Snooker\n\nTo date, Ronnie O Sullivan has made more professional 147 breaks in snooker than any other player amassing 15 maxis so far. His first came on 21st April 1997, aged 21 years and 137 Days against Mark Price in ... ",
                "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d12",
                "snippet": " ... By the start of the 2010–11 snooker season, O'Sullivan had made 597 century breaks. He made one century in the Players Tour Championship 2010/2011 – Event 1, and four during the Players Tour Championship 2010/2011 – Event 4 which was played from 14 to 16 August ... ",
                "title": "https://en.wikipedia.org/wiki/Maximum_and_century_breaks_made_by_Ronnie_O%27Sullivan"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d6",
                "snippet": " ... He has twice reached the final of the Masters, winning once in 2011. In 2016, he became the first Asian player to reach the final of the World Championship.\n\nDing began playing snooker at age nine and rose to international prominence in 2002 after winning the Asian Under ... ",
                "title": "https://en.wikipedia.org/wiki/Ding_Junhui"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d7",
                "snippet": " ... 2014, 2016, 2017, 2021\n\nMark Anthony Selby (born 19 June 1983) is an English professional snooker player. Ranked world number one on multiple occasions, he has won a total of 24 ranking titles, placing him eighth on the all-time list of ranking tournament winners. He is a ... ",
                "title": "https://en.wikipedia.org/wiki/Mark_Selby"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d3",
                "snippet": " ... O'Sullivan, Higgins, and Williams, collectively known as the Class of '92 having all turned professional in 1992, all reached the quarter-finals for the first time since 2011. \"I think it's incredible that it's been 30 years and the three of us are better players ... ",
                "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
              }
            ],
            "query": "snooker players turned professional between 2011 2016"
          },
          {
            "cached": true,
            "hits": [
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d12",
                "snippet": " ... He had made 695 century breaks at the start of the 2013–14 snooker season. He made four in the European Tour 2013/2014 – Event 1 to take his century total to 699. His first-round match in the European Tour 2013/2014 – Event 3 was against Lyu ... ",
                "title": "https://en.wikipedia.org/wiki/Maximum_and_century_breaks_made_by_Ronnie_O%27Sullivan"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d7",
                "snippet": " ... Leicester, England\nprofessional: 1999–present\nhigh ranking: 1 (Sep 2011–Nov 2012, Dec 2012–Feb 2013, Apr–Jun 2013, May–Jul 2014, Aug–Dec 2014, Feb 2015–Mar 2019, Aug–Oct 2021, Nov 2021–Apr 2022)\nofficial maximums: 6\nranking wins: 24\nminor wins: 7\nworld champ: 2014 ... ",
                "title": "https://en.wikipedia.org/wiki/Mark_Selby"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d4",
                "snippet": " ... The year 2018 had the highest number of 147 breaks with 12, closely followed by 2012 with 11.\n\n💯 Consistency was seen in the years 2011, 2016, and 2019, with 9 maximum breaks each.\n\n| Year | 147s |\n\n|---|---|\n\n| 2010 | 7 |\n\n| 2011 | 9 |\n\n| 2012 | 11 |\n\n| 2013 | 6 |\n\n| 2014 | 8 |\n\n| 2015 | 6 |\n\n| 2016 ... ",
                "title": "https://www.olbg.com/blogs/snooker-maximum-breaks"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d3",
                "snippet": " ... 2023\n\nThe 2022 World Snooker Championship (officially the 2022 Betfred World Snooker Championship) was a professional snooker tournament that took place from 16 April to 2 May 2022 at the Crucible Theatre in Sheffield, England, the 46th consecutive year the World Snooker Championship was held at the venue ... ",
                "title": "https://en.wikipedia.org/wiki/2022_World_Snooker_Championship"
              },
              {
                "kind": "navigation_not_evidence",
                "previously_received": true,
                "ref": "d2",
                "snippet": " ... It was Robertson's sixth Triple Crown title, following his world title in 2010, his previous Masters victory in 2012, and his three UK Championship wins in 2013, 2015, and 2020. Robertson compiled two centuries and six other breaks of 50 or more in the final, while Hawkins ... ",
                "title": "https://en.wikipedia.org/wiki/2022_Masters_(snooker)"
              }
            ],
            "query": "snooker professional debut year 2012 2013 2014 2015"
          }
        ]
      },
      "round": 25,
      "tool": "search",
      "tool_call_id": "call_5515005bccdf48ccaf67b3a6"
    },
    "previous": "f382ecfc6173d8729cf177df5297047d94614f2ab10ab85a9af234559e517ddc",
    "hash": "641083825541d8a3e3fd9840dcc812c3efc75c8e037bad9b67deb22f16f2ac6f"
  },
  {
    "seq": 461,
    "kind": "round_end",
    "payload": {
      "group": "9a171a4072394c44d00080f60108eb46b9678f7bf5346c85a2e4af4630eef945",
      "notes": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
      "remaining": {
        "action_slots": 150,
        "backend_calls": 99,
        "model_calls": 39,
        "output_reservation": 43926
      },
      "round": 25
    },
    "previous": "641083825541d8a3e3fd9840dcc812c3efc75c8e037bad9b67deb22f16f2ac6f",
    "hash": "de09655278c288a6bd9fc54cc37e4457d341509b9e4cbab5e204610783a171e5"
  }
]
```
