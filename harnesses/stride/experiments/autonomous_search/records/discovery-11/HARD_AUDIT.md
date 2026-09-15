# Discovery 11 难题独立轨迹与来源审阅

审阅对象为已封存的 q775、q774 两臂，以及八个策略槽的机械完整性。代码身份为 f29c23769e48e6aca6434b77b9aa20cef6881b45。本审阅没有读取 judge、标准答案或 RESULTS judgments，没有调用模型。下文“支持”指实际交付原文对关系的支持，不是判分结论。

## 完整性与持续省略

`audit_continuous_stage.py` 在全局 POLICY_SEALED 后运行通过：8 个 SQLite 链、440 个 seal 文件、2144 个归档事件、78 对策略 HTTP 请求/响应（156 个 body）、11 个不同证据窗口。四组 R1 请求分别逐字节相同；所有 baseline 均无投影事件。没有自动取文事件或 capacity withholding。

审阅器按 retained_group_rounds 取原始 round_end 组，重算 project_continuous，核对 changes、实际 wire_sha256、归档请求与 HTTP body；投影后的完整 native 历史与实际请求一致。工具 arguments、回执、原始窗口及已有 provider reasoning 字段保留，原档未被覆盖；结构化 evidence 对象与 snapshot 范围/hash、visible_evidence、delivery_ack 一致。没有用正文字符串出现代替实际交付判断。控制阶段与归档 workflow 相符；这里不声称不同轨迹的 control 反事实相同。

q775 处理臂 R2 删除保留的 R1 散文，R3 删除 R1/R2；随后容量压缩改变保留组，但每次保留组均投影。R16 FINAL 保留 R11–15，五组全部删除散文。q774 及两个控制题的处理臂也通过逐请求及 FINAL 检查。删除针对实际 wire 可见 content，未把原本不上 wire 的推理当作删除收益。

两道难题均在 R1 响应已分歧，早于首次有历史可删除的 R2。q775 的 R1 一个响应发两次 search、另一个一次，查询和 top_k 已不同；q774 查询和 top_k 使用也不同。不能把这些起始搜索差异、随后全部成本差异直接归因于持续省略。

## q775：基线提交局部有据、完整关系未证；处理臂仍混淆两本书

基线 R2 search 返回 d40 的 Obioma 两本小说、年份、Booker shortlist 与 30 种语言导航；R3 称其 strong lead，并原生 read d40。e1=[0,3000) 在 R4 首次交付，确实写 Chigozie Obioma 生于 Akure、两部小说为 2015/2019、入围 Booker、译成 30 种语言。这个窗口没有建立题目要求的另一获奖书、前一年出版、同一奖项及“另一作者出生地=首作者成长地”。

R4 已明确识别“that's the Booker Prize, not the International Booker Prize”，却没有据此排除或核验候选。R4–8 反复重写同一解释；R5–8 两组查询精确重复；R9–13 继续 International Booker 查询。共 56 条有效列表中的查询字符串，仅 23 条不同，发生四次 duplicate_query_blocked 和一次 arguments_invalid。R14 仍复述奖项冲突，随后合法 finish Akure refs=[e1]。因此出生地这个局部事实有原文，作为完整题目答案的实体识别与关系链未获支持。引用有效不能消除作者选择错误。

处理臂 R2 在尚无原文时引入 Han Kang / Hwang Sok-yong；R3 转成“Han Kang 生于 Gwangju，寻找 2016 年出版、作者成长于 Gwangju 的另一本书”。d33 在 R2 搜索已出现，R4 才 read，e1=[3585,5590) 于 R5 交付，明确包含 Gwangju 为 Kang 出生地。模型称将读 Wikipedia，实际 d33 是讨论韩江作品的文章，文档身份与计划描述不一致。

R5 read d5 得 e2=[25007,27249)，R6 交付；这段实际是 Booker 关联奖项尾部，含 Man Asian Literary Prize 于 2007 年成立，没有所求 International Booker 2016 shortlist。R7 再读 d33，e3=[0,3000) 于 R8 交付，清楚区分《素食者》韩文 2007、英文 2015、国际布克获奖 2016，以及《白》2018 入围。R15 的 e4=[0,1200) 是 e3 已覆盖内容的子窗口，R16 交付，没有新增关系事实。

持续省略没有阻止新的错配：R7 开始将首书向韩江作品收缩；R8 将 e2 的 Man Asian 与 e3 的 Man Booker International 并列，R9 把前者当作题中奖项，并在同一响应先正确复述英文 2015，随后又称英文版出版于 2016。R9/10/12 查询 Man Asian 2016 获奖者；R11/13/14 反复查翻译数量。R16 又将 e2 误引作国际布克 2005 成立依据（该实际窗口没有此句），一度把首书和获奖书都设为《素食者》，最后才承认两书区分和首作者出生地仍未知。它在 FINAL 发 search，被 final_only 拒绝，16 次模型预算结束，空答案；没有合法 finish 或明确 abstain。

