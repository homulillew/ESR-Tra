# Workflow v1：离线验收与六个真实槽位的轨迹分析

本轮完成 387 项离线测试、68 次真实策略请求和 3 次独立后处理 judge 请求。q775 的 full 臂提交了错误答案；q774 的 full 臂通过重复控制提前弃答；q771、q778 两个 full 控制槽位均在 4 次请求内正确提交。**本轮没有证据支持将 full 视为难题准确率改进，也不足以支持继续把它作为默认配置。**建议保留为显式可选的实验 profile。本轮保持在线启动时的代码冻结，没有根据结果修改 CLI 默认值或提示。

## 实验身份与执行边界

- 远程基底：`266772cebd296c4f9a7cb861c562f639ed3b0190`。
- 实际运行实现 SHA：`2d62ac9dbe3bd6f59eb62c3f9980fbfb4c7364a7`。包含必要修正、测试及冻结计划；本报告属于其后独立的报告提交。
- 分支：`research/stride-workflow-validation-20260915T075630Z`。
- 包版本：`0.1.0a3`；档案协议：`stride-search-3`；workflow：`gap-workflow-v1`；答案合同：`string-integer-v1`。
- 请求模型 `EB-GLM-5.2`，全部 71 次实际返回 `glm-5.2`，temperature=0。使用原只读 CPU SQLite FTS5 索引；索引、模型其余身份及逐字段 Config 见 [PLAN.json](PLAN.json)。
- 正式入口为 `cli.execute(run)`，显式指定答案合同和 workflow profile，调用原 `Harness.run`。每槽均为空 episode，只使用原题及本槽新工具结果。两组同题对照的非 workflow 配置、原题、检索和计量身份核验一致。
- 四个难题槽位的原生 `max_model_calls=16`，控制槽位为 4；每槽真实单调时钟上限 600 秒。上下文 96000、输出预留 4096 均为 UTF-8 字节，单请求输出上限 4096 为模型 token。没有把额外观察上限写入提示。
- 所有策略在 `2026-09-15T08:27:35.561511+00:00` 封存；标准答案读取始于 `08:27:35.571896+00:00`；其后才发生 judge 请求。judge 使用项目原实现及同一部署，属于独立后处理调用，不是独立模型家族。
- 没有探针、重试、重跑、在线调参或额外审核请求。历史失败轨迹和正式 6/12 均保持原样；本表是新的开发题运行结果。

## 离线验收及最小产品修正

远程基底的完整 STRIDE 测试实际通过 374 项。新增边界测试先暴露 3 个失败断言：CLI 丢失 token 计量模式下的输出预留检查，以及 cohort 在 `NOT_RUN` / 基础设施失败时的非零退出码。补回 `cli.py` 共 6 行后，完整测试通过 382 项；加入 5 项在线入口本地 fixture 检查后，最终完整测试 **387 passed in 129.08s**，无失败、错误或跳过。各次原始日志/XML 哈希及真实计数见 [OFFLINE_TESTS.json](OFFLINE_TESTS.json)，最小产品改动见 [PRODUCT_DIFF.patch](PRODUCT_DIFF.patch)。

已核验：六段工具说明；默认 `read(dN)`；goal/start 互斥及 eN 精确回放；goal 窗口为冻结文本的连续切片、无匹配不生成证据；未交付/容量隐藏结果不算已收到；复用结果可恢复完整卡片、片段变化不误折叠；gap 来源权限、无变化更新和有限历史；有限恢复及重复查询错误不阻断独立合法 finish；整数/字符串答案、CPU 检索、原生调用 ID、档案回放和导出回归。

新增入口 fixture 通过实际 CLI 配置/执行路径与本地 transport，验证 legacy/full 都能 search→read→finish，原始请求响应与 SQLite 导出对应；共享总账原记录保留，未知失败发送前占额；72/6 分角色上限及总上限生效；封存前不能进入 judge 或读取标准答案。这些测试是机械与集成证据，不是模型质量证据。工作流算法、SYSTEM、工具说明、schema 和检索策略在本轮均未调整。

## 实际结果

