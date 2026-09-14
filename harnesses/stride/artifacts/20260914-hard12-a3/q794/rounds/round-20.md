# Round 20

[Actual request](../http/020/request.body) · [Actual response](../http/020/response.body) · [All interaction](../FULL_INTERACTION.md)

## Input visibility

```json
{
  "capacity": 90454,
  "compacted": false,
  "counter": {
    "calibrated_provider_tokens": false,
    "kind": "utf8_bytes"
  },
  "evidence_shelf": [],
  "final": false,
  "output_reservation": 4096,
  "request": "0a7f55cfee56ea2a1da3ced27ca9959bbd8ec1d225549c9e908c2e60b57cddb1",
  "round": 20,
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
            "id": "call_3bec28f063a64dc2a0be9d10",
            "index": 0,
            "type": "function"
          },
          {
            "function": {
              "arguments": "{\"queries\": [\"snooker player turned professional 2011 2012 2013 2014 2015 2016 list\", \"snooker players turned professional between 2011 2016\", \"snooker professional debut year 2012 2013 2014 2015\"]}",
              "name": "search"
            },
            "id": "call_5570f0ab01c44966a815af7d",
            "index": 1,
            "type": "function"
          }
        ]
      }
    }
  ],
  "created": 1789382493,
  "id": "chatcmpl-06459d97-f2cf-9166-924f-85d3bc3165a1",
  "model": "glm-5.2",
  "object": "chat.completion",
  "usage": {
    "prompt_tokens": 24646,
    "completion_tokens": 165,
    "reasoning_tokens": 0,
    "total_tokens": 24811,
    "cached_tokens": 19328,
    "prompt_tokens_details": {
      "cached_tokens": 19328
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
  "round": 20,
  "tool": "search",
  "tool_call_id": "call_3bec28f063a64dc2a0be9d10"
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
  "round": 20,
  "tool": "search",
  "tool_call_id": "call_5570f0ab01c44966a815af7d"
}
```

## Full event records for this request interval

