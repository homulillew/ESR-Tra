# STRIDE 设计：从研究行动到明确提交

当前版本 `0.1.0a2`，协议 `stride-search-2`。三项恢复合同见 [RECOVERY_A2](RECOVERY_A2.md)，实验控制见 [EXPERIMENTS](EXPERIMENTS.md)，实际验证见 [VALIDATION](VALIDATION.md)。这是固定强模型、固定 BC+ 检索环境下的前向 harness，不训练参数，不宣称已提高真实任务准确率或降低工具轮数。

## 1. 从 bad case 得到的设计决策

旧 ESR 研究记录包含不同断点：无关 pending 阻止提交、finding 已记录但 answer 未外化、最后一轮只保存草稿、合法多调用受到限制、正确反馈没有改变参数。另一类失败始终没有找到必要材料，不能通过末尾审核解决。[1][2]

STRIDE 以真实行动和已交付观察为中心，而非要求每题维护完整 claim/evidence verified state。模型选择查询、解释材料并明确结束；程序负责对象身份、档案、原生回执、交付范围和成本。增加状态管理的收益仍需验证，不能由记录结构漂亮推导。

| 不再作为默认步骤 | 保留代价 |
|---|---|
| 逐页 pending 清账、focus 执行许可 | 不使用材料管理完成度代理答案完成度 |
| claim 图和 meaning_version | 不再具有机械依赖撤销能力，不声称旧计划自动失效 |
| 常驻 candidate/draft | 候选由 policy 在 finish 外化，不自动从便笺捞答案 |
| 默认 auditor、总结器、规划器 | 没有额外模型费用，也没有这些角色的判断能力 |
| 每轮必填 note/requirement | 便笺可能不写、写错或有偏，必须单独评测 |
| 自动补标点、猜号或归一化答案 | 保留真实失败，不改变被测策略 |

a2 增加的短期待修响应不是常驻草稿；容量恢复不是自动总结；外围错误隔离不放宽证据来源合同。旧 ESR 包不导入、不改写、不迁移。

## 2. 有限的研究依据

SLIM 启发在无用正文进入窗口之前选择性读取；已有 search/open 分离的系统不能照搬全部节省幅度。W&D 启发同轮执行多个已知行动以减少串行决定，本实现后端仍逐项执行，不宣称并行加速。HarnessOpt-Bench 启发固定目标模型、环境和评测并限制开发反馈。[3–5]

多代理审议、假设分支、语义进展分类、动态审核不是本版默认组件。需要明确失败和独立实验再引入，不因论文出现就增加一个 Agent。

## 3. 状态 S=(A,H,N,B,Z)

A 是文档导航、不可变快照、证据窗口及已交付集合；H 是原生交互组及当前工作视图；N 是可选小便笺；B 是模型请求、行动、后端、输出和时间预算；Z 是 RESEARCH、FINAL 或终态。另有只用于下一次修复的短期数据。不存在中心 supported 布尔值。

### 档案 A 与交付

搜索生成 dN。第一次 read/find 获取全文并冻结，后续本局使用同一快照；适合固定语料，不适合声称追踪实时网页。read 返回 eN，绑定文档、快照、start/end、全文长度、准确原文和 hash。同文档同快照同范围复用 eN，恢复不暗中扩展。

偏移是 Python Unicode code point，不是 UTF-8 字节或 grapheme。search/find/recall 摘录只是导航；后台已有全文不等于 policy 看过全文。只有实际呈现在请求并获得完整可解析响应确认的窗口才进入已交付集合。这是交付代理，不是理解证明。

一份响应内 search 后猜新 dN，或 read 后猜新 eN，仍然拒绝。顺序执行不能让模型获得尚未看到的信息。曾经交付过的 eN 即使退出当前窗口仍可显式引用或恢复。没有 this/claim 别名，不自动纠号。

### 便笺 N