| 槽位，按运行顺序 | 策略请求 | 终态 | 完整提交文本 | refs | 本次 judge | 原文审阅 |
|---|---:|---|---|---|---|---|
| q775 legacy | 16 | model_budget | 空 | 无 | NOT_SUBMITTED，未调用 | 未读取原文 |
| q775 full | 16 | submitted | Akure, Nigeria | e1, e2 | false；标准答案 Boston | e1 支持错误候选本人的出生地；不支持题目关系链，e2 主体也不符 |
| q774 full | 12 | abstained | 空 | 无 | NOT_SUBMITTED，未调用 | 没有证据窗口，未识别满足条件的人物 |
| q774 legacy | 16 | model_budget | 空 | 无 | NOT_SUBMITTED，未调用 | 读到候选的亲属关系，其他条件未证实 |
| q771 full | 4 | submitted | Vakkorama | e1, e2, e3 | true | 原文支持品牌与年代及人物线索 |
| q778 full | 4 | submitted | 21 | e1 | true | 原文明示所问母亲生育时为 21 岁 |

三份 judge 输入均逐字符等于对应 `terminal.answer`，没有删除解释或从 assistant 散文另提答案。q775 full 的长篇解释在 assistant content 中，完整留在私有原响应；其实际提交文本只有表中的城市名。来源合法与语义正确单独判断：三个提交的 refs 均已交付，q775 仍然错误。

| 槽位 | 声明工具 / 已调度 / 成功 | 声明查询 / 进入查询执行 | 实际 FTS 搜索 / 文档后端 | 查询缓存命中 | 输入 / 输出 token | cache-read token | 端到端秒 |
|---|---|---|---|---:|---|---:|---:|
| q775 legacy | 32 / 30 / 30 | 96 / 90 | 30 / 0 | 60 | 254947 / 2845 | 94080 | 132.15 |
| q775 full | 20 / 20 / 20 | 29 / 29 | 28 / 3 | 1 | 290202 / 2933 | 141568 | 126.93 |
| q774 full | 12 / 12 / 10 | 33 / 27 | 21 / 0 | 6 | 194375 / 1585 | 88576 | 111.05 |
| q774 legacy | 16 / 15 / 15 | 39 / 36 | 33 / 1 | 3 | 186629 / 1117 | 127616 | 118.30 |
| q771 full | 5 / 5 / 5 | 3 / 3 | 3 / 2 | 0 | 27941 / 619 | 13568 | 20.19 |
| q778 full | 4 / 4 / 4 | 6 / 6 | 6 / 1 | 0 | 29852 / 425 | 13440 | 23.72 |

“已调度”对应档案 `executed=true`，包括进入执行器后被重复查询规则拒绝的动作；“成功”另计 `result.ok=true`。查询执行包含缓存命中，FTS 搜索列只计实际搜索后端调用；文档缓存复用不重复计后端。这里没有把 SQLite 内部元数据语句都称为一次搜索。

68 次策略合计输入 983946、输出 9524、cache-read 478848 token；3 次 judge 输入 568、输出 98、cache-read 0 token。输入/输出计量未知调用为 0。**所有 71 次的 cache-write 计量均未知**，机器汇总中的 0 仅表示没有可累加的已知值。策略端到端时间合计 532.34 秒，其中模型 HTTP 延迟合计 298.30 秒；judge HTTP 合计 4.35 秒。整轮墙钟时间为 577.19 秒，另包含封存、标准答案文件校验和后处理等开销。逐次计量、原始 body 哈希、身份与时间见 [HTTP_USAGE.json](HTTP_USAGE.json)，更细指标见 [RESULTS.json](RESULTS.json)。

共享总账从已用 572、剩余 428 变为已用 **643、剩余 357**；新记录 ID 为 573–643。实际使用 **71/80**，其中策略 **68/72**、judge **3/6**。全部 HTTP 200，无鉴权、截断、身份、未知完成或后端异常；没有把未使用额度补齐。

## 逐槽完整动作分析

### q775 legacy：导航未转化为原文阅读

R1–R5 围绕文学奖、出版年份及若干作者探索。R1 的返回已经包含 Booker 相关导航，随后也出现作者介绍及书目线索，但模型始终只发 search。它反复表示要重新审视时间线，没有执行 read。

R5 发出的两组三条查询成为固定模式，R6–R15 重复同样六条查询，形成 60 次查询缓存命中，没有新原文。整个槽位 32 个声明动作均为 search。R16 已进入原预算 FINAL，模型仍声明两个 search，均被 `final_only` 拒绝，最后 `model_budget`，没有程序代交或自动弃答。

本臂未启用 workflow，故 reuse/recovery/gap/goal-read 均不适用。这里的查询缓存只节省后端，并没有阻止模型调用消耗，也没有产生可引用证据。

### q775 full：开始阅读，但错误候选与关系冲突被保留到提交