处理臂有四次原生 read、四个窗口，但只有两份 snapshot；自动 read 为零。原文支持韩江出生地及部分出版/获奖年份，没有支持另一作者成长地、首书身份和翻译数的完整合取。查询精确重复减少（46 条、42 条不同），仍存在语义重复和读后关系误用。本次不能把“少重复/多 read”解释为准确率改善。

## q774：一臂始终不读，一臂读到反证后又恢复错误说法

原题写 1.65 cm–1.70 cm，两臂 R1 均静默按 m 解释。婚姻次数 3 或 4 的解析正确，原题没有限定女性。基线 R4 将“首次出现的季开始年份”改述为整个 series 开始年份，并围绕 actress/telenovela 收窄搜索；这属于搜索方向收窄，不等于获得排除男性的证据。R13 虽重新意识到首次出演季条件，仍先用“这些剧 2000 年前开播”排除老剧，推理来回摇摆。

基线 R2 探 Grey's Anatomy，R4/5 转 Jane the Virgin / Rogelio，R6–9 在亲属、婚姻、Jane/Grey's 间重复；R10–12 再扫 Vampire Diaries、Fosters、Pretty Little Liars 等，R13–15 回到 Grey's。81 条查询字符串、71 条不同；R4 两个 queries 字段为字符串而非列表，均被拒绝，R5 修复。整槽 29 次 search 动作、71 次 backend，零 read、零 evidence，不能把大量导航描述成已经核验原文。R16 正常 abstain，承认没有可确认的完整匹配；这是未建立来源链，不是读过完整来源后排除所有候选。

处理臂 R1–4 查亲属及子女死亡，R5 William H Macy / Frank，R7 Grey's，R9 This Is Us / Yellowstone，R11 Chandra Wilson，R12 称身高 152 cm 因而转向 NCIS。上述判断主要来自导航或模型已有叙述，不能提升为原文核验。全槽 58 条查询字符串均不完全相同，但亲属/婚姻组合有大量语义重复。

R12 搜索出现 d140，R13 的模型已经写出 Sarah 与 Timothy 在剧中是兄妹，知道这与 unrelated 条件冲突，却继续将其叫作 strong lead。R13 原生 goal read d140，e1=[183805,186805) 于 R14 交付。原文明确：Sarah 由 Sean Murray 的现实继妹 Troian Bellisario 饰演，同时 Sarah 是 Timothy 的 younger sister。该窗口足以否定这对角色符合“不相关”的条件。它也包含 Tess Monroe 多次离婚、无子女，属于另一主体；不能移用到 Timothy。

R14 正确复述“they ARE related on screen”，随后还查 Sean/McGee 的身高、妻子和双胞胎；R15 称其余条件不合，尝试回查。R16 FINAL 的 abstain reason 却写“unrelated as siblings on the show”，与仍可见原文及 R14 正确理解冲突，并用 NCIS 2003 首播代替首次出演季核验。它最终没有提交姓名，因此语义状态为无提交；弃答理由本身含错误，不能说它正确验证了亲属条件。最主要的后期问题是读到反证后没有稳定排除候选，早期则是检索多而阅读迟。

## 成本（策略槽口径）

| 题/臂 | 终态 | HTTP | backend | search/read/finish 动作 | 输入/输出 token | cache-read token | 秒 |
|---|---|---:|---:|---|---|---:|---:|
| q775 baseline | submitted Akure | 14 | 24 | 20/1/1 | 228027/3727 | 104960 | 132.011 |
| q775 continuous | model_budget 空答 | 16 | 43 | 18/4/0 | 267375/2329 | 97920 | 147.858 |
| q774 baseline | abstained | 16 | 71 | 29/0/1 | 281064/4097 | 70784 | 222.430 |
| q774 continuous | abstained | 16 | 59 | 20/1/1 | 254319/1968 | 114432 | 138.211 |

动作数包括记录的被拒动作；backend 是实际 backend 尝试，不是查询字符串数。query cache hits 分别为 21、3、10、0；compaction_requests 分别为 5、8、12、7。cache-write 的默认零不作为供应方明确报告的零。难题共 62 对 HTTP，所有响应为正常归档响应，无本地合同配对或 HTTP 拒绝可解释这些终态。

结构核验表明持续省略机制真实执行，不能解释为没删到最新轮或 FINAL。行为证据仍显示：正确关系即使短暂出现，模型会重新构造错误的主体和时序；现有工具/证据仍可见也不保证下一轮使用正确。这是本次轨迹观察，不能在单次且 R1 已分歧的比较中估计机制总体因果效应。