```json
[
  {
    "seq": 366,
    "kind": "model_request",
    "payload": {
      "capacity": 90454,
      "compacted": false,
      "counter": {
        "calibrated_provider_tokens": false,
        "kind": "utf8_bytes"
      },
      "evidence_shelf": [],
      "final": false,
      "output_reservation": 4096,
      "request": "0a7f55cfee56ea2a1da3ced27ca9959bbd8ec1d225549c9e908c2e60b57cddb1",
      "round": 20,
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
    "previous": "7b502af0c43633a82a56ef5bd624a50b99739401a57ef5762b9d6921832858ba",
    "hash": "b10b5f7b4215fe743fdffed1a4da8678d428878c485147c1acc634fd590e3652"
  },
  {
    "seq": 367,
    "kind": "model_response",
    "payload": {
      "elapsed_seconds": 4.1595465000136755,
      "output_charged": 165,
      "raw": "eee9fbd1802b0a7c893eb0671646eb423fc78c2deef96fe165fa642793c383f8",
      "response_model": "glm-5.2",
      "round": 20,
      "usage": {
        "cache_read_tokens": 19328,
        "input_tokens": 24646,
        "output_tokens": 165
      }
    },
    "previous": "b10b5f7b4215fe743fdffed1a4da8678d428878c485147c1acc634fd590e3652",
    "hash": "34ea68abcf85f5fd00f9d9d5d5e8c959c611a091b8a116e9978ae41e5a476c8d"
  },
  {
    "seq": 368,
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
      "round": 20
    },
    "previous": "34ea68abcf85f5fd00f9d9d5d5e8c959c611a091b8a116e9978ae41e5a476c8d",
    "hash": "be765609acd5cd66f735fb730beae304c0d83bbb4acfe68d9b5ab7539e515278"
  },
  {
    "seq": 369,
    "kind": "navigation_ack",
    "payload": {
      "object": "b27ec6fbffd35b00fa1911642c474e4f260d8f3dc0a5e48b0e81e875f2c5b682",
      "round": 20,
      "source_round": 19
    },
    "previous": "be765609acd5cd66f735fb730beae304c0d83bbb4acfe68d9b5ab7539e515278",
    "hash": "ba8e32a852c18c04bdeba69ddea0a1e4168b959997db3c720b04f6185170b38e"
  },
  {
    "seq": 370,
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
      "round": 20,
      "top_k": 5
    },
    "previous": "ba8e32a852c18c04bdeba69ddea0a1e4168b959997db3c720b04f6185170b38e",
    "hash": "2286c117359699c2b07835a559d0af27177fa01a9a2f80fee0e6bc2074ccd86c"
  },
  {
    "seq": 371,
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
      "round": 20,
      "top_k": 5
    },
    "previous": "2286c117359699c2b07835a559d0af27177fa01a9a2f80fee0e6bc2074ccd86c",
    "hash": "180f18a2ab7fbfe14223044cece217d6bb1fd4ae8fa91f40d28be035af4a261f"
  },
  {
    "seq": 372,
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
      "round": 20,
      "top_k": 5
    },
    "previous": "180f18a2ab7fbfe14223044cece217d6bb1fd4ae8fa91f40d28be035af4a261f",
    "hash": "e5a3700c9738ff8416f65ec4664862f18cd5244467670731803399da5db519d3"
  },
  {
    "seq": 373,
    "kind": "action_execution",
    "payload": {
      "object": "92ae90f13e232446bfccc8454e631938a9a516c3a884ca2d64f29f9390067218",
      "round": 20,
      "tool_call_id": "call_3bec28f063a64dc2a0be9d10"
    },
    "previous": "e5a3700c9738ff8416f65ec4664862f18cd5244467670731803399da5db519d3",
    "hash": "23c0b9f434aa8ae06f07866e96d39d9da4fdb9ac9fef88cc9c65a26b583807b5"
  },
  {
    "seq": 374,
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
      "round": 20,
      "top_k": 5
    },
    "previous": "23c0b9f434aa8ae06f07866e96d39d9da4fdb9ac9fef88cc9c65a26b583807b5",
    "hash": "1129ddf2cc77dc49c9b4247cc7c4997f17591aa14ee59e06bdb5d1314024b201"
  },
  {
    "seq": 375,
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
      "round": 20,
      "top_k": 5
    },
    "previous": "1129ddf2cc77dc49c9b4247cc7c4997f17591aa14ee59e06bdb5d1314024b201",
    "hash": "d636ca0cdd4ad6526021baa38915b27512926e6c5d42881652a0f6806422c177"
  },
  {
    "seq": 376,
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
      "round": 20,
      "top_k": 5
    },
    "previous": "d636ca0cdd4ad6526021baa38915b27512926e6c5d42881652a0f6806422c177",
    "hash": "33d0518411cb7779dfd1fe0123a58dd44fbefbfbd17e99a8ffa264b1753eff62"
  },
  {
    "seq": 377,
    "kind": "action_execution",
    "payload": {
      "object": "91f6ed166752c327f7567e287229ee9b05c8dd1829b3338e340b8bf397e59fdc",
      "round": 20,
      "tool_call_id": "call_5570f0ab01c44966a815af7d"
    },
    "previous": "33d0518411cb7779dfd1fe0123a58dd44fbefbfbd17e99a8ffa264b1753eff62",
    "hash": "71920a1c6339652a45ce9cb0be2172f9a93078264ac0b91148e709bf7d9c80b7"
  },
  {
    "seq": 378,
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
      "round": 20
    },
    "previous": "71920a1c6339652a45ce9cb0be2172f9a93078264ac0b91148e709bf7d9c80b7",
    "hash": "a9d0e5e91cf720b13fc9dce80a6eca714d4da3f4c84c52ee4612aa6b76112faf"
  },
  {
    "seq": 379,
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
      "round": 20,
      "tool": "search",
      "tool_call_id": "call_3bec28f063a64dc2a0be9d10"
    },
    "previous": "a9d0e5e91cf720b13fc9dce80a6eca714d4da3f4c84c52ee4612aa6b76112faf",
    "hash": "65e16190c9e2a4e11079b5151be4beef7b4596c2fe75748c976f52bb97ab45c6"
  },
  {
    "seq": 380,
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
      "round": 20,
      "tool": "search",
      "tool_call_id": "call_5570f0ab01c44966a815af7d"
    },
    "previous": "65e16190c9e2a4e11079b5151be4beef7b4596c2fe75748c976f52bb97ab45c6",
    "hash": "527807868194dd0b7f6c50926232527d3c2275216f92d63f85a5abd1b934532a"
  },
  {
    "seq": 381,
    "kind": "round_end",
    "payload": {
      "group": "de605f95bdaa0aa6ca47a2ddfaa2b38c72569f4ec80a5648031fdceed145bf0f",
      "notes": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
      "remaining": {
        "action_slots": 160,
        "backend_calls": 99,
        "model_calls": 44,
        "output_reservation": 44751
      },
      "round": 20
    },
    "previous": "527807868194dd0b7f6c50926232527d3c2275216f92d63f85a5abd1b934532a",
    "hash": "9beca5a50ce5bfead4672f134f6ab7ebc077ce97ad00d57801bf0cfd87556055"
  }
]
```
