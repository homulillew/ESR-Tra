# Discovery 05：q775 封存轨迹审阅

范围：仅本轮 q775 的 once-prose-reset-v1 与随后获准读取的已封存 baseline；未读取 gold、其他题或未封存槽，未调用模型。两臂均合法提交，但引用原文没有建立题目要求的完整关系。本报告不代替本轮 judge，也不沿用历史错误标签。

## 完整性与实际请求

两槽 SEALED 文件清单逐文件 SHA-256 全部通过，SQLite 内容对象和事件链验证通过；检查结束时 SEALED 原始字节不变。处理臂 366 个事件，链头 `9943199e3f5b8fe394e4cf6df5cc71e428d49a9897fa0bd1725abcd02ce49b49`。全部 31 个 request.body 解析结果与归档模型请求相同。原始请求、响应文件均包含在封存哈希检查内，没有修改任何原始文件。详见同目录 discovery05-q775-checks.json。

处理臂仅 R9 发生一次 reset，观察窗口为 R6–R8。这三轮 search 均有 executed=true、ok=true 的成功回执，完成组未新增 evidence；它们重复同一组 Alharthi / Celestial Bodies 查询，没有交付新的来源正文。事件记录保留组 R4–R8，五组 assistant.content 全部置 null，包括当时 first R4 和 latest R8；删除字符数依次为 598、301、289、289、289，共 1766。

逐个按 tool_call id 对齐所有实际请求中的历史组，验证 assistant 除该次 content 外与原始 round_end 组相同，工具调用参数和工具回执原文相同。R10 及随后请求中的仍可见原组恢复原始散文，不是永久删除；已被正常上下文保留规则移出的组不声称恢复到 wire。事件每个 original/projected message hash、removed content hash、rule hash 均重算匹配。R9 实际完整请求的规范 JSON 摘要匹配 wire_sha256 `4692638553c3e656ba8010d54bc46994308ce79c9f3004c98a9f1f49fbbe8532`。这是规范 JSON 哈希，不应与原始文件字节哈希混称。处理臂 16 请求、16 响应，无辅助模型调用。

## 处理臂的首次问题与引用边界

R3 已将 Obioma 作为候选，并识别普通 Booker 创立年份与题目“2000s”条件不符；R3 read d49 后，R4 首次收到 e1。R4 没有排除候选，却把普通 Booker 的入围书与 International Booker 的创立年份、获奖者组合起来。首次实质失败是奖项身份不一致仍继续连接关系，发生在 reset 前。

e1 是 ADVISORS 页面 [0,3000)，明确写 Obioma 出生于 Akure，两部小说及年份、Booker 入围和 30 种语言。它支持这个人的出生城市，但没有证明他就是满足题目所有条件的作者，也没有交付其成长城市与另一作者出生地的关系。

R5 read d71，R6 首次收到 e2。e2 是 TIME《The 42 Most Anticipated Books of Fall 2019》[0,3000)，涵盖导语、Dominicana、Quichotte、The Testaments 和 Ducks, Newburyport 开头。最终解释把 Celestial Bodies 获奖信息归到 e2，但该实际引用范围没有这些内容，更没有 Alharthi 出生地。检索命中整页不等于已经阅读相关段落。

R6–R8 散文及查询重复。R9 reset 后查询确实变化，从 Muscat / 2018 原版查询转为 `Jokha Alharthi born Akure Nigeria` 和 biography，但同时把尚未建立的关系当成前提：“Jokha Alharthi was born in Akure”。这不是发现独立候选，而是围绕原候选追加确认性搜索。R10–R11 再次重复 R9，随后仍未新增 read。R16 finish 提交 Akure、refs e1/e2；合法引用和合法终态不意味着关系论证成立。

## 当前 baseline 配对

两臂 R1 request.body 字节完全相同。R1 输出已经不同，R4 行为也在处理触发前明显分化，不能把这些差异归因 reset。baseline R4 明确说普通 Booker 与 International Booker 不同；R5–R9 多次重复同一冲突。R10 转向 The Fishermen / Marlon James 的 2015 获奖线索，仍保留 Obioma。R13、R14 才追加 read。

baseline e1 与处理臂 e1 是完全相同正文。e2 为 Grinnell《Distinguished Authors》前 3000 字符，末尾实际支持 Marlon James 与 2015 获奖书的关系。e3 为 The Atlantic《TheGreatAmericanNovels》前 2500 字符，只有榜单导语，没有最终解释声称的 2014 书目条目。R15 把题目“相同城市”的条件反过来当作 Obioma 在 Kingston 长大的证明，并将奖项创立年代冲突解释成题目措辞宽松。它也没有凭交付原文完成作者成长地关系。baseline 提交 Akure (Nigeria)、refs e1/e2/e3；两臂答案接近，不等于两臂均已证实答案。

| 观测 | baseline | once-prose-reset-v1 |
|---|---:|---:|
| policy 请求 | 15 | 16 |
| search / read / finish 工具调用 | 19 / 3 / 1 | 17 / 2 / 1 |
| query_execution 事件 | 52 | 38 |
| backend_request 事件（含检索与读取） | 43 | 32 |
| prompt tokens | 250955 | 266126 |
| completion tokens | 4415 | 2258 |
| cached tokens | 109312 | 126336 |
| total tokens | 255370 | 268384 |
| reset 次数 | 0 | 1 |

结论限于本对轨迹：reset 按约定进入一次实际请求并恢复原组，紧接着动作文本变化，但仍围绕未验证候选搜索，未修复奖项身份及作者关系。下一步若评估机制收益，应以本轮独立 judge 和更多预定配对为依据；本次可观察到的缺陷是把题目条件当作候选关系的证明，以及把整页命中误作引用区间内已读事实。
