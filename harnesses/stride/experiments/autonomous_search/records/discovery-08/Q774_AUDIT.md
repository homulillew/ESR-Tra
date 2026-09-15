# 第八轮 q774 中断阶段审阅

只读本轮两个已封存q774槽，未读取gold、未重发、过滤或改写请求，未调用API或重跑CPU。阶段STOPPED，无全局POLICY_SEALED；49次policy、0judge，四个控制NOT_RUN，窗口累计427/1000、剩573。没有完整对照准确率可报告，也未进行发布。

处理臂80个seal清单文件、395事件链通过，链头 `9cfc12f3b11dc1db5940d58472f29827fb56fa95df2a5849c14714856b68307b`；baseline32文件、195事件链通过，链头 `72a32610367c2df5ddb2e232a538ede4cee6f1ba62bafe40fc7228a2622bde15`。全部20个实际请求与归档相同，原始响应文件纳入seal校验；详见checks。首请求字节相同，但R1输出/查询已不同，预触发分歧不能归因协议。

## 处理臂

R4唯一read-only，据R1–R3成功search且无新raw触发，24个可见授权导航d1–d24。实际工具精确等于原schema中的read，wire哈希匹配；R5恢复正常工具。模型R4仍生成search，read_only_tool_only拒绝且没有替换为read；没有自主页/范围选择。全槽0read/0snapshot/0evidence，不存在原文关系验证。

R4还把原题首次出现季改成整剧起始年，并把3–4次婚姻误写为“so 3 times”。原题cm在R1已静默改m。此后在肥皂剧、Jane the Virgin、Grey's Anatomy、This Is Us之间搜索，无正文读取。R16 FINAL仍search，final_only拒绝，无finish，最终model_budget空答。

处理16模型HTTP全部200，16search声明中14实际执行；42后端全部成功，0缓存query。输入235796、输出2254、cache135936，132.044秒。没有CPU错误。

## baseline HTTP400与新增请求内容

baseline R1–R3 HTTP200，R4 HTTP400。响应外层error是JSON字符串，解析其中error.type及code均为data_inspection_failed，message说明输入内容检查拒绝。不是401鉴权失败或429限流；也不是模型生成错误答案或正常弃答。终态http_error。归档metrics的outstanding_requests=[4]表示没有正常model_response事件，并非缺失HTTP response.body；原始400响应已捕获、封存。

R3→R4的system、原题及工具schema保持相同，baseline无read-only、审阅或记忆事件。新内容来自R3模型生成的检索分析、两组search参数及对应CPU检索导航回执；有上下文容量压缩和control状态更新。没有新增read原文、图片、人工消息或judge材料。R3讨论角色婚姻、孩子存活和多个剧名，查询扩展到telenovela/Game of Thrones/Bridgerton等；这些只是可观察的内容来源和类型，不足以定位哪个词触发服务方检查。本审阅不推测具体触发词，也未尝试删改以绕过检查。

原始请求与归档逐项相等，前三轮工具执行正常，未发现本地合同或请求配对错误可以解释该外部拒绝。baseline6个search动作、17后端均成功，0read；3次成功模型响应已知输入33810、输出683、cache17152，R4 usage未知，不补记为0。总耗时50.675秒，4次模型尝试仍按预算占额。

结论：处理臂的模型未遵守一次read-only工具面，最终未合法结束；baseline则被服务方内容检查提前终止。后者是外部拒绝，不能与处理臂完整任务失败直接做准确率胜负比较。原始拒绝记录完整，具体内容检查原因未知。
