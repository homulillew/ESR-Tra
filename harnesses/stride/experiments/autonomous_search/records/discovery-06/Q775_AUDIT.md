# 第六轮 q775 baseline 封存审阅

本报告审阅 `discovery-06` 已封存的 q775 baseline 与 relation-review-once-v1 两槽，运行冻结身份由主流程指定为 `1f92698`。未读取 gold、当前 q774 或其他保留题，未调用模型或重跑检索。baseline submitted Ottawa 尚未 judge，处理臂空答 model_budget；本报告评价实际来源与论证，不给标准答案判分。

## 完整性及调用计量

SEALED 列出 80 个文件，逐文件 SHA-256 全部匹配；SQLite 310 个事件及内容对象验证通过，链头 `8b58a6bf0079fc5a4c1db59dd8e69ba22886dd44f6fb5d6d75bce1e344a9e6f8`。16 个 request.body 解析后与对应归档模型请求完全相同；原始请求/响应文件包含在封存校验内，检查结束时 seal 字节不变。详细摘要见同目录 discovery06-q775-checks.json。

16 次模型 HTTP 全部 200；21 个工具动作包括 search 13、read 5、find 2、finish 1。33 条 query_execution 中 9 条缓存命中，实际 CPU search 24 次；另外 4 次 get_document，共 28 次后端请求及 28 次成功响应。后端响应记录耗时合计约 46.272 秒，最长 12.548 秒；没有 backend_error。一次 search 在 R9 被 duplicate_query_blocked，未执行后端请求，不能计成 CPU 故障。

模型输入 tokens 256979、输出 2521、缓存读取 148992，无未知 usage；全槽约 120.332 秒。82 个文档登记、4 个 snapshot、5 个 evidence，4 个请求首次收到新正文。正常上下文压缩涉及 5 个请求；baseline 无关系审阅或历史投影事件。R16 为 FINAL，实际调用 finish，结果为 submitted，refs e3/e5 均为合法已交付引用，semantic_status=not_automatically_verified。

## 候选与首次关系错误

R1 正确拆解题目：Book A 的作者出生地是目标；Book B 的作者出生地应等于 Book A 作者成长地；两个书必须对应同一奖项，且获奖书应在前一年出版。R2 把 International Booker（2005）当作方向。

R3 根据检索命中选中 Obioma 与 An Orchestra of Minorities，转而搜索普通 Booker 的 2019 获奖者，却未建立两者是同一奖项。R3 read d45，R4 收到 e1，确实支持 Obioma 的两部书、年份、普通 Booker 入围、30 种语言和出生于 Akure。最早实质问题在 R3：候选切换到另一奖项身份后，2000s 创立条件未继续验证。

R5 自己陈述 The Testaments 和 Girl, Woman, Other 都在 2019 年出版，与其选定 Book A 的 2019 年相同，已经不满足获奖书“前一年出版”的条件，仍继续该候选链。R6 称“for the puzzle to work, Obioma must have grown up in one of these cities”，这是待证假设；后续没有交付支持 Obioma 成长于 Ottawa 或 Eltham 的原文。

## 五条交付正文的主体与范围

| 引用 | 实际读取及首次可见请求 | 支持与边界 |
|---|---|---|
| e1 | R3 read d45 [0,3000)，R4 可见 | ADVISORS：Obioma born in Akure；两部小说及年份、Booker 入围、30 种语言。未证明成长地关系。 |
| e2 | R5 read d69 [0,3000)，R6 可见 | Evaristo 自述：2019 Booker 获奖，born in Eltham、raised in Woolwich。主体是 Evaristo，不是 Obioma。 |
| e3 | R5 read d75 [0,3000)，R6 可见 | GALE：Margaret Eleanor Atwood born on 18 November 1939 in Ottawa, Ontario。该出生地属于 Atwood。 |
| e4 | R10 read d81 [0,3000)，R11 可见 | Wesleyan 新教师名单导语、前两位教师简介；该范围没有 Obioma。 |
| e5 | R13 read d81 [63000,64500)，R14 可见 | Wesleyan 原文写“Chigoze Obioma was born in Akure, Nigeria”，随后两部小说、Booker 入围及超过30种语言；没有 Ottawa 或 Obioma 成长城市。 |

R11 对 d81 find 完整短语 `Chigozie Obioma was born in Akure` 无匹配；R12 改找 `Obioma` 返回 63019、63569 两个位置。原文名字拼作 Chigoze，能够解释完整短语无匹配，无须推断检索器故障。R13 据位置实际读取 e5，因此本槽有真实的定位→读取进展，不是全程只搜索或没有来源。

## 重复与最终主体错位

R7–R16 的 assistant.content 逐字相同，均声称已有全部证据，随后又说需要确认 Obioma 成长地。R7–R9 查询重复，R9 触发重复阻断；R10–R13 改用 read/find/read，R14 又回到旧查询，R15 改词序，R16 finish。工具动作变化没有带来散文中的关系更新。

