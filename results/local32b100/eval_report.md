# 本地 Qwen3-32B 强策略标准评测（随机100条，ESR vs baseline）

| 指标 | ESR | baseline |
|------|-----|----------|
| 提交率 | 47% | 100% |
| Accuracy (仅已提交) | 23% | 15% |
| Accuracy (含未提交) | 11% | 15% |
| 平均工具调用轮数 total | 58.1 | 4.3 |
| 平均 turns | 58.1 | 4.3 |
| 平均 search | 32.9 | 1.6 |
| 平均 open_page | 13.1 | 1.8 |
| 平均 read_evidence | 0.1 | 0.0 |
| 平均 update_state | 5.6 | 0.0 |
| 平均 verify_answer | 6.0 | 0.0 |

## 逐条判定

| qid | mode | outcome | submitted | correct | answer | gold | turns | tool_total |
|---|---|---|---|---|---|---|---|---|
| 1007 | baseline | submitted | True | False | Gautam Adani | Ahmed Ezz | 4 | 4 |
| 1007 | esr | submitted | True | True | Ahmed Ezz | Ahmed Ezz | 13 | 13 |
| 1012 | baseline | submitted | True | False | 13 October 2023 | 22 September 2023 | 3 | 3 |
| 1012 | esr | submitted | True | False | 21 August 2020 | 22 September 2023 | 5 | 5 |
| 1022 | baseline | submitted | True | False | The information provided doe | 2300; Sara Beatriz Maldonado | 5 | 5 |
| 1022 | esr | submitted | True | False | The age of the objects found | 2300; Sara Beatriz Maldonado | 5 | 5 |
| 1026 | baseline | submitted | True | False | Allison Fromm | Linus Lerner | 3 | 3 |
| 1026 | esr | max_turns | False | False |  | Linus Lerner | 100 | 100 |
| 1027 | baseline | submitted | True | False | Based on the evidence, Greg  | 17 | 3 | 3 |
| 1027 | esr | max_turns | False | False |  | 17 | 100 | 100 |
| 1076 | baseline | submitted | True | False | The MH de Young Museum in Sa | 1939 | 3 | 3 |
| 1076 | esr | submitted | True | False | Evidence does not provide th | 1939 | 9 | 9 |
| 1108 | baseline | submitted | True | True | The aircraft's registration  | RDPL-34062 | 3 | 3 |
| 1108 | esr | submitted | True | False | The aircraft's registration  | RDPL-34062 | 5 | 5 |
| 1119 | baseline | submitted | True | False | Based on the information pro | Micro Man | 9 | 9 |
| 1119 | esr | submitted | True | False | The evidence still does not  | Micro Man | 23 | 23 |
| 1127 | baseline | submitted | True | True | Macrocheira kaempferi | Macrocheira Kaempferi | 12 | 12 |
| 1127 | esr | submitted | True | True | Macrocheira kaempferi | Macrocheira Kaempferi | 33 | 33 |
| 1139 | baseline | submitted | True | False | The non-English word used fo |  Ukudlanga | 4 | 4 |
| 1139 | esr | submitted | True | False | ulwaluko |  Ukudlanga | 5 | 5 |
| 1201 | baseline | submitted | True | False | Tatiana Toro | Govardhan Asrani | 3 | 3 |
| 1201 | esr | max_turns | False | False |  | Govardhan Asrani | 100 | 100 |
| 1203 | baseline | submitted | True | False | The audio technician respons | Cassano Thruston | 3 | 3 |
| 1203 | esr | submitted | True | False | Petri Alanko and Martin Stig | Cassano Thruston | 5 | 5 |
| 1206 | baseline | submitted | True | False | Potential functional bakery  | Development of waffle with f | 3 | 3 |
| 1206 | esr | max_turns | False | False |  | Development of waffle with f | 100 | 100 |
| 1209 | baseline | submitted | True | False | From Dusk Till Dawn: The Ser | Reset | 3 | 3 |
| 1209 | esr | max_turns | False | False |  | Reset | 100 | 100 |
| 1211 | baseline | submitted | True | False | Based on the information pro | 20 tantos | 5 | 5 |
| 1211 | esr | submitted | True | False | The series is not identified | 20 tantos | 12 | 12 |
| 1226 | baseline | submitted | True | True | Yumi Arai | Yumi Arai | 3 | 3 |
| 1226 | esr | max_turns | False | False |  | Yumi Arai | 100 | 100 |
| 1230 | baseline | submitted | True | True | Gertrude Pownall | Gertrude Pownall | 4 | 4 |
| 1230 | esr | submitted | True | False | Alexandra Minna Stern | Gertrude Pownall | 15 | 15 |
| 1236 | baseline | submitted | True | False | Days of Our Lives | Defendant | 3 | 3 |
| 1236 | esr | max_turns | False | False |  | Defendant | 100 | 100 |
| 1252 | baseline | submitted | True | False | The 2010 Winter Olympics, he | August 13-August 29, 2004 | 6 | 6 |
| 1252 | esr | max_turns | False | False |  | August 13-August 29, 2004 | 100 | 100 |
| 1253 | baseline | submitted | True | True | Haroon | Haroon | 3 | 3 |
| 1253 | esr | submitted | True | True | Haroon | Haroon | 5 | 5 |
| 130 | baseline | submitted | True | True | The pseudonym of the writer  | Esther Wyndham | 3 | 3 |
| 130 | esr | submitted | True | True | Esther Wyndham | Esther Wyndham | 6 | 6 |
| 15 | baseline | submitted | True | True | Romanian Statistical Review | Romanian Statistical Review | 3 | 3 |
| 15 | esr | submitted | True | True | Romanian Statistical Review | Romanian Statistical Review | 5 | 5 |
| 161 | baseline | submitted | True | False | Based on the details provide | Kune Rima | 5 | 5 |
| 161 | esr | max_turns | False | False |  | Kune Rima | 100 | 100 |
| 175 | baseline | submitted | True | False | League Championship Series ( | Cocomelon | 3 | 3 |
| 175 | esr | submitted | True | False | The evidence does not provid | Cocomelon | 14 | 14 |
| 18 | baseline | submitted | True | False | Ryan Iafigliola | Lillian Karabaic | 5 | 5 |
| 18 | esr | submitted | True | False | Not found in the provided ev | Lillian Karabaic | 5 | 5 |
| 199 | baseline | submitted | True | False | The song is 'There Must Be A | Gae Lowe (Le Duel) | 3 | 3 |
| 199 | esr | max_turns | False | False |  | Gae Lowe (Le Duel) | 100 | 100 |
| 211 | baseline | submitted | True | True | Thomas Ngomba | Thomas Ngomba | 3 | 3 |
| 211 | esr | submitted | True | True | Thomas Ngomba | Thomas Ngomba | 5 | 5 |
| 239 | baseline | submitted | True | False | Isabelle | Jun | 4 | 4 |
| 239 | esr | max_turns | False | False |  | Jun | 100 | 100 |
| 240 | baseline | submitted | True | False | Based on the information pro | Kwabena Yeboah | 5 | 5 |
| 240 | esr | submitted | True | False | The man who accompanied them | Kwabena Yeboah | 5 | 5 |
| 250 | baseline | submitted | True | False | Ravichandran Ashwin | Pragyan Ojha | 4 | 4 |
| 250 | esr | max_turns | False | False |  | Pragyan Ojha | 100 | 100 |
| 265 | baseline | submitted | True | False | The dimensions of the art pi | 5" x 5" | 3 | 3 |
| 265 | esr | max_turns | False | False |  | 5" x 5" | 100 | 100 |
| 266 | baseline | submitted | True | False | The name of the blog is Shak | In Asian Spaces  | 3 | 3 |
| 266 | esr | submitted | True | True | In Asian Spaces | In Asian Spaces  | 15 | 15 |
| 275 | baseline | submitted | True | False | Anheuser-Busch | Union Carbide and Carbon Cor | 4 | 4 |
| 275 | esr | max_turns | False | False |  | Union Carbide and Carbon Cor | 100 | 100 |
| 280 | baseline | submitted | True | False | The full name of the away te | Sol Campbell | 6 | 6 |
| 280 | esr | max_turns | False | False |  | Sol Campbell | 100 | 100 |
| 282 | baseline | submitted | True | False | The information provided doe | BX 293A | 4 | 4 |
| 282 | esr | submitted | True | False | The information needed to de | BX 293A | 5 | 5 |
| 287 | baseline | submitted | True | False | 05/11/1864 | 07/28/1865 | 4 | 4 |
| 287 | esr | max_turns | False | False |  | 07/28/1865 | 100 | 100 |
| 297 | baseline | submitted | True | False | The Godfather | Insomnia | 6 | 6 |
| 297 | esr | submitted | True | False | The evidence does not specif | Insomnia | 21 | 21 |
| 301 | baseline | submitted | True | False | The information provided doe | Nwoko | 6 | 6 |
| 301 | esr | submitted | True | False | No relevant information foun | Nwoko | 5 | 5 |
| 328 | baseline | submitted | True | False | The individual was born on S | December 1991 | 3 | 3 |
| 328 | esr | max_turns | False | False |  | December 1991 | 100 | 100 |
| 362 | baseline | submitted | True | False | Scooby-Doo | Captain Star | 3 | 3 |
| 362 | esr | max_turns | False | False |  | Captain Star | 100 | 100 |
| 380 | baseline | submitted | True | True | The exact height of the pott | 46.30 centimetres | 4 | 4 |
| 380 | esr | submitted | True | False | 46.30 cm | 46.30 centimetres | 8 | 8 |
| 389 | baseline | submitted | True | False | Based on the information pro | Benedict Timothy Carlton Cum | 4 | 4 |
| 389 | esr | max_turns | False | False |  | Benedict Timothy Carlton Cum | 100 | 100 |
| 390 | baseline | submitted | True | False | The name of the track that a | Estou Livre | 6 | 6 |
| 390 | esr | max_turns | False | False |  | Estou Livre | 100 | 100 |
| 392 | baseline | submitted | True | False | Dubna | Bedford | 5 | 5 |
| 392 | esr | max_turns | False | False |  | Bedford | 100 | 100 |
| 393 | baseline | submitted | True | True | The full name of the advisor | Alexander Yarin | 5 | 5 |
| 393 | esr | submitted | True | True | Alexander Yarin | Alexander Yarin | 9 | 9 |
| 394 | baseline | submitted | True | False | Based on the information pro | wing three-quarter | 3 | 3 |
| 394 | esr | submitted | True | False | The evidence does not provid | wing three-quarter | 14 | 14 |
| 408 | baseline | submitted | True | False | The make and model of the fi | Atari 130XE | 3 | 3 |
| 408 | esr | submitted | True | False | Atari computer with 128KB of | Atari 130XE | 5 | 5 |
| 416 | baseline | submitted | True | False | 无法从提供的信息中确定最后一篇论文致谢部分中提到的第三个 | Hsiang Sing Naik | 3 | 3 |
| 416 | esr | submitted | True | False | Kelsee Baranowski | Hsiang Sing Naik | 25 | 25 |
| 421 | baseline | submitted | True | False | Kozuki Foundation | Smilegate Foundation | 4 | 4 |
| 421 | esr | max_turns | False | False |  | Smilegate Foundation | 100 | 100 |
| 426 | baseline | submitted | True | False | The actor's name is Finn Wol | Noor Taher | 6 | 6 |
| 426 | esr | submitted | True | False | No sufficient evidence found | Noor Taher | 13 | 13 |
| 432 | baseline | submitted | True | False | Based on the information pro | Aaron Strick | 5 | 5 |
| 432 | esr | max_turns | False | False |  | Aaron Strick | 100 | 100 |
| 434 | baseline | submitted | True | False | Mimi | Madhumalti | 4 | 4 |
| 434 | esr | max_turns | False | False |  | Madhumalti | 100 | 100 |
| 467 | baseline | submitted | True | False | The first names of the two a | Robert and Washington   Titl | 5 | 5 |
| 467 | esr | max_turns | False | False |  | Robert and Washington   Titl | 100 | 100 |
| 473 | baseline | submitted | True | False | The blog post about the home | 28 October 2014 | 4 | 4 |
| 473 | esr | max_turns | False | False |  | 28 October 2014 | 100 | 100 |
| 481 | baseline | submitted | True | False | The individual is Peanut (Yo | 1986, Portugal | 4 | 4 |
| 481 | esr | max_turns | False | False |  | 1986, Portugal | 100 | 100 |
| 498 | baseline | submitted | True | False | Based on the provided detail | Singh Is Bliing. | 5 | 5 |
| 498 | esr | max_turns | False | False |  | Singh Is Bliing. | 100 | 100 |
| 503 | baseline | submitted | True | False | The company in question is H | Winky | 9 | 9 |
| 503 | esr | max_turns | False | False |  | Winky | 100 | 100 |
| 514 | baseline | submitted | True | False | Paul Winfield | Maximilian Josef Sommer | 5 | 5 |
| 514 | esr | max_turns | False | False |  | Maximilian Josef Sommer | 100 | 100 |
| 538 | baseline | submitted | True | True | The title of the book is 'Pr | Practical Mechanics for Boys | 3 | 3 |
| 538 | esr | submitted | True | True | Practical Mechanics for Boys | Practical Mechanics for Boys | 26 | 26 |
| 543 | baseline | submitted | True | False | The player was on loan to Ra | Arsenal Tula | 5 | 5 |
| 543 | esr | submitted | True | False | Based on the evidence, the s | Arsenal Tula | 63 | 63 |
| 546 | baseline | submitted | True | False | Ronnie O'Sullivan | Ding Junhui | 4 | 4 |
| 546 | esr | max_turns | False | False |  | Ding Junhui | 100 | 100 |
| 550 | baseline | submitted | True | False | The lover's name was Suzanne | Snowy Moshoeshoe | 3 | 3 |
| 550 | esr | max_turns | False | False |  | Snowy Moshoeshoe | 100 | 100 |
| 555 | baseline | submitted | True | False | The Sea | Foreign Fruit | 7 | 7 |
| 555 | esr | submitted | True | False | There is no evidence in the  | Foreign Fruit | 9 | 9 |
| 580 | baseline | submitted | True | False | Friends | You're the Worst | 3 | 3 |
| 580 | esr | submitted | True | False | Friends | You're the Worst | 5 | 5 |
| 583 | baseline | submitted | True | False | 2019 Grant Recipients | New mural in Coghlan painted | 3 | 3 |
| 583 | esr | submitted | True | False | 2019 Grant Recipients | New mural in Coghlan painted | 5 | 5 |
| 591 | baseline | submitted | True | False | Based on the information pro | German University in Cairo | 3 | 3 |
| 591 | esr | submitted | True | False | Insufficient evidence to det | German University in Cairo | 9 | 9 |
| 600 | baseline | submitted | True | False | John Philip Sousa | Hermann Göring | 3 | 3 |
| 600 | esr | max_turns | False | False |  | Hermann Göring | 100 | 100 |
| 624 | baseline | submitted | True | False | Based on the information pro | 65% | 5 | 5 |
| 624 | esr | submitted | True | False | 66% | 65% | 9 | 9 |
| 628 | baseline | submitted | True | False | The information provided doe | Brazuca | 4 | 4 |
| 628 | esr | submitted | True | False | The short film in question i | Brazuca | 9 | 9 |
| 63 | baseline | submitted | True | False | Renfrew | St. Louis | 5 | 5 |
| 63 | esr | max_turns | False | False |  | St. Louis | 100 | 100 |
| 638 | baseline | submitted | True | False | Coty | Parle | 3 | 3 |
| 638 | esr | max_turns | False | False |  | Parle | 100 | 100 |
| 653 | baseline | submitted | True | False | 2001 | 2005 | 3 | 3 |
| 653 | esr | max_turns | False | False |  | 2005 | 100 | 100 |
| 664 | baseline | submitted | True | False | Celtic | FC Krasnodar | 8 | 8 |
| 664 | esr | submitted | True | False | Bolton Wanderers | FC Krasnodar | 11 | 11 |
| 67 | baseline | submitted | True | False | ODI no #12345 | ODI no. 1880 | 6 | 6 |
| 67 | esr | max_turns | False | False |  | ODI no. 1880 | 100 | 100 |
| 685 | baseline | submitted | True | False | San Jose Earthquakes v D.C.  | Oldham Athletic v Southampto | 3 | 3 |
| 685 | esr | max_turns | False | False |  | Oldham Athletic v Southampto | 100 | 100 |
| 696 | baseline | submitted | True | False | Brendan O'Leary | Cesar Dominguez | 3 | 3 |
| 696 | esr | max_turns | False | False |  | Cesar Dominguez | 100 | 100 |
| 711 | baseline | submitted | True | False | Kieran | Roberto | 3 | 3 |
| 711 | esr | max_turns | False | False |  | Roberto | 100 | 100 |
| 719 | baseline | submitted | True | False | Adrian Belew | Talvin Singh | 3 | 3 |
| 719 | esr | max_turns | False | False |  | Talvin Singh | 100 | 100 |
| 726 | baseline | submitted | True | False | The cricketer who matches th | 2010 | 3 | 3 |
| 726 | esr | max_turns | False | False |  | 2010 | 100 | 100 |
| 753 | baseline | submitted | True | False | Based on the information pro | NC Dinos | 4 | 4 |
| 753 | esr | submitted | True | False | No specific sports team foun | NC Dinos | 9 | 9 |
| 778 | baseline | submitted | True | False | The question asks for the ag | 21 | 4 | 4 |
| 778 | esr | submitted | True | False | 22 | 21 | 9 | 9 |
| 785 | baseline | submitted | True | False | The full name of the other c | Rona Weerasuriya | 4 | 4 |
| 785 | esr | submitted | True | False | The evidence does not provid | Rona Weerasuriya | 5 | 5 |
| 805 | baseline | submitted | True | False | Based on the provided inform | Ana Djaimilia dos Santos Per | 8 | 8 |
| 805 | esr | max_turns | False | False |  | Ana Djaimilia dos Santos Per | 100 | 100 |
| 806 | baseline | submitted | True | False | The question cannot be answe | Mack, Sheffield | 5 | 5 |
| 806 | esr | submitted | True | False | The surnames of the producti | Mack, Sheffield | 5 | 5 |
| 838 | baseline | submitted | True | False | The first name and surname o | Sandie Hatch | 3 | 3 |
| 838 | esr | submitted | True | False | The information required to  | Sandie Hatch | 5 | 5 |
| 847 | baseline | submitted | True | False | Based on the evidence provid | Urza Acharya | 5 | 5 |
| 847 | esr | max_turns | False | False |  | Urza Acharya | 100 | 100 |
| 853 | baseline | submitted | True | True | Based on the information pro | Richard C. Larson | 10 | 10 |
| 853 | esr | max_turns | False | False |  | Richard C. Larson | 100 | 100 |
| 864 | baseline | submitted | True | False | Based on the information pro | Lyric Geography | 4 | 4 |
| 864 | esr | submitted | True | False | Insufficient evidence to det | Lyric Geography | 9 | 9 |
| 883 | baseline | submitted | True | False | The Addams Family (video gam | Oscar | 4 | 4 |
| 883 | esr | max_turns | False | False |  | Oscar | 100 | 100 |
| 885 | baseline | submitted | True | False | Idil Biret's mother's full n | Leman Biret | 5 | 5 |
| 885 | esr | submitted | True | False | Martha Argerich's mother's f | Leman Biret | 5 | 5 |
| 904 | baseline | submitted | True | False | 2009 | 1980 | 8 | 8 |
| 904 | esr | max_turns | False | False |  | 1980 | 100 | 100 |
| 907 | baseline | submitted | True | True | The historical structure in  | Vasco da Gama Pillar | 3 | 3 |
| 907 | esr | max_turns | False | False |  | Vasco da Gama Pillar | 100 | 100 |
| 915 | baseline | submitted | True | False | The character she played in  | Miss Ealand | 4 | 4 |
| 915 | esr | max_turns | False | False |  | Miss Ealand | 100 | 100 |
| 928 | baseline | submitted | True | False | The name of the essay is not | Qoyllur Rit'i - The Snow Sta | 3 | 3 |
| 928 | esr | max_turns | False | False |  | Qoyllur Rit'i - The Snow Sta | 100 | 100 |
| 932 | baseline | submitted | True | True | 10.3389/fphar.2016.00258 | 10.3389/fphar.2016.00258 | 3 | 3 |
| 932 | esr | submitted | True | True | 10.3389/fphar.2016.00258 | 10.3389/fphar.2016.00258 | 5 | 5 |
| 959 | baseline | submitted | True | False | Donald Sutherland | Salman Shah | 4 | 4 |
| 959 | esr | max_turns | False | False |  | Salman Shah | 100 | 100 |
| 963 | baseline | submitted | True | True | Rod Crist | Rod Crist | 7 | 7 |
| 963 | esr | submitted | True | True | Rod Crist | Rod Crist | 11 | 11 |
| 969 | baseline | submitted | True | False | The entertainer is Sean Conn | Richard Andrew Palethorpe-To | 3 | 3 |
| 969 | esr | max_turns | False | False |  | Richard Andrew Palethorpe-To | 100 | 100 |
| 972 | baseline | submitted | True | False | The reality TV series for wh | Sister Wives | 4 | 4 |
| 972 | esr | max_turns | False | False |  | Sister Wives | 100 | 100 |
| 98 | baseline | submitted | True | False | The information provided doe | Laura | 4 | 4 |
| 98 | esr | submitted | True | False | Not enough information to de | Laura | 5 | 5 |
