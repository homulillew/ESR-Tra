# 第六轮 q774 来源与轨迹审阅

本报告覆盖本轮已封存的 relation-review-once-v1 和随后封存的 baseline；没有读取任何活动槽文件、gold 或其他保留题，未调用模型或重跑 CPU 检索。本报告不把合法 submitted 当作 judge 正确。

处理臂 64 个 SEALED 清单文件哈希匹配，SQLite 352 个事件及对象链验证通过，链头 `b3a67c70e02b754d4146184a4aed19e364699e14420a21f5c834c11e75ab68cc`。12 次实际请求与归档相同，HTTP 全部 200；详见 discovery06-q774-checks.json。

## 候选、原文与题目条件

R1 保持“首次出现的季”与“剧集总季数”分别解释，婚姻次数正确写作 3 或 4；将原题 cm 静默改为 m，未保留单位不确定性。没有凭身高强制限定女性。R2 根据 R1 的 d1 导航立即选择 Richard Harmon；同页同时提到 Jessica，并没有原文证明应选兄弟中的哪一位。

R2 read d1 [0,3000)，R3 收到 e1：ScreenRant 的 CW 演员亲属文章，内容主要为导语、Amell、Padalecki/Cortese 等，尚未到 Harmon 段。R3 再读 [3000,6000)，R4 收到 e2，其中确实说明 Jessica 与 Richard 是现实兄妹，在 The 100 扮演无亲属关系的 Niylah 和 John Murphy；Jessica 第三季出现，Richard 在前两季为常驻配角、第三季升为主要角色。

因此 e2 真正支持亲属与角色关系；没有交付 Richard 身高、角色结婚 3–4 次、仅一名孩子存活的证据，也没有该剧首播日期或总共七季的文字。e2 同段的邻近演员生活信息不能移作 Richard 的事实。全槽原文只有该页两段，无其他 snapshot。

R4 起每轮检索 Murphy、Emori、身高和首播年，R5、R6 散文逐字相同。问题并非无原文，而是一个条件命中后便持续锚定 Richard，用多次查询寻找其余条件，始终没有另一次 read 验证它们。

## R7 关系审阅实际交付

唯一 relation_review 在 R7，依据 R4–R6 三个成功 search 且无新正文的完成轮。正常容量规则后仅保留 R5/R6 工具组；审阅输入中调用参数和回执与原组一致，旧 assistant 散文不在请求里。原文精确等于 e1/e2 和 visible_evidence，不扩大来源授权；wire、system、tools 哈希与事件一致。实际工具只允许 search/read/find。R8 恢复当时保留原组散文，原审阅记录也成为普通历史；恢复轮次见 checks。

R7 输出重新列条件，并承认还需核对其他线索，但没有逐项给出原文支持/冲突/未证状态或引用精确支持词。它仍以 Richard 为唯一候选，发出 height、Murphy marriages、剧集季数三个 search；没有读取新正文。R8 立即恢复 R5/R6 相同散文和旧五条查询，R9、R10 继续重复。R11 自称使用 different queries，实际仍是同一组参数。

## 最终提交与计量

R12 在 bounded workflow FINAL 合法 finish：Richard Harmon、refs e2。最终解释明确承认没有从交付证据独立核实身高、婚姻次数和孩子存活条件，却又声称这些条件指向同一人，以亲属线索作为足够识别依据。这是把一个真实关系当成完整候选识别依据；缺失条件未因审阅变为有证据支持。

12 次模型请求，18 search、2 read、1 finish，共 21 动作；其中 4 search 为 duplicate_query_blocked，无后端执行。37 query_execution、12 缓存命中；实际 25 CPU search 加 1 get_document，共 26 后端请求全部成功。148 文档登记、1 snapshot、2 evidence；输入 tokens 208751、输出 1795、cache read 75776，耗时 160.829 秒。没有 CPU 异常，未运行 judge。

本处理臂显示审阅协议正常进入一次实际请求，但未引发新来源读取或纠正单一条件锚定。

## 当前 baseline 与配对结论

baseline 的 80 个封存文件哈希、582 事件链和 16 个实际请求均通过验证；链头 `85350ebe5aa024f49c6e3e90a17f77c37de7fd2498437de2a69b4a6ed9fbb2f5`。16 次 HTTP 全为 200，无关系审阅事件。两臂 R1 请求 body 字节完全相同，但 R1 输出和查询已经不同：处理臂 R2 就发现 Harmon 页面，baseline R4 才明确选择该线索；这些差异远早于处理 R7 的审阅，不能归因机制。

baseline R1 正确保留季的首次出现与总季数，婚姻次数为 3 或 4；同样静默 cm→m。R2 开始改成 Show started 2001–2019，R3 照此选剧。后面同时考虑 Jessica 和 Richard，并没有把性别强制限定女性。R6 已明确说婚姻和孩子条件“不明显符合”两个角色，R7 开始把冲突可能归为题目不精确，却始终不离开该兄妹候选。

baseline R4 read d15 [0,3000)，R5 首次收到 e1；R5 继续 read [3000,9000)，R6 收到 e2。两臂读的是同一 ScreenRant snapshot；baseline e2 比处理臂多读 3000 字符，后半主要是 Cassidy、Routh/Ford、Morgan/White 等其他演员关系，不提供 Harmon 的婚姻次数、身高和孩子存活条件。baseline 也仅有这一个 snapshot、两条正文引用。R6 后没有新增 read，R8–R15 反复查询两人的身高与角色页面。

R16 FINAL 仍返回两个 search，均被 final_only 拒绝执行；没有 finish，随后 model_budget 空答。处理臂 R12 在重复恢复触发的 FINAL 中合法提交 Richard Harmon，但其理由仍承认关键条件未核实。两臂终态差异是“合法但证据不完整的提交”与“未合法结束”，不能在没有 judge 时换算正确率提升。

| 计量 | baseline | relation-review-once-v1 |
|---|---:|---:|
| 模型请求 | 16 | 12 |
| search 声明 | 28（2 次 FINAL 未执行） | 18（4 次重复阻断） |
| read / finish | 2 / 0 | 2 / 1 |
| 后端请求 | 49 | 26 |
| 缓存 query 命中 | 13 | 12 |
| snapshot / evidence | 1 / 2 | 1 / 2 |
| 输入 / 输出 tokens | 284570 / 3455 | 208751 / 1795 |
| cache read tokens | 99328 | 75776 |
| 耗时秒 | 241.029 | 160.829 |

baseline 后端请求全部成功，未发生 CPU 异常。两臂共同停留在“一条真实亲属关系足够辨认人物”的候选锚定，没有交付其余关键条件的支持。处理臂更早发现候选、读取较窄范围均发生在触发前；R7 审阅本身未带来新阅读或稳定的关系纠正。这一配对仅说明本次实际行为，不能外推机制总体收益。