R1 导航使模型锁定 Chigozie Obioma；R2 获取其出生地与书目线索，R3 实际读取 d38，生成 e1，同时继续检索。e1 的 `[0,3000)` 明确记载 Obioma 出生于 Akure，以及两部作品入围 Booker 和翻译数量。它支持这一候选的局部事实，不能证明该候选满足题目的全部关系。

R4–R8 围绕 Marlon James、Kingston 与 Obioma、Akure 改写查询。R5 读取 d86 得到 e2；该窗口 `[0,3000)` 是对音乐人 Yellowman 的文章，Marlon James 出现在摄影署名，窗口并无模型后来声称的那句 James 出生地原文。R9 读取 d72 开头 e3，为作家音乐偏好的文章；R10 find 定位姓名，R11 读取 `[21600,24600)` 得到 e4，确有 James 的获奖信息，但没有修好题目要求的同城关系。

R12–R14 继续变体查询，R15 又读取 Yellowman 文章下一段 e5 `[3000,6000)`，其孤儿院经历与所问作者城市关系无关。R16 原预算 FINAL 中提交 `Akure, Nigeria`，引用 e1/e2。原始 answer 为字符串，`string-integer-v1` 的 identity 规则逐字符保留。

关键错误可在原轨迹内定位：R16 的 assistant 解释明知所选奖项创立年代不合题意，却将题意视为误导；又把题目给定的同城关系套到未经证实的候选上，并把 e2 中没有的出生地句子写成引用。没有任何 gap 更新来保存或处理这些冲突。

本臂实际出现 1 个复用结果批次，未出现 workflow recover/final；最终 FINAL 来自原调用预算。查询措辞变化及新导航/原文使完全重复计数未形成连续停滞，不能据此认为获得了新的有效关系。发生了“搜索重复＋部分无关阅读”，没有 gap 循环。goal-read 未被使用。与 legacy 相比，同为 16 次请求，输入 token 增加、后端总调用从 30 到 31；合法但错误的提交不构成准确率或成本改善。

### q774 full：完全重复控制实际生效，结果仍是任务失败

R1–R7 改写亲属同剧、婚姻和子女线索，得到娱乐人物列表、剧情等导航。没有形成一个已被证实满足组合条件的候选，始终没有 read。可见导航里有可打开的页面，但它没有按 `read_action` 获取原文；本次不能声称其中已藏有确定的正确答案。

R7 固定一组三条查询；R8、R9 完全重复，6 个结果批次实际使用 compact reuse，对应 6 次查询缓存命中。R10 进入 recover，`consecutive_repeat_rounds=2`；R10、R11 仍请求同一组查询，均得到 `duplicate_query_blocked`，没有新后端调用。两次恢复决策用完，R12 的 workflow stage 为 final，模型显式 `finish(abstain=true)`。此处最终阶段由有限重复规则触发，早于 16 次原预算边界。

无原文、无 goal-read、无 gap，未发生“搜索改为无关 read/gap”的替代循环，也没有使用 replay 参数恢复完整卡片。机制成功终止了完全重复，但没有帮助模型找到答案。相较 legacy，少 4 次模型请求、少 13 次后端调用，输入/输出 token 反而更多，不能笼统称为更便宜或更准确。

### q774 legacy：读到了一个真实关系，随后困在未获证实的候选

R1 导航出现 Jessica/Richard Harmon 同剧但角色无亲属关系的线索；R2–R3 针对 Richard Harmon、John Murphy 和《The 100》探索。R4 read(d1) 读取文章开头，R5 find 姓名，R6 按实际位置读取 d1 `[4344,5844)`，形成 e2。该窗口确实支持现实中的兄妹在剧中扮演无亲属关系角色，并区分 Jessica/Niylah 与 Richard/John Murphy。

R7–R15 持续改写同一候选的身高、婚姻、子女及剧集年份查询。全槽 36 次查询执行、33 个不同查询字符串，只有 3 次缓存命中；措辞变化很频繁，但没有新的已读原文来满足其余条件。R16 原预算 FINAL 时仍 search，触发一次 `final_only`，最终 `model_budget`。

与 full 相比，本臂确实取得了与一个关键关系有关的原文；这不等于候选正确。full 较早弃答的结果不能被描述为在这道题上增加了有效阅读。由于 legacy 没有启用 gap/recovery，不从本臂推断那些功能的效果。

### q771 full：有效的短路径与按偏移继续阅读

R1 发出三条查询；R2 根据已收到的导航同时读取 d1、d8，得到 e1/e2；R3 读取 d8 从 3000 起的后续窗口 e3；R4 提交字符串 `Vakkorama`，引用三个已交付窗口。

