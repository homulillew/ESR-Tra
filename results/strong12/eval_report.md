# 强策略标准评测 12 条（ESR vs baseline）

| 指标 | ESR | baseline |
|------|-----|----------|
| 提交率 | 100% | 100% |
| Accuracy (仅已提交) | 92% | 92% |
| Accuracy (含未提交) | 92% | 92% |
| 平均工具调用轮数 total | 8.2 | 3.3 |
| 平均 turns | 8.2 | 3.3 |
| 平均 search | 2.2 | 1.1 |
| 平均 open_page | 1.9 | 1.2 |
| 平均 read_evidence | 0.6 | 0.0 |
| 平均 update_state | 1.4 | 0.0 |
| 平均 verify_answer | 1.2 | 0.0 |

## 逐条判定

| qid | mode | outcome | submitted | correct | answer | gold | turns | tool_total |
|---|---|---|---|---|---|---|---|---|
| 186 | esr | submitted | True | True | Galacta: The Battle for Satu | Galacta: The Battle for Satu | 5 | 5 |
| 186 | baseline | submitted | True | True | Galacta: The Battle for Satu | Galacta: The Battle for Satu | 3 | 3 |
| 56 | esr | submitted | True | True | Last Christmas | Last Christmas | 5 | 5 |
| 56 | baseline | submitted | True | True | Last Christmas | Last Christmas | 3 | 3 |
| 1041 | esr | submitted | True | False | Bonang Matheba | Adaku | 5 | 5 |
| 1041 | baseline | submitted | True | False | Bonang Matheba | Adaku | 3 | 3 |
| 1089 | esr | submitted | True | True | Zius Galit | Zius Galit | 5 | 5 |
| 1089 | baseline | submitted | True | True | Zius Galit | Zius Galit | 3 | 3 |
| 1198 | esr | submitted | True | True | Robert Mugabe | Robert Mugabe | 10 | 10 |
| 1198 | baseline | submitted | True | True | Robert Mugabe | Robert Mugabe | 3 | 3 |
| 324 | esr | submitted | True | True | Svetlana Gromenkova | Svetlana Gromenkova | 5 | 5 |
| 324 | baseline | submitted | True | True | Svetlana Gromenkova | Svetlana Gromenkova | 3 | 3 |
| 364 | esr | submitted | True | True | Bada Lee | Bada Lee | 10 | 10 |
| 364 | baseline | submitted | True | True | Bada Lee | Bada Lee | 4 | 4 |
| 391 | esr | submitted | True | True | María Constanza Guzmán | María Constanza Guzmán | 6 | 6 |
| 391 | baseline | submitted | True | True | María Constanza Guzmán | María Constanza Guzmán | 4 | 4 |
| 517 | esr | submitted | True | True | Peter King | Peter King | 8 | 8 |
| 517 | baseline | submitted | True | True | Peter King | Peter King | 3 | 3 |
| 636 | esr | submitted | True | True | 2011 | 2011 | 12 | 12 |
| 636 | baseline | submitted | True | True | 2011 | 2011 | 3 | 3 |
| 772 | esr | submitted | True | True | Secretary | Secretary | 13 | 13 |
| 772 | baseline | submitted | True | True | Secretary | Secretary | 3 | 3 |
| 83 | esr | submitted | True | True | Joseph Dalton Hooker |  Joseph Dalton Hooker | 15 | 15 |
| 83 | baseline | submitted | True | True | Joseph Dalton Hooker |  Joseph Dalton Hooker | 5 | 5 |
