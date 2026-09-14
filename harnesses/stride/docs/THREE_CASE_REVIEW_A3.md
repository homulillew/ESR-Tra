# STRIDE a3 三题自然运行与事后判分

本次对 q26、q72、q661 各完成一次自然运行，并在三题全部结束后分别执行一次语义 judge。三个最终提交均与冻结基准答案逐字相同，judge 均判正确。这个 3/3 只描述三道已分析题，不构成整体准确率或性能提升证明。轨迹审阅同时发现：模型可能提交正确名称，却没有用正式引用证明全部限定条件。

本文件整理计数、执行合同和机制分析。用户在事后明确授权公开完整材料，见[三题完整轨迹入口](../artifacts/20260914-three-case-a3/README.md)与[给 GPT 的审阅任务](../artifacts/20260914-three-case-a3/GPT_REVIEW.md)。机器可读统计见 [three_case_metrics_a3.json](three_case_metrics_a3.json)，采集与判分工具见 [TRACE_CAPTURE_A3.md](TRACE_CAPTURE_A3.md)。

## 执行设置

被测 release 为 `5d7752be94a9d40aa757383d8899504bc0f81e81`，包版本 `0.1.0a3`，协议 `stride-search-3`。当前提交增加的是采集、分析、判分代码和文档；下列结果不声称是当前新提交上的自然重跑。

三个 episode 使用同一个 CPU SQLite FTS5 生产索引：100195 份文档，`porter unicode61`，词项 OR，SQLite BM25 排序，关闭 compiled_query_cache。索引只读，核心代码按文件哈希与 release 比对。模型请求名为 EB-GLM-5.2，返回标识为 glm-5.2，temperature=0。没有搜索代理、额外总结模型、在线 auditor、探针、自动重试或补跑。

每题完整 Config 相同：最多 32 次模型请求、100 个动作、60 次后端调用；每批最多 4 个工具动作，每个 search 最多 3 条 query；单次输出上限 4096 tokens、累计输出上限 24000 tokens；ByteCounter 上下文 96000 字节，预留响应 4096 字节；read 默认 3000 字符，recent_groups=4，max_notes=6，max_document_chars=2000000，max_seconds=900。

notes_enabled、reserve_finish、require_sources、nonblocking_notes、repair_context、delivery_preflight、disclose_retriever、recall_navigation、centered_recall 均为 true；context_mode=rolling、evidence_shelf_size=3；answer_prefix/suffix 为空。机器可读文件保存全部字段，避免将字节预算与供应商 token 混淆。

q26 是已知开发题。q72／q661 按此前冻结顺序分别选择第一道 easy／hard，依据是题面结构启发式，并非本模型的经验难度标签。两题原属 confirmation，完整轨迹分析后已标记为开发暴露题，不能继续用于“未接触确认集”的结论。没有按结果替换题目。

## 结果与成本

| 指标 | q26 | q72（预标简单） | q661（预标困难） |
|---|---:|---:|---:|
| 自然 episode | 1 | 1 | 1 |
| policy / HTTP attempts | 12 / 12 | 14 / 14 | 4 / 4 |
| 原生工具／实际动作 | 20 / 20 | 25 / 25 | 5 / 5 |
| search 动作 | 13 | 15 | 1 |
| 内含 query／CPU search SQL | 39 / 39 | 44 / 44 | 3 / 3 |
| get_document | 2 | 6 | 2 |
| read / find / recall / notes | 4 / 2 / 0 / 0 | 9 / 0 / 0 / 0 | 3 / 0 / 0 / 0 |
| 全部后端调用 | 41 | 50 | 5 |
| 压缩请求 | 2 | 2 | 0 |
| shelf 恢复请求 | 0 | 1 | 0 |
| 恢复消息直接增加的请求字节 | 0 | 935 | 0 |
| 编译等价重复 query | 1 | 0 | 0 |
| 相同历史结果集合 | 4 | 6 | 0 |
| input tokens | 160790 | 189203 | 18934 |
| output tokens | 1657 | 1833 | 718 |
| cache read tokens，已含在 input 中 | 102912 | 127744 | 10112 |
| cache write tokens | 未报告 | 未报告 | 未报告 |
| 请求正文累计字节 | 678680 | 747596 | 80033 |
| HTTP 累计秒 | 53.644900 | 56.533646 | 17.856859 |
| CPU 累计秒 | 42.045500 | 47.703787 | 5.717481 |
| episode elapsed 秒 | 97.498317 | 105.885783 | 24.011447 |
| 终态 | submitted | submitted | submitted |
| 事后答案 judge | correct | correct | correct |

