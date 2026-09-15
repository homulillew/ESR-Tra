# 第八轮 q775 来源与轨迹审阅

本报告覆盖本轮q775两个封存槽，评价实际来源和行为，不使用gold或judge结论。

运行代码2d3d195；审阅未调用模型或重跑CPU。baseline的68个seal清单文件哈希通过，214事件链通过，链头 `979c793e12bc8b5bdb8274011aef85d38b48e7782937616f99ab1bbbfa02afe6`；13个实际请求与归档相同。检查见 Q775_CHECKS.json。

baseline R2把Man Asian Literary Prize当作奖项候选，后续R3–R12均只搜索这个奖项的Wikipedia、获奖名单与入围书。R7出现Bi Feiyu/Three Sisters查询，但没有交付相关书、作者或日期正文，不能当作已验证实体。R6–R12散文高度重复，R8–R12查询参数完全相同；两次重复阻断没有带来read。

全槽12 search、0 read、1 finish，0 snapshot和原文证据。检索实际返回导航和片段，模型没有选择读取；最终解释“without being able to read”只能理解为没有实际读到，不能当作工具权限或后端无法读取的证据。没有read尝试，自然也没有read失败。最早瓶颈是R3已决定需要奖项名单，却始终用页面名称查询代替读取，后续未构成可供检验的完整作者关系链。

R13 bounded FINAL合法finish(abstain=true)。模型正确区分导航片段与可引用e窗口，逐条列出书籍身份、年份、翻译数量、获奖书和两位作者城市关系仍未核实，最终空答abstained。它没有凭某个真实地名强行提交；不足在前面的证据获取行为。

计量：13模型请求，16后端请求，无后端错误；11个缓存query命中，2次duplicate_query_blocked。输入tokens204499、输出1351、cache read121472，耗时73.091秒。baseline无read-only触发、关系审阅或记忆机制。当前无judge判断，不报告正确率。

## 当前处理臂与配对

处理80文件seal、300事件链、16实际wire验证通过；链头 `7714890bd3b054edd5cb2aace804d8f8baebb49ffe70139c3b4579da2cb7b262`。两臂R1请求字节相同，但R1输出和查询立即不同。处理R3已read Obioma，R4收到e1出生地/Booker入围/30种语言；baseline全程不read。预触发读取差异不能归因R7限制。

唯一read-only在R7，观察R4–R6成功search且无新raw。实际仅原read schema，wire/schema/导航列表哈希匹配事件；原system/题目和已保留原生历史消息、参数、回执逐项保持不变。44个可读导航d1–d44均在历史或control中呈现并在原授权内，没有从私有档案补来源。R8恢复正常工具。

关键结果：R7模型没有自主选择任何read页或范围，而是继续输出search；引擎返回read_only_tool_only，未执行、不替换、不重试，单次机会已消费。因此不能报告“限制成功促使阅读”。R8后继续搜索奖项。

R11回到Obioma/Evaristo候选，R13提出城市不符，但比较的是Evaristo出生地与Obioma出生地，而题目要求后者成长地；这种比较不能单独构成反证。普通Booker创立年份不合题意则仍是未解决条件。R15正常工具阶段自主发出read d12、goal='Man Asian Literary Prize'，既有guided read选择[24407,27249)，R16收到e2。这是有用的新原文，明确说明International Booker 2005、Man Asian2007和前一年出版规则；但距R7已八轮，不能当作限制轮成功执行的read，也尚未建立具体书作者链。

R16 FINAL仍search，final_only未执行，无finish，最终model_budget空答。处理16请求、16search声明（read-only和FINAL各拒绝1）、2read、35后端，8缓存query命中；输入260261、输出3249、cache147712、耗时101.449秒。无后端错误。baseline13请求合法弃答，处理16请求未合法结束；当前配对没有完整关系答案，不能将多读两次等同成功，也不能把预触发差异归因机制。
