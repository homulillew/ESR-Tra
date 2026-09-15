# Discovery 09：q774 两臂封存审阅

本报告仅审阅本轮 q774 baseline 与 read-only-explicit-v1 两个已封存槽。未读取标准答案、judge 或活动中的控制题，也未重发请求。两臂均合法弃答，证据窗口和 read 调用均为零；当前材料支持分析行为与合同执行，不能据此报告正确率或机制的总体效果。

## 完整性与计量

逐文件重算 SEALED 所列 SHA-256：baseline 80 项、处理臂 76 项全部一致。只读 SQLite 验证分别通过 505 与 313 个事件，链尾为 `744e6311f8a4b16b480b0a1fb2838809bc05d6ad695db292407eeb3189ae8187` 与 `b9c95b1008f77053c8b5908bbaf96819b28ac90a4a763e479500b602a75ec6e4`。全部 31 个实际 request.body 解析后等于归档请求，HTTP 均为 200；无未知 usage、未配对请求或后端失败。逐项结果保存在同目录 Q774_CHECKS.json。

| 项目 | baseline | read-only-explicit-v1 |
|---|---:|---:|
| 模型请求 | 16 | 15 |
| backend 尝试 | 43 | 26 |
| search 动作记录 | 30 | 27 |
| read / 新原文交付轮次 | 0 / 0 | 0 / 0 |
| finish | 1 | 1 |
| 重复查询拦截 | 4 | 4 |
| read-only 非法工具拦截 | 0 | 2 |
| query 缓存命中 | 10 | 4 |
| input / output tokens | 261226 / 2938 | 222766 / 2417 |
| cache-read tokens | 85120 | 146176 |
| compaction 请求 | 10 | 1 |
| 耗时（秒） | 164.85 | 137.88 |

动作计数与后端请求不是同一单位：一个 search 可包含多个查询，缓存及拒绝也不会各自生成后端请求。处理臂共 28 条动作记录，26 条执行；R4 两条 search 在本地被拒绝。两臂最后分别在 R16、R15 的 FINAL 合法调用 finish(abstain=true)，均非 HTTP 故障或非法终态。

## 原题约束与 baseline 的首次偏离

实际 user 原文写的是 `height is over 1.65 cm but below than 1.70 cm`，存在明显单位异常；两臂 R1 均自行按 m 解释，未注明该假设。原题婚姻次数为大于 2、小于 5，即整数 3 或 4；baseline R1 却写成 “so 3 times”，同时将身高搜索离散为 1.66–1.69。原题限定首次出现的某一季在 2000 年后、2020 年前，不能自动替换为整部剧首播时间；baseline R2 已按 show “started 2001–2019”组织思考。原题没有限定性别，后续 actress 查询属于未经验证的候选缩窄。

baseline R1–R3 泛搜、Grey's Anatomy、Jane the Virgin、This Is Us；R4 起集中 Callie Torres / Sara Ramirez 和 Gloria / Sofía Vergara。R5 搜 Callie 的 George、Arizona、Penny 与女儿 Sofia，又搜 Sofía 的儿子 Manolo。R9–R15 转向 Gloria、Javier、Jay、Manny、Joe 及 Manolo cameo，并出现连续近似和精确重复。R16 认为 Gloria 有两个存活孩子、Manolo 的现实母子关系不能直接满足角色关系，最终弃答。

上述判断没有 read 原文窗口支持，不能把它们当已完成的事实核验。事件显示确有导航交付，不能称“检索没有返回任何来源”；但 EVIDENCE_TABLE 为空、没有 read 动作，全部候选关系都停留在模型推测和导航片段层面。本槽主要失败是搜索后一直未读，伴随条件缩窄和候选循环；没有证据表明它已经读到完整条件后仍提交错误答案。

## 处理臂的实际触发与响应

唯一 read_only_once 事件位于 R4，source_rounds=[1,2,3]。前三轮成功 search 回执没有新原文，R4 实际可见且已授权的 57 个文档等于前三个保留组的文档并集。普通历史消息（助手正文、原始工具参数、工具回执）逐项与这些归档组一致；没有从历史中删改正文或扩大来源权限。可见导航包含真实亲属同台的页面，如 d56 People 的 Hollywood families，以及 d57 Business Insider 的 on-screen siblings 页面；页面标题与片段只是可读线索，不能证明目标满足条件。

R4 实际 tools 仅为 R1 原生 read schema。SYSTEM 在原内容末尾追加一次英文指令，明确本轮只能 read、应自主选择已授权页面和段落范围。实际 request.body SHA-256 为 `d6d62fb22b18ab1c60d8b288d47411914064d30e5c0f342d45ac4ea031fbb8ad`，与事件 wire_sha256 一致；请求为 60870 字节。R5 SYSTEM 恢复原值，完整工具集合恢复。

尽管指令实际送达，R4 response 仍说 “Let me search more specifically”，生成两条 search，分别搜索 Days of Our Lives / Bold and Beautiful 与 Game of Thrones / Cersei；两条均获 read_only_tool_only，未调用后端。模型没有选择任何页面或范围，没有 read、没有新增原文。R5 恢复工具后继续 search。该现象是明确阶段指令加 schema 限制仍未诱导 native read，不能归因为提示未送达、导航不可见或来源权限不够。

处理臂 R1 正确保留婚姻 3–4 次，R2–R3 搜 Grey's、Jane、This Is Us；R4 后转入 Cersei 与肥皂剧，R6 加 Erica Kane / Susan Lucci，R7 Bold / Days；R8–R14 反复 Cersei、Robert、Joffrey、Myrcella、Tommen 与 Lena Headey，后几轮精确重复。它反复复述“仅一名子女存活”与“3–4 次婚姻”，却没有取得能将这些条件绑定到同一演员的原文。R15 的 FINAL 合法弃答，理由如实指出仅有 navigation snippets，没有 read evidence；这里可由事件独立确认，而非仅引用模型自述。

## 当前配对的解释边界

两臂 R1 request.body 逐字节相同，SHA-256 为 `fe019b884af954cf8777f10448535ff340cb76bb43e9ff9bfcb87c4cc5b7cdcd`；R1 response 已不同，包括婚姻次数解释、search 批次和查询内容。因此触发前的候选差异、之后不同的搜索路径和 token 差异不能全部归因于 R4 机制。本轮直接可观察结论是：处理机制按合同只触发一次并恢复，模型在该次依然生成 search，两个槽最终都没有取得原文并弃答。它检验了执行约束和模型服从行为，没有提供完整关系验证或答题改善证据。
