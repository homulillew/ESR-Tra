# 第九轮 q775 两臂来源审阅

范围为本轮已封存两个q775槽，运行代码a18054b；不使用gold或judge结论，未读活动q774，未调用模型或重跑检索。处理臂60个seal清单文件哈希、238事件链和11个实际请求验证通过，链头 `afd2858ea33588fc38053f616aa4e071457f374ab9ac1ced302515cba0c9e8c3`；检查见 Q775_CHECKS.json。

R4唯一read-only触发，依据R1–R3成功search且无新正文。实际SYSTEM为原SYSTEM加约定说明，追加文本哈希、完整SYSTEM哈希及wire哈希均匹配；tools精确等于原read schema，52个当前可读导航列于事件。R5 SYSTEM和工具恢复正常，没有第二次触发。

模型R4完全没有生成read，反而发出两个search，均被read_only_tool_only拒绝且未执行。没有自动替换、代选页或范围、补请求。显式说明确实送达，因此本槽不能把不遵从归因说明未进入wire；但单次轨迹也不能证明说明在所有场景无效。

全槽0read、0snapshot、0evidence。R2锁定International Booker，并提到Dublin成立2006；R3/R4称2017赢家是The Unseen，但没有读取原文验证这些年份或获奖身份。本审阅仅标记为未经来源支持，不调用外部查询判定真伪。R5–R9继续搜索奖项Wikipedia，R10明确replay缓存，也没有读取。候选书、奖项年份与作者城市链从未得到已交付正文支持。

R11 bounded FINAL合法finish(abstain=true)，理由正确说明只有导航、没有原文确认完整关系，终态abstained空答，不是非法FINAL或model_budget。计量：11模型请求、14search声明加1finish，其中R4两个search未执行、另一次重复阻断；19后端成功、6缓存query命中。输入178771、输出1734、cache83456，耗时82.686秒。

## 当前baseline配对

baseline80个seal清单文件哈希、340事件链、16个实际请求验证通过，链头 `cdedce079fcd7980a26fbdc39fbb837a76a52fe761c9e4a37cb9468b84e543be`。R1请求字节相同但响应立即分化：baseline一个top_k8 search，处理两个top_k10 search。R3 baseline已经选择Obioma并read，早于处理R4触发，不能将一臂有read另一臂无read归因说明。

baseline只有e1：R3 read d42[0,3000)，R4交付ADVISORS，真实支持Obioma出生Akure、两部书年份、普通Booker入围及30种语言。没有获奖书、另一作者出生地或Obioma成长地正文。R4已识别普通Booker创立年份不符合2000s，后面多轮仍停留Obioma与ManAsian搜索；没有新增read。

R16 FINAL合法提交Akure refs e1，但解释自身冲突：先说两部2019获奖书均于2019出版，随后声称前一年出版条件指向同一2019组合；又承认1969与2000s不符却继续选普通Booker。所称Obioma成长Akure及另一作者同城出生没有e1支持。因此出生地单一事实真实，完整题目关系仍未建立；不能将submitted当作correct。

baseline16请求、17search/1read/1finish、36后端、7缓存query、2重复阻断；输入286183、输出3454、cache95360，141.294秒。处理11请求合法弃答，baseline16请求证据不足地提交；双方模型/CPU无外部错误。无judge结论，不报告准确率，也不将预触发分歧当作机制因果效果。