最终 finish 为 `Ottawa`，refs 为 e3/e5。Ottawa 的直接文字来源确实是 e3 的 Atwood 出生地；但模型贯穿最终一轮仍把 Book A 作者认定为 Obioma，而其所引 e5 直接写该作者出生于 Akure。最后一轮没有说明为什么改换目标作者，也没有交付两位作者之间的成长地等式。因而这是有真实地名出处但主体与问题目标错位的提交；合法 refs 不能补足缺失的实体关系。

本槽能确认：真实引用存在，甚至正确读到了支持其候选作者出生于另一城市的段落；重复散文及关系身份未更新使最终动作选了另一主体的出生地。没有 judge 前不报告准确率。

## 追加：当前处理臂完整配对

处理臂 80 个封存文件哈希及 361 个事件链通过，链头 `99c694602d67a94c57cbbb5b3821e7036f7f283b05761b7b08db99b152466297`；16 个实际请求与归档逐项相同。两臂首请求 body 字节相同，但 R1 响应和查询已经不同：baseline 两个 search 共五条查询，处理臂一个 search 三条。R3 虽都选择 Obioma，处理臂已经明确提出普通 Booker 1969 与 International Booker 2005 的冲突；baseline 没有同样保持这个区分。处理臂 R5 已主动读奖项页。因此这些差异早于 R9 机制触发，不能归因关系审阅。

### R9 实际关系审阅请求

仅一次 relation_review，观察 R6–R8 三轮均成功 search，无新正文交付。实际请求只含 system、原题 user、审阅数据 user 三条消息；完整 wire、system、tools、rule 哈希与事件一致。工具 schema 仅 search/read/find。保留组 R5–R8 的原始调用参数、工具回执逐项与归档组相等，组内旧 assistant 散文未进入审阅消息；旧候选可在原始检索参数中出现，这是保留执行记录的边界。

审阅数据中的正文集合严格等于请求 visible_evidence={e1,e2}，逐对象比对与 archive.evidence 完全相同，没有扩大到尚未交付的 e3。e1 是两臂共有的 ADVISORS 前 3000 字符；e2 是 Booker Prize Wikipedia [0,6000)，R5 read 后 R6 已交付，实际写 year:1969，并区分普通奖项和 International Booker。R10 正常请求恢复保留组 R7、R8 的原散文及 R9 新审阅散文；更早组按正常容量规则移出，不声称全部历史均恢复到 wire。该验证已补入 checks.json。

### 审阅内容与后续行为

R9 确实重新列出六项关系，引用 e1 的普通 Booker 入围文字，并指出它与 2000s 条件不合；但随后直接断言奖项“must be”International Booker。这没有穷尽其他奖项，也没有明确将完整候选关系标记为未证。该区分在 R3–R5 已出现，R9 不是首次纠错。

R9 发出 read d65 加三条新查询，R10 收到 e3《20 Best Book Awards Of 2025》[0,3000)。这次是真实新原文：它分别说明 Booker 自 1969 年颁发、International Booker 成立于 2005 年。审阅触发后确有 read 和交付进展，但不是一个新候选作者或完整关系的证明。

R10–R13 再次围绕 International Booker 列表反复 search，没有更多 read。R14 又把 Obioma 的普通 Booker 入围与 International Booker 获奖书连接；R15 虽正确引用 e3 的 2005 年，仍将两个奖项混为同一关系，并把 d79 整页命中的出版信息用作论证。R16 才明确怀疑 Alharthi 与 Akure 的联系，但又考虑 2015 Book A 与 2016 获奖书，不满足原题同年条件。此前审阅没有稳定阻止错误候选关系重新进入推理。

R16 实际已经是 FINAL，工具只允许 finish，模型却生成 search；回执 final_only、executed=false。无合法 finish，下一次调度因模型调用用尽产生 model_budget 空答。这与 baseline 的合法 submitted 终态不同；不能把空答解释为经过证据判断的主动弃答，也不能在未 judge 时把 baseline 提交视作正确。

| 计量 | baseline | relation-review-once-v1 |
|---|---:|---:|
| 模型请求 | 16 | 16 |
| search 声明 | 13 | 15（最后一次未执行） |
| read / find / finish | 5 / 2 / 1 | 3 / 0 / 0 |
| query_execution / 缓存命中 | 33 / 9 | 41 / 0 |
| 后端总调用 | 28 | 44（41 search + 3 get_document） |
| 已交付正文引用 | 5 | 3 |
| 输入 / 输出 tokens | 256979 / 2521 | 277160 / 3425 |
| cache read tokens | 148992 | 74752 |
| 总耗时秒 | 120.332 | 137.403 |

处理臂 44 次后端均有成功响应，无 CPU 错误。当前配对只支持有限结论：关系审阅按约定进入一次实际请求，原文边界和历史恢复正确，并伴随一次新原文读取；但奖项混同后来复发，最终未合法结束。触发前已分化和单次轨迹限制，使上述行为差异不能作为机制总体效果结论。
