# 强策略标准评测 12 条（api 自动，ESR vs baseline）

| 指标 | ESR | baseline |
|------|-----|----------|
| 提交率 | 92% | 100% |
| Accuracy (仅已提交) | 100% | 83% |
| Accuracy (含未提交) | 92% | 83% |
| 平均工具调用轮数 total | 15.2 | 6.2 |
| 平均 turns | 15.2 | 6.2 |
| 平均 search | 4.0 | 3.2 |
| 平均 open_page | 2.9 | 2.1 |
| 平均 read_evidence | 0.0 | 0.0 |
| 平均 update_state | 5.0 | 0.0 |
| 平均 verify_answer | 2.2 | 0.0 |

## 逐条判定

| qid | mode | outcome | submitted | correct | answer | gold | turns | tool_total |
|---|---|---|---|---|---|---|---|---|
| 186 | esr | submitted | True | True | Galacta: The Battle for Satu | Galacta: The Battle for Satu | 8 | 8 |
| 186 | baseline | submitted | True | True | Galacta: The Battle for Satu | Galacta: The Battle for Satu | 3 | 3 |
| 56 | esr | submitted | True | True | Last Christmas | Last Christmas | 9 | 9 |
| 56 | baseline | submitted | True | True | Last Christmas | Last Christmas | 8 | 8 |
| 1041 | esr | submitted | True | True | Adaku | Adaku | 5 | 5 |
| 1041 | baseline | submitted | True | True | Adaku | Adaku | 3 | 3 |
| 1089 | esr | submitted | True | True | Zius Galit | Zius Galit | 11 | 11 |
| 1089 | baseline | submitted | True | True | Zius Galit | Zius Galit | 3 | 3 |
| 1198 | esr | submitted | True | True | Robert Mugabe | Robert Mugabe | 9 | 9 |
| 1198 | baseline | submitted | True | True | Robert Mugabe | Robert Mugabe | 5 | 5 |
| 324 | esr | submitted | True | True | Svetlana Gromenkova | Svetlana Gromenkova | 11 | 11 |
| 324 | baseline | submitted | True | True | Svetlana Gromenkova | Svetlana Gromenkova | 6 | 6 |
| 364 | esr | submitted | True | True | Bada Lee | Bada Lee | 30 | 30 |
| 364 | baseline | submitted | True | True | Bada Lee | Bada Lee | 19 | 19 |
| 391 | esr | submitted | True | True | María Constanza Guzmán | María Constanza Guzmán | 9 | 9 |
| 391 | baseline | submitted | True | True | María Constanza Guzmán | María Constanza Guzmán | 5 | 5 |
| 517 | esr | submitted | True | True | Peter King Nzioki | Peter King | 42 | 42 |
| 517 | baseline | submitted | True | False | Peter Sarsgaard | Peter King | 8 | 8 |
| 636 | esr | max_turns | False | False |  | 2011 | 30 | 30 |
| 636 | baseline | submitted | True | False | 2020 | 2011 | 3 | 3 |
| 772 | esr | submitted | True | True | 秘书（secretary） | Secretary | 8 | 8 |
| 772 | baseline | submitted | True | True | 根据2021年3月的文章《Ballet Rising》（ | Secretary | 6 | 6 |
| 83 | esr | submitted | True | True | Joseph Dalton Hooker |  Joseph Dalton Hooker | 10 | 10 |
| 83 | baseline | submitted | True | True | Joseph Dalton Hooker |  Joseph Dalton Hooker | 6 | 6 |