e1 连接人物、家庭和帽店线索，e2 标识企业及父子身份，e3 `[3000,6000)` 在绝对偏移约 3526 起直接记载 1982 年面向年轻人的 Vakkorama。核心答案有原文支持，judge=true。这里没有声称题干每个背景细节都已单独核验。实际路径使用默认 read 与 start 偏移，没有 goal、reuse、recover 或 gap。新界面没有阻止本槽在既定 4 次上限内完成。

### q778 full：整数提交路径真实生效

R1 三条查询识别人物背景，R2 三条查询定位自称有亲属关系的女子，R3 读取 d16 `[0,3000)` 得到 e1，R4 原生 `finish` 参数为 `{"answer":21,"refs":["e1"]}`。

e1 在绝对偏移约 2157 起指明 Riette/Mariette 的母亲生育时为 21 岁，支持所问主体与年龄；正文显示 2021 年发表日期。这里只使用文章中的指称，不将其亲属关系主张升级为已证实事实。

原始 JSON 输入类型为整数，原始值 21；结构化元数据为 `rule=string-integer-v1, operation=decimal, input_type=integer, input_value=21`；终态为文本 `"21"`，refs 保持 e1。原始 HTTP 和规范化终态均可追溯。judge=true。这验证整数答案不再被字符串专用接口阻塞，不是模型学会了加引号。goal/reuse/recovery/gap 均未自然触发。

## 哪些机制实际得到验证

| 机制 | 本次真实运行 |
|---|---|
| 六段工具说明、workflow 可见视图、显式 profile | 全部 full 槽位使用；没有单独消融来归因各段说明 |
| 默认 read 与偏移续读 | q775 full、q771 full、q778 full 实际使用；q774 legacy 也使用了旧入口 |
| goal-read、无匹配行为 | **NOT_EXERCISED**；仅离线机械验收 |
| compact reuse | q774 full 6 批、q775 full 1 批 |
| replay=true 恢复完整卡片 | **NOT_EXERCISED**；离线验收通过 |
| bounded recover→final | q774 full R10/R11→R12，最后弃答；没有正确恢复案例 |
| update_gap 及拒绝/冲突历史 | 所有 full 槽位 **NOT_EXERCISED**，不能声称模型利用了记忆或冲突记录 |
| 整数到文本表示 | q778 full 自然触发并正确提交 |

full 的可达性和审计边界通过本地与在线检查，但 bundle 中多个变化共同作用，单次温度 0 运行也不保证确定性。这两道已暴露难题不能代表总体准确率；更少请求、主动弃答和形式合法均不能替代正确答案。唯一建议的下一问题是：**如何依据已交付原文排除与明确题目约束冲突的候选。**本轮未启动该研究。

## 记录与发布

完整私有目录为工作树内 `runs/workflow-v1-live-20260915/`。六个槽位分别保存 `episode.sqlite`、`http/NNN/{request.body,response.body,attempt-start.json,metadata.json}`、`trajectory.jsonl`、`events-timed.jsonl`、`all-objects.json`、`FULL_INTERACTION.md`、逐轮/查询/工具/证据表及 `SEALED.json`。`all-objects.json` 与 SQLite 包含全部被引用对象及 workflow/gap 视图；UTC 是新运行的记录时间，初始 header 没有伪造追加时刻。

根目录保存冻结实现身份、策略封存、标准答案读取时刻、judge 原输入及输出、原共享总账本轮记录和最终余额。原始问题、页面全文、完整 HTTP/SQLite、部署地址及总账均保留私有；公开发布经过筛选的动作参数摘要、完整提交文本、计量、哈希与来源定位。重复题干的弃答理由在公开摘要中用哈希代替，私有原文完整保留。

- [ROUND_ACTIONS.json](ROUND_ACTIONS.json)：每轮真实原生 tool ID、原始 arguments 哈希、动作摘要、反馈、可见证据和阶段。
- [RESULTS.json](RESULTS.json)：六槽详细指标、原始 answer 类型/表示规则、terminal、refs 与独立 judge。
- [POST_RUN_CHECKS.json](POST_RUN_CHECKS.json)：68 个请求与档案对应、71 个响应身份、总账关联、同题配置一致及封存顺序。
- [PRIVATE_RECORD_HASHES.json](PRIVATE_RECORD_HASHES.json)：私有轨迹、原始输入/输出及判分记录的精确哈希。
- [PLAN.json](PLAN.json)、[OFFLINE_TESTS.json](OFFLINE_TESTS.json)：冻结配置、源码定位及本轮实际验收。

六个策略档案封存后未变；首次在线发送后实现和计划未变。本轮到此停止。
