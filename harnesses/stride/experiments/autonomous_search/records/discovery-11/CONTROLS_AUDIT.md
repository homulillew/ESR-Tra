# Discovery 11 控制题独立来源审阅

审阅范围仅四个已封存控制槽 q771/q778 × baseline/continuous-prose-omission-v1。未读取 judge、gold 或其他题。下列结论依据实际请求、工具回执及交付窗口，未采用判分结果。

## 结论

q771 候选提交了 Vakkorama，但实际交付原文**没有直接支持父子共同创立该品牌**；父子身份、品牌名分别出现，不能证明共同创立关系。q778 两臂提交的年龄 21 均有直接原文支持，主语是所述女子的母亲；文章中的父女血缘关系仍是当事人声称，不能提升为已证实事实。

## 原文与动作

| 槽 | 实际原文与首次交付 | 终态与支持范围 |
|---|---|---|
| q771 baseline | R2 read d1，e1 [0,3000)，R3/R4交付 | 未提交，model_budget。原文支持人物出生、父母职业及开帽店背景，尚未读到父子共同创品牌段。 |
| q771 candidate | R2 read d1/d8，e1/e2均[0,3000)，R3/R4交付 | R4 finish 字符串 Vakkorama，引用合法；核心共同创立关系未获原文支持。 |
| q778 baseline | R3 read d19，e1 [0,3000)，R4交付 | R4 finish 原始 JSON 整数21，核心年龄关系有支持，其他背景链未完全建立。 |
| q778 candidate | R3 read d22，e1 [0,3000)，R4交付 | 同上，读取的是与基线相同快照、相同窗口。 |

q771 基线 R1 搜索，R2 读取人物文章开头，R3 find 返回位置导航：Vakkorama 在 [5774,5783)，摘录包含“1982 created a new brand together with his son Cem”。该回执明确为 positions_not_evidence，不生成 e 引用。R4 尝试读取后部，被 FINAL 阶段 final_only 拒绝，executed=false；预算耗尽而无 finish。不能把导航摘录当成已经交付该段原文，也不能把这次拒绝归因为参数校验：归档显示阶段检查先拒绝。

q771 候选 R1 搜索后，R2 读人物文章及 Vakko 百科开头。e1 尚未覆盖上述父子共同创立段；e2 提及创始人、儿子及旗下 Vakkorama 品牌，未把二人与共同创立该品牌绑定。R3 find d8 返回 [3532,3541) 等位置，导航摘录提到1982年青年商店开业，但不提父子共同创立，也没有新增原文。R4 assistant 将共同创立关系表述为百科已确认，随后 finish；这是模型生成断言，引用的两个窗口不能支持这一核心断言。

q778 两臂前两轮搜索，第三轮读取同篇文章；候选第三轮另有一个搜索批次。已交付正文明确把 Riette Nel、其母 Riana van Deventer、1975年出生记录和母亲生育时21岁连接起来。因此答案所问的母亲年龄有直接支持。有关 Errol 为其父的部分是转述临终告知和当事人主张；其余用于定位公众人物的公司、家世、子女等条件并未全部由这个窗口覆盖。

q778 两个 finish 的原始 answer 都是 JSON integer 21；终端 answer 为字符串 "21"，answer_representation 记录 input_type=integer、input_value=21、operation=decimal、rule=string-integer-v1。这是明确的表示转换，没有改变数值。q771 候选为 string→identity。

## 结构与投影

指定 audit_continuous_stage.audit_continuous_slot 四槽均通过：128个封存文件、16次正常模型请求/响应、5个槽内唯一原文窗口均核对。SQLite 事件链、归档请求与 HTTP body、窗口快照切片与哈希、交付 acknowledgment 一致。结构合法不等于语义正确。

候选每次请求均有投影审计；R1无历史可删，R2/R3/R4分别对保留的1/2/3个完整组省略 assistant.content，R4包括 FINAL。逐组重算投影与实际 wire 完全一致；原工具调用ID、名称、参数、回执和原文未被投影修改，原始归档组仍保留。基线没有投影事件。本次实际请求是原生 OpenAI 兼容消息，未把离线 Anthropic转换检查写成线上观察。

每题两臂首请求 bytes 完全相同（哈希见 checks），首轮动作输出已经不同，发生在首次有效散文省略之前。后续确实实施了投影，但这个单次比较不能把路径或提交差异全部归因于投影。

## 成本

| 槽 | 模型请求 | 后端尝试 | 输入/输出token | 缓存读取token | elapsed秒 |
|---|---:|---:|---:|---:|---:|
| q771 baseline | 4 | 4 | 25151 / 252 | 13568 | 29.859 |
| q771 candidate | 4 | 5 | 27346 / 367 | 14464 | 17.303 |
| q778 baseline | 4 | 7 | 30081 / 342 | 14208 | 20.085 |
| q778 candidate | 4 | 10 | 32051 / 435 | 13440 | 25.585 |

后端尝试数不等于工具调用数；批量查询各自计量，FINAL 拒绝的 read 不执行后端读取。elapsed 是归档整槽时间，不能当作 CPU 时间；此报告未取得独立进程 CPU 计时，不能据此断言 CPU 节省。两题候选实际输入 token 均高于基线，轨迹不同，不能用总量差估计同轨迹省略幅度。

详细机械证据见 CONTROLS_CHECKS.json。来源支持结论不使用任何外部判分。