notes put 接受 key/text/anchors，最多六条、每条 600 字符，anchors 可以为空。它服务于候选区别、排除方向和桥接线索，不要求猜测伪装成有证据结论。便笺不能作为 finish.refs。

相同文本与 anchors 为 noop，不增加 revision；顺序使用显式 order，不依赖 JSON 字典顺序。替换/删除由 policy 明确选择；历史便笺可 recall，标为 agent_note_not_evidence 并记录 active 状态。没有自动依赖撤销，旧文字也可能留在历史调用参数中。

### 工作视图 H

默认保留完整原生过程，不每轮摘要。rolling 在实际请求超容量时先退出旧完整回合，再减少导航索引和便笺。原始档案与过去请求不改写，不能拆坏调用/回执组或丢掉最新组后伪称已交付。

当前控制视图包括便笺、近期已读范围、剩余预算、局部错误及有界待修输出。导航最多显示近期十六份文档、每份四个窗口，不保证全档案覆盖。recall 目前词面搜索已交付窗口和便笺，不包含全部未读搜索卡片；摘录可能不是匹配词所在位置。find 区分大小写做字面查找，一次最多八处，返回续查位置。这些限制不自动升级为“文档没有所需事实”。

full 模式不退出旧历史、不自动摘要；开启 a2 交付预检时，过大的新结果可以明确撤下并拒绝交付。需要旧式完整结果溢出对照时，应同时登记 delivery_preflight=False。极窄窗口击败溢出的 full 臂，不代表宽窗口强模型普遍获益。

## 4. 行动与最短路径

六个工具为 search/read/find/recall/notes/finish。正常短路径是三个决定：search → read → finish。find 和 notes 都可省略。一个响应默认最多四项原生调用，每项 search 最多三个查询；严格单查询对照须同时限制这两个宽度。

普通局部读取错误不阻止只依赖旧信息的独立 sibling；关键错误阻止同批预生成 finish。a2 只对参数合法且 anchors 已交付的少数 notes 可用性/容量错误作非阻断处理。finish 必须最后，其他来源与格式校验不变。超批量整批拒绝，重复/缺失 native ID 不制造虚假配对，原响应留档。

传输、鉴权、身份变化、截断和完整性错误停止后缀，不自动重试或换路由。实际执行槽与声明调用分开统计；每次模型尝试始终计费。search 在执行整项未缓存查询前预检后端预算，缓存不产生新后端请求，但仍占发起它的 policy 决定。

## 5. a2 的执行—交付分层

实际提取结果先写 action_execution，不等于向 policy 承诺成功。整批结束后用同一 provider.prepare/counter 预检下一完整输入。放不下时可撤下完整的 search/read/find/recall payload，保存 result_withheld 对象，并生成明确 result_capacity 回执。

撤下按字节大小控制，不判断相关性，不摘要、不静默截断；后台快照/窗口/成本保留，未交付身份不可引用。所有调用仍有一一对应回执。policy 可在后续决定中按已知 dN 缩小范围或减少批次；同范围可复用快照。最小原题、assistant 参数与错误组仍放不下时明确失败。

短期修复视图只呈现可见文本/调用对象的有界预览、长度、hash 和错误，完整数据留档；不复制 provider thinking/signature，不作为来源或 system 指令，不自动生成答案。下一个完整响应后清除。超容量可省略预览并明确标记；没有额外免费修复请求。

三项恢复机制分别由 nonblocking_notes、repair_context、delivery_preflight 控制，细则与边界见 RECOVERY_A2。当前没有证据证明它们在自然任务上净省调用。

## 6. 预算与明确终答

reserve_finish=True 时，最后一次模型请求、只剩一个行动槽或输出预算只够一个最大响应，会进入 FINAL。工具 schema 和执行器都限制为 finish。模型基于已有证据提交准确字符串及 eN refs，或明确弃答；没有需要先保存的草稿、审核报告或全页清账。

