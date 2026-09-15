# 第七轮 q775 记忆处理臂封存审阅

审阅本轮已封存 q775 的 memory 与 baseline 两槽，冻结运行身份 f919885；来源支持审阅不使用 gold 或 judge 结论，未调用模型、重跑检索或修改冻结文件。

64 个 SEALED 清单文件哈希匹配，SQLite 249 事件链通过，链头 `2c939bac3c92dbbf7d15978c9dd6819eed4f8da82148fefee80a51895b460cd9`。12 个实际 request.body 与归档逐项相同；正文文件纳入封存检查。详细检查见 Q775_CHECKS.json。

## 审阅资格、保存与实际呈现

R1–R3 成功 search 且无新正文，R4 触发唯一关系审阅。输入只含原题、控制和 R1–R3 检索调用/回执，raw_windows=[]。请求 wire 哈希匹配事件；检索参数和回执逐项与历史组一致，没有未交付正文进入审阅。

R4 实际 assistant.content 完整内容为：

> Let me search for the Man Asian Literary Prize Wikipedia page directly, and also search for books translated into over 25 languages that were contenders for this prize.

这段只有 168 字符、168 UTF-8 字节，低于 2000 字符限制；该轮 search 回执成功，符合保守保存条件。因此 capture created=true，未跳过。source_response_sha256 精确等于 R4 model_response.raw；助手消息、正文及空输入证据列表哈希均重算通过。input_evidence=[]，没有把该响应之后工具命中的导航倒挂为来源依据。

R5–R12 每次请求均呈现完整同一记录，共 8 次、容量省略 0 次；包括 R12 FINAL。逐次从实际 control 删除该记忆字段重建基础 wire，ByteCounter 精确匹配 base_capacity；实际 wire 匹配 proposed_capacity 和事件 wire_sha256。每次增加 891 个计量字节，八次合计 7128，不是 provider tokens。记录保留“可能错误或过时、不是证据、不授予引用权限”标签；所有输入及当前可见 refs 都为空。不存在摘要、截断、增补或授权扩大。

## 保存内容为何没有修复关系

R2 在没有 read 的情况下提出 Man Asian Literary Prize 2007 和 International Booker 2005，R3 选择前者并搜索名单。R4 虽是关系审阅请求，模型没有给出任何受支持/冲突/未证关系区分，也没有逐项核对作者成长地与另一作者出生地；实际保存的仅是再次搜索奖项页面的意向。这与第六轮曾出现的较完整关系区分内容不同，不能把旧审阅质量当作本次已经产生的能力。

R5 短暂查询 Jan Michalski Prize，R6 回到 Man Asian；R7–R11 反复同一方向及近似/相同查询。记忆持续可见，却未产生 read 或一个经来源核实的作者候选。原文约束没有形成可以保留的实质关系结论，因此本次失败首先是审阅输出本身缺少关系核对，而非记录没保存或容量没呈现。两臂触发前已分化，不能据此断言记忆导致重复。

全槽 0 read、0 snapshot、0 evidence，所有 delivery_ack 的 evidence 为空；有成功导航检索，不等于没有返回页面。模型持续把查找 Wikipedia 页当作下一动作，没有转成读取。两次 search 被 duplicate_query_blocked，不是 CPU 故障。

## FINAL 与计量

R12 为 bounded recovery FINAL，记忆仍可见。模型再次列出题目关系后调用 search，没有 finish；工具以 final_only、executed=false 拒绝。终态为 stalled_no_submission，detail 为 No legal finish in bounded recovery final decision；当时只用了 12 次模型请求，不能称为 16 次模型预算耗尽，也不是主动弃答。

12 个 search 声明中 11 个进入动作执行；包含两次重复阻断和一次 FINAL 未执行。实际后端 20 次，均成功；缓存 query 命中 7。输入 tokens 193876、输出 1348、cache read 69248，全槽约 84.200 秒。无 judge，不报告准确率。

本槽结论：保存资格、原文时序、来源哈希和八次实际呈现均正确；保存的内容只是搜索意向，未提供可持续保持的关系区分。缺少读取及 FINAL 非法动作仍未解决。

## 当前 baseline 配对

baseline 已封存：56 个清单文件哈希匹配，290 个事件链验证通过，链头 `522dfafd475dfc008d12f2ef512c5bc70b984dd5dd1e728659c2d8e31d46cd4e`；10 个实际请求与归档相同。两臂 R1 body 字节完全相同，但输出立刻不同：处理臂无散文、top_k=8；baseline 有详细题意拆解、不同查询且 top_k=10。R3 baseline 已选择 Obioma 并 read，处理臂仍只搜索 Man Asian。差异发生在处理 R4 审阅与 R5 记忆呈现之前，不能归因记忆。

baseline R3 读 ADVISORS，R4 收到 e1，支持 Obioma 出生于 Akure 及两部书普通 Booker 入围。随后读奖项页、Evaristo 页面及 Marlon James 两页，共 5 次 read。R6 明确识别普通 Booker 与 International Booker 不是同一奖项，以及两部 2019 获奖书不满足前一年条件；因此转向 The Fishermen / Marlon James 的 2015 获奖链。R7 又将奖项创立条件改说可能是赞助时代或题目不精确，未排除冲突候选。

R9 自己同时陈述 James 出生 Kingston、Obioma 成长 Akure，却继续宣称全部关系确认；这两座城市显然没有形成题目要求的同城关系。R10 直接提交 Akure, Nigeria，refs e1/e2/e4/e5，将题目条件当作关系成立的连接语，没有给出支持 Obioma 成长于 Kingston 的交付原文。Akure 在 e1 确有出生地支持，但完整实体识别链未成立。合法提交不等于本轮 judge 正确。

最终引用还有可直接检验的错归属：e2 仅为 Booker Wikipedia [0,3000)，没有最终声称的 Marlon James 2015 获奖引文；e4 实际是《King Yellowman》[0,3000)，作者署名含 photography by Marlon James，正文主体是 Winston Foster/Yellowman，不是 James 的出生传记；e5 是 BBC《11 of the best TV shows to watch this November》[0,3000)，尚在 The Day of the Jackal、Bad Sisters、Say Nothing 等节目段落，没有最终声称的 A Brief History of Seven Killings (2014) 引文。因此 5 次 read 并未使模型按实际段落验证其引用内容。

baseline 使用 10 次模型请求、9 search、5 read、1 finish，29 次后端请求；输入 tokens 165013、输出 2977、cache read 59520，耗时119.939秒。处理臂为12请求、12 search、0 read、0 finish、20后端，输入193876、输出1348、cache69248、84.200秒。两臂原文获取与候选路径在触发前已经分化，不能用这一个配对认定记忆造成更少读取。baseline 没有关系审阅或记忆事件；无 gold/judge 读取，不报告准确率。