三个 episode 共 30 次模型调用；事后 judge 另有 3 次，不能混入 policy 成本。judge 总计输入 636 tokens、输出 87 tokens、请求正文 3030 字节、HTTP 8.311854 秒。没有价格与结算依据，不估算金额。供应商未提供的缓存写入记为 null；Archive 的可选字段空和 0 保留作原始汇总，不能把它解释为真实零用量。

## 工具执行与证据连续性

所有真实请求均返回 HTTP 200，返回模型身份一致，没有未知完成状态。请求正文与 Archive.load_request 逐项 JSON 等价，发布版 canonical 序列化也与实际 urllib Request.data 按字节一致。这是正文对应，不是 TCP 报文证明。原生工具 ID、顺序、名称和参数均与执行记录一致；所有非终止回执进入下一次实际模型请求。最终 finish 回执仅存本地，不为回传额外调用模型。

q26 经 find 从正确文档中定位目标段落，再分两个窗口读取。核心窗口产生在最后一次压缩之后，保持可见到提交；没有 shelf 恢复，不能把相对旧 ESR 的调用数下降归因于 shelf。正式名称有原文，部分辅助关系缺少正式引用。

q72 的早期活动原文 e1 在第 9 轮压缩后退出输入，经第 11 轮重读才重新可见。第 13 轮压缩时，shelf 恢复 e4，增加正文 935 字节；模型同轮仍重读 e4，不能说这次恢复省掉了读取。e3 在提交时不再可见，但保留过去交付的合法引用资格；模型把它解释成另一类地点来源。程序绑定和交付没有换错，误解发生在模型解释中。没有对照证明压缩导致该误解。

q661 没有压缩，提交时三份正式窗口全部可见。模型用年份算术代替实际周年事件证据，并以展览记录推断工具持续使用。这说明过度确认也会出现在原文没有丢失的情形。该题首次查询迅速命中人物，加上模型提前结束验证，形成了低调用成本；不能仅凭“困难题更快提交”宣称困难问题已解决。

三题都未使用 notes 或 recall。q26 的 find 自然触发且原文偏移核验正确；q72 的重复 read 复用已缓存全文，没有新的 get_document。没有强制模型调用机制以制造成功案例。

## 答案正确与引用充分性

事后判分使用仓库 `OpenAICompatibleJudge` 的语义等价合同，每题只输入原题、基准答案、原始 finish.answer。未输入模型提交前的解释、refs 或人工审计。三个候选都是基准答案的逐字匹配，judge 也一致确认正确。

judge 是同一配置模型家族的独立事后请求，不声称具有不同模型部署的交叉验证。返回对象中 confidence=1.0 来自项目代码的默认值，并非 judge 生成的置信度。每条判断绑定已完成 Archive head；新标签独立追加，原轨迹中未判分的 formal_correct=null 保持封存时状态。

这个判分不覆盖解释事实性和引用充分性。q26 的部分辅助条件、q72 的距离与历史状态、q661 的持续使用和周年活动仍缺少正式证据。证据缺口和正确名称可以同时存在。当前 finish 检查结构与交付资格，并不自动检查所有关系是否由原文支持。

## 验证与边界

自然运行前基础 228 项测试、smoke、replay、diagnose 和 CPU 合成验收均通过；采集、预算及 judge 另外用 localhost、合成索引、合成账本验证。发布时再运行基础与全部新增测试，结果保存于发布验证记录。

此前失败的本地验收、原始实验和事后分析分别留档。核心 harness 未因结果改动，三题没有补跑。经用户授权发布的完整包包含原题、答案、对应 gold、实际取得的文档及完整 HTTP 正文；不包含内部 API 地址、密钥、真实预算数据库或生产索引。部署元数据替换、公开事件链重算及原始 head 映射在发布包中逐项说明。

仅建议一个后续机制实验：固定已记录动作，离线比较 shelf_size=3/0，以 q72 的恢复轮为观察点、未压缩的 q661 为负对照，比较窗口可见集合、原始组裁剪和请求字节。模型调用预算为 0；本次未执行。固定动作回放不能代替自然行为或准确率对照。