正式答案保留首尾空白、标点和 Unicode，不自动 strip。answer_prefix/answer_suffix 是从显式实验配置输入的字面合同，默认空，不由程序从题号或 gold 猜测，两臂必须一致。违反合同只返回错误。最后一轮仍可能生成错格式、散文、非法来源或弃答，所以预留机会不等于保证正确提交。

预算内终答也可能剥夺最后一跳检索，须与关闭预留在同预算下比较。分别观察“旧错/新对”与“旧对/新错”，不能以提交率自证提升。

## 7. 存储、供应商和成本

SQLite 保存内容寻址对象、事件、文档/证据索引；全文按 hash 去重，窗口保存范围及 hash，请求拆为 envelope 与独立 message 引用。事件不反复复制全 agent state，但请求引用清单仍增长，校验需扫描，不声称最优线性复杂度。

只读检查同时验证事件链、对象 hash、引用存在性和索引与注册事件一致性。哈希链不是抗恶意全库重写的签名认证。输出独占新路径，不自动 resume 或重发未知完成的调用；旧协议可只读且不重标为新协议。

prepare→send→parse 在发送前保存实际 wire body。OpenAI-compatible 保留 tool_calls/reasoning_content；Anthropic 保留原始内容块与 ID，tool_result 紧随调用组、排在合并 user 文本前。[6][7] 不支持的内容类型、多 choice、截断不执行。原响应与已知 usage 先入账；HTTP 不跟随重定向，错误响应体和认证头不保存。

index_id/model_revision 是部署冻结标签，不证明真实权重固定；可检查 expected_response_model，标识不变也不等于模型不变。get_doc 未回显身份时记录 identity_echoed=False，只按请求绑定。

ByteCounter 使用 UTF-8 字节；HFCounter 只读本地 tokenizer、禁用 remote code，仍是服务模板一致性的估计，不支持声称准确计算 Anthropic。部署必须校准。缺失 output usage 按最大输出预留保守扣减；unknown、cache read/write 单列，不把未知当零。没有价目表不生成金额。

max_seconds 在调用边界检查，无法取消已发送请求；HTTP timeout 限制单次等待。episode 时间不包含依赖安装、服务启动或 tokenizer 预热。本版没有额外模型调用，不能将 fixture 决定数当成供应商使用量。

## 8. 可反驳的效果假设

H1：去掉 claim/draft/audit 手续，使必要材料到正式提交之间的决定减少。H2：定位和准确恢复减少重复读取，但短任务强制 find 会增成本。H3：小便笺帮助候选辨别与桥接保留，但也可能锚定错误。H4：预算内终答减少空终态，却可能损失最后一跳发现。a2 的外围隔离、修复数据与容量预检分别需要同条件续程和自然配对。

只提高中间合法率、只减少后端请求或只增加提交数，都不等于任务成功。当前没有语义 verifier、来源独立判定、提示注入免疫或真实 BC+ 提升证明。

## 来源

[1] ESR 作者结案记录，固定旧提交 c6dec9c：
https://github.com/homulillew/ESR-Tra/blob/c6dec9c3ac965d084ef4a28706458508a99ff59a/docs/research/strong_api_esr/FORMAL_DEVELOPMENT_CLOSEOUT_20260910.md

[2] 旧顺序工具与修复研究，同提交，非本版自然重放：
https://github.com/homulillew/ESR-Tra/blob/c6dec9c3ac965d084ef4a28706458508a99ff59a/docs/research/strong_api_esr/ORDERED_TOOLS_RESEARCH_20260910.md

[3] SLIM, Lost in the Maze：https://arxiv.org/html/2510.18939v1

[4] W&D, Scaling Parallel Tool Calling：https://arxiv.org/html/2602.07359v1

[5] HarnessOpt-Bench：https://arxiv.org/html/2608.06301v1

[6] OpenAI Chat Completions：https://platform.openai.com/docs/api-reference/chat/create

[7] Anthropic tool results：https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
