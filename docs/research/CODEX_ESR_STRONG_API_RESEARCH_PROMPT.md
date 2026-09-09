# Codex 任务：强策略 API 上的 ESR 前向调试、少样本研究与公平验证

版本：1.0｜编写日期：2026-09-09

**这是给 Codex 中研究／编程模型的任务指令，不是给被测策略模型或 auditor 的系统提示词。** 不得把本文件、历史答案、bad-case 分析或参考文献笔记拼进被测模型上下文。

下面从“任务正文”开始交给 Codex 执行。文末资料索引只用于工程／研究核对，不是运行时证据。

---

# 任务正文

## 0. 角色、目标与执行原则

你是这个仓库的研究工程负责人，在用户授权的本地服务器中直接阅读代码、实现修复、运行测试、调用已经授权的远程强策略 API，并分析真实轨迹。不要只给建议或一份计划；在资源和权限允许的范围内完成实现、真实 rollout、分析与报告。

项目：`homulillew/ESR-Tra`。
起始分支：`refactor/esr-state-2.1`。
本提示编写时核对的快照：`a9ccd5180507f1dcf0e0a7b281c012975cc137a1`。这只是定位锚点，不要求回退到它；实际运行以本地检出的最新授权版本为准，记录确切 SHA 与 dirty diff。

注意我本地仓库有改动，按照我们本地仓库优先

目标是在**同一个强策略 API、同一 BC+ 语料与检索器、可比较的实际计算预算**下，使 ESR 相比高质量、无 ESR 的搜索 baseline：

1. 正式提交答案的准确率更高；
2. 实际工具调用与总推理成本更少；
3. 更快达到正确、可提交的终态。

这三项是优化与验收目标，不是预设结论。不得为了“完成任务”弱化 baseline、偷看答案、漏算审核成本、改变判分口径、挑选有利题目或删除失败。可以得到未达标、仅部分改进或证据不足的结论，但必须指出真实瓶颈、完成合理的最小迭代，而非无依据地放弃。

当前只做强 API 的前向研究，不做 SFT、RL、权重更新或全量 830 题评测。最终仍考虑向 4B 迁移，因此优先降低状态维护、协议修复和无效动作的负担；不通过增加大型在线模型组件或无限额外采样制造优势。

区分三个身份：
- **你／Codex**：调试者和离线研究者，可看开发集 bad case、查论文、写代码。
- **被测 policy/auditor**：经 `api/` 调用的远程模型，只看本 episode 原题、允许的工具观察和预先固定的运行提示。
- **离线 evaluator**：只在 rollout 完成后读取参考答案。其结果绝不能回流至正在运行的 episode。

先读取生效的 `AGENTS.md`／本地工程指令，遵守当前网络、命令和文件权限。不要尝试绕过审批或访问限制。每完成一个实质阶段或得到关键新证据，给用户一两句进度；不要重复讲计划，不承诺任务结束后后台继续跑。

## 1. 先勘察，再改动；保留真实版本和历史失败

优先阅读：

```text
api/README.md
api/lanz_client.py
api/demo_multiturn.py
src/esr_harness/{prompts,protocol,state,engine,context,runner,client,audit,views,ledger,cli}.py
docs/harness/{DESIGN,RUNBOOK,PROMPTS,VALIDATION,FORWARD_VALIDATION_PROMPT}.md
move/stage0_report_restored/{Stage0_REPORT.md,manifest.json,metrics.json}
move/stage0_report_restored/source_code/run_stage0_lanz.py
move/stage1_report_restored/{REPORT_STAGE1.md,manifest.json,metrics.json}
move/stage1_report_restored/source_code/run_stage1_batch.sh
move/*_report_restored/trajectories/ 中的相关案例
```

路径不存在时寻找实际对应文件，不伪造已读取内容。先列目录并定向阅读，不一次把整个仓库、历史 gold 和所有轨迹塞进上下文。

执行并保存：git 状态、当前分支、SHA、diff、Python/依赖版本、相关服务配置和可用资源。创建新的本地研究分支，例如 `research/strong-api-esr-<日期>`；不覆盖用户未提交修改，不 force push，不重写历史、不合并 main、不杀掉他人进程。默认本地提交代码；没有明确远程推送授权，不自行公开结果或推送原始数据。

`move/` 的报告是待核查的解释，不是真值。历史 TXT 常常截断参数、错误和 policy 输出；缺少原始 SQLite 时，将结论标成“已确认”“可复现机制”或“待原日志核实”。不要把每个 protocol_error 都归因于同一个字段。

特别检查以下已发现过的风险是否仍存在：
- Stage0 的 `fits=True`、每次固定记 400 token、未真实阻断预算。
- 适配器追加第二份工具说明，并禁止正式 schema 所需的 `revision_reason`。
- 记录的 messages 与适配器最终发送的 provider request 不一致。
- finding 已含候选内容，但 state 更新失败，最终 draft=null。
- `attempt_id` 等辅助账本字段错误，导致整个有效语义更新回滚。
- 重复 verify 其实是读缓存，却仍消耗 policy 生成与动作预算。
- shell 在 `ec=$?` 后又写 `echo "exit=$?"`，丢失原退出码。
- 把正确草稿、supported、HTTP 200 或 exit=0 当成任务成功。

这些问题须用当前代码／日志验证；不要将历史缺陷误称为当前已发生事实。技术修复和模型行为假设分开提交。

## 2. 正确接入 api/：协议适配，不另造一套 Agent

### 2.1 安全发现实际 endpoint、model 和 key

优先使用用户已配置的环境变量和指定配置文件；当前客户端支持 `ANTHROPIC_BASE_URL`、`ANTHROPIC_AUTH_TOKEN`，新统一配置可以提供清楚的别名，但不得靠猜测覆盖现有值。

只报告凭证是否存在、使用的变量名和脱敏来源。禁止打印 key、完整鉴权请求头、把 key 写进 git／报告／终端历史，或把凭证发给文献搜索和其他服务。不要扫描整块磁盘寻找密钥。缺失凭证只报告所需变量，不能绕过访问控制。组织网关的接入和客户端标识应遵从用户授权及正式配置，不因遇到403就自行伪装其他获准客户端。

确认实际协议是 Anthropic Messages、OpenAI Chat Completions 还是其他兼容格式，不根据文件名假定。使用配置、接口文档、响应中的 provider/model 标识进行核对；模型自称“我是谁”不构成版本证明。网关只给路由别名且无法固定底层版本时，记录不可验证项，按相邻时间块交错运行对照，不宣称完全可复现。

### 2.2 建立单一、薄的 provider adapter

尽量复用 `api/` 和既有 harness 入口。adapter 只负责：

```text
统一请求 → provider字段映射 → 已授权HTTP请求
→ 完整原始响应 → 统一响应／结构化动作 → 用量与错误记录
```

研究提示、工具定义、状态转移、审核规则仍由 `esr_harness` 的唯一契约产生。禁止在 Stage0 风格脚本中再手写一份 allowed fields 或另一套 policy prompt。baseline 与 ESR 必须使用同一 adapter 和同一解析条件。

系统消息应按该 provider 的正式字段传递；不能无说明地压成一条 user message。`temperature`、thinking/reasoning、max_tokens、tools/schema 等参数必须实际发送且受支持；不支持则明确记录，并在各臂统一处理。不要从其他 API 模式复制不兼容参数。

完整响应至少保留请求ID、返回模型标识、允许记录的content/thinking/tool_use块、usage、stop/finish_reason、耗时、重试。只记录服务实际返回且允许记录的信息，不索要或假造不可用的内部推理。不能丢掉 usage 后用常数补账。

优先采用可靠的原生工具调用或最终动作结构化输出。支持文本JSON时，只接受已声明且无歧义的包装，严格检查只有一个最终动作。不得从任意散文／思考中的第一个JSON猜动作；多个动作、截断或非法字段均保留原输出并分类处理。

### 2.3 真实预算与错误分类

共用一次 episode 的 policy＋audit＋模型辅助记忆／修复调用预算。记录输入、输出、缓存读写及reasoning用量；区分服务实测值和保守估计。若远端tokenizer不可得，可用官方计数接口或明确标记的保守容量估计；不能使用本地Qwen tokenizer冒充远端模型计数，也不能让fits恒True。

请求前预留；成功后按usage结算；超时或未知用量保守占用，不能当零。无法保证上下文／预算时停止扩展并报告限制，不假装满足严格预算。保留结束动作所需的生成空间。

网络错误、限流、鉴权失败、输出截断、JSON解析、schema错误、状态前置条件、引用错误、审核语义缺证分别记录。仅按固定有界规则重试可重试传输错误；每次重试计成本。不得整局重复直到成功再只保留最后一份。

### 2.4 先完成小型联通与契约验收

先用合成问题，验证一次真实policy动作、一次真实工具返回、一次局部更新及一次fresh-context审核；再用已暴露的BC+旧题检查真实链路。合成内容只能标为fixture，不得当BC+效果。

必须覆盖：
- policy与auditor无跨题会话残留，provider适配后的实际请求已保存；
- 无答案／pending时的合法恢复路径；
- 一份已解析提案只有一个字段错，下一轮能局部修复；
- 辅助note错误不会静默丢掉合法研究内容或伪造provenance；
- 同包审核缓存正常，相同诊断不被当成新证据；
- 已引用视图重读后，正文确实进入下一次策略请求；
- thinking导致输出截断时分类准确，不执行残缺动作；
- baseline可用动作与提示一致，真实保留历史观察。

若前几局仍出现系统性无效动作或重复submit循环，先停批跑修协议，不消耗几十局来再次确认相同错误。

## 3. 构建少样本集：难度分层，但不能对 ESR 挑题

本任务中的“少样本集”是小规模诊断评测集，**不是把BC+答案轨迹当few-shot例子注入被测模型**。协议示例只能用自造的小型任务，baseline与ESR获得同等接口教学投入。

BC+的难度按本次固定强模型、检索器和预算定义，不假定官方有easy/medium/hard标签，也不按题目长短或旧报告标题直接定难度。

### 3.1 三种用途分开

**A. 历史回归集。** 先用已经研究过的 q120、q594、q324、q234 等少量案例检验接口恢复、关系绑定和审核错误。这些只能做known-regression，不得写成新泛化成绩，也不能将旧答案／docid／成功query注入rollout。

**B. 开发集。** 目标9题，每档3题，用于真正查看bad case和修改方案。

**C. 一次性确认集。** 目标9题，每档3题；在任何ESR效果观察前锁定，最终版本冻结后才运行和查看详细轨迹。它只是小型held-out确认，不能冒充全量benchmark或强统计证明。

### 3.2 选择方法

1. 从本地合法BC+数据中读取ID和原问题；排除已知历史调参题及可检测近重复题。以固定种子／ID哈希选择24个新候选，不使用ESR结果、gold文档或答案内容排序。
2. 仅根据问题显式结构给出粗略prior难度：直接定位／短关系链为相对易；需要多个来源和明确桥接为中；多次实体消歧、范围核算、计数／否定和长证据链为难。输出简短理由和不确定性，不能把词数当难度。
3. 按prior分层先锁定9题确认集。不要运行它的筛选rollout，不读取其gold／历史解答来修改提示。锁定清单、规则和哈希；实在不足某档就如实保留不平衡，不能按ESR输赢补题。
4. 对其余最多15题，用同一个合格baseline做至多2次pilot。只将真实能力表现与任务有效调用成本用于开发集难度校准：两次答对且短链路倾向相对易；部分成功或较长链路倾向中；在有效执行和固定预算下持续困难倾向难。2次采样非常不稳定，标记为provisional。
5. 基础设施失败、协议卡死和明显数据问题不能当“难题”。先修共同问题，或保留为单独诊断类别。
6. 从pilot池冻结开发集9题，尽量覆盖三档及不同失败机制。选择不看ESR胜负。保存所有pilot样本与结果，不能只留下表现符合预期者。

确认集只有prior难度，正式运行后才可补充经验难度；不得为了“经验分层”提前查看其结果。若没有足够新题，明确这一限制，不把旧题伪装为新题。

### 3.3 数据与运行隔离

rollout输入副本只含ID和原问题。gold、参考答案别名、gold docids、相关性标签只在离线评价层读取。检索服务只返回正常语料，不允许按qid过滤为gold文档。

禁止Codex在运行中给policy定制答案提示、手写下一条查询或接管某一题的决策；需要这样定位问题时单独标为oracle-assisted诊断，不能混入自然rollout成绩。

确认集不向开发上下文输出问题内容、答案或逐题结果直到冻结。逻辑隔离不等于操作系统安全隔离：记录实际保护方式，能使用独立进程/工作目录时采用；不要声称做到了未实施的访问控制。

遵从数据许可和canary要求：不把解密后的题库、答案、原始评测轨迹或批量原文推到公开仓库。原始日志在服务器受限目录保存；公开提交仅含代码、配置模板、合成测试和允许公开的脱敏聚合结果。

## 4. 先建立强而公平的无 ESR baseline

baseline必须是同一强策略模型的正常多轮搜索Agent，不是故意弱化的单次猜测器。

必须做到：
- 同一实际provider/model版本、允许的thinking与采样配置、检索索引和服务、可用search/open/read能力；
- 保留普通的有效工具交互历史，不使用会丢掉旧正文和查询结果的简陋渲染当作“无state”；
- 无ESR特有claim/finding/focus表、gap tracker、语义审核门禁；
- 合理简短的研究提示、协议例子和终止指令；不得故意诱导它提前finish或禁止它做正常局部推理；
- 通用API、解析、预算、工具错误恢复、确定性检索缓存等修复同时应用两臂；
- 开发阶段给予相近的prompt校准机会，然后冻结baseline。不得ESR调十轮、baseline只跑一个明显失常默认配置。

不要在主实验中强制baseline每题至少搜一次；直接作答是合法策略，但将0-search/0-open单独统计。另做需要检索的诊断时，两臂施加同样约束并另标名称。

完整ESR可以使用紧凑工作卡，这是待测机制的一部分；但整个输入窗口和总计算约束必须可比。若baseline需要压缩，应采用合理且固定的通用方法，额外模型调用计成本，不能故意删除其关键材料。

最小实验臂：

```text
B：修好共同工程问题的强API ReAct-style baseline，无ESR。
E-off：ESR state/focus，无在线auditor；用于隔离state本身作用。
E-soft：ESR state/focus＋同一个强模型fresh-context审核，保留真实verdict。
```

hard只在少量机制题中独立诊断，不要同时扩大所有模式。先在开发集固定主候选是E-off还是E-soft；最后确认集只比较B与选定ESR。原版ESR可保留为历史控制，但不要花大批预算复现已定位的协议死循环。

如要采用更强检索器、不同工具、额外搜索或外部reader，给baseline同等能力并重建对照；否则将收益归于整个扩展系统，而不是单独归于ESR。

## 5. 优先修正确可用性，再优化研究策略
v0方案在C:\Users\wushuhong\Desktop\zip\ESR-Tra\bad_case分析与ESR-GRPO方案.md。
我们现在代码是v1方案在C:\Users\wushuhong\Desktop\zip\ESR-Tra\ESR-GRPO的Harness层实现与调试.md
我希望能迭代我们的ESR的Harness，同时保证我们的方案优雅简洁，同时提高性能。未来我们的方案要在4B或者32B级别的模型上rollout验证，所以我希望先在强策略模型先迭代harness，把我们的harness方案调整至合理。
### 5.1 设计不变量

保留轻量结构：

```text
target
answer: string | null
claims: [{claim_id, requirement, finding, observation_ids}]
focus: {claim_id, need} | null
```

原文不可变，finding可修订，answer是假设，audit带作用域；工作focus和审核缺口不同。模型写局部delta；版本、ID、缓存、尝试归属和预算由系统维护。

既有架构不是不可改，但重大变化必须有实际bad case、机制论证与消融支撑。不要先重写整个项目，也不要把实验脚本变成第二套agent。

### 5.2 第一轮只消除高频执行障碍

- 将辅助记账字段从核心研究提交路径中解耦；歧义必须可见，不能默默伪造关联。
- 给失败动作保留局部提案和字段级错误，优先执行有界协议修复而不是从头重新解题。修复不允许读取gold。
- 用共享前置条件产生动作可执行性和blocked原因。无answer／pending时不要持续鼓励必败submit；abstain仍保留，不能强迫成功。
- 当前审核已存在且已交付时，不将重复verify当作下一步研究；内容改变后再审核。缓存复用不是新判断。
- 空状态的partial audit应有明确用途，不应白白消耗一次审核来得出“没有答案”。
- 处理合法格式包装和reasoning输出，避免首个JSON抽取；不通过丢掉错误字段或自动补未知ID“救活”语义动作。

保持非法引用、陈旧审核和未知证据的严格边界。操作可执行性改善不是给错误答案放行。

### 5.3 第二轮再修 finding → gap → action

检查新证据是否真实改变了当前未知关系。一次focus可以指向search、未读hit、同文档新窗口、精确重读或局部解释，不是一律“继续搜”。

当出现独立桥接关系时渐进新建小claim；简单lookup可以只有c0，不奖励claim数量，不强制退役条件。保留先前桥接事实，不因换focus覆盖掉。

按实际目的保留最近查法：查了什么、读了什么、哪些关系仍未建立。完全相同请求缓存；近似query结合命中池、未读候选和观察区间判断，不用简单语义相似度硬封禁。没有新文档不等于没有推理进展，未搜到也不等于候选为假。

检查旧audit.need在状态更新后是否仍作为带旧scope的诊断可恢复，不能只剩一组没有含义的ID。

### 5.4 审核与停止优化独立研究

“引用存在”不等于“引用蕴含”，“supported”不等于“答案正确”。对误放或误拒保留完整原文审核包并离线复核。

不要把hard失败改成supported，不因答案与gold一致而倒填证据。可选择soft/off作为优化候选，也可以研究审核时机，但必须作为预先声明的新配置，统一应用整批题目，并计入所有成本。

不新增未校准confidence作为通过门槛；不自动从思考或未提交提案打捞答案；不要用“失败N次强制交卷”掩盖问题。

## 6. 自主检索最新研究，但每篇都必须服务于一个可检验问题

以实际执行日期为准，使用可用网页工具检索最近6–12个月与经典相关工作。优先原论文、作者代码、官方文档；记录首次发表日期、当前版本日期、读取范围和证据等级。

最初围绕当前已观察的3–5个瓶颈检索，而不是先写几十篇论文的综述。可用作检索种子的方向：

```text
IRCoT / Search-R1：检索与局部推理、搜索策略学习
MEM1 / AgentFold / source-indexed memory：可恢复上下文与记忆更新
ECHO / AREX / TRACE：先确认同名工作和准确版本，再看与ESR的最近邻关系
agent tool-use error recovery / constrained action generation
search stagnation / query reformulation / evidence-guided stopping
agent RL credit assignment / context mismatch / evaluation leakage
```

上述名称不是对其效果和最新性的背书；找不到可靠原文就标未核实，不编造论文标题、年份、数字或“理论保证”。同时查反证、负结果和失败条件。网络不可用时记录限制，继续代码与已有证据分析，不假装做了最新检索。

研究网页只供Codex离线查方法，不属于BC+被测环境。不要将BC+完整问题、gold或特定题答案拿到开放网页上查解后反馈policy。

每个候选改动写入 `research_notes.md`：

```text
论文/代码来源与日期
它处理的具体问题
与当前case的对应关系
能够借用的最小机制
额外复杂度与线上成本
一个可证伪的预测
需要的消融
为什么本轮采用或拒绝
```

每轮最多引入一个主要机制，不同时改检索器、模型、state、审核和采样。通用工程bug可以成组修，但与科学机制改动分开归因。不要未经验证引入过程reward、训练器、知识图谱、多agent控制器或大规模搜索树。

## 7. 有界自主迭代：每轮都有证据、回归与停止点

建立固定循环：

```text
实际bad case
→ 定位第一个有后果的断点
→ 一条根因假设
→ 离线最小复现／固定前缀诊断
→ 最小补丁与回归测试
→ 开发集paired rollout
→ 成本／正确率／行为分析
→ 保留、回滚或标记未证实
```

不能只拿最终失败文本分析。逐题至少区分：
1. 原文未召回；2.召回但未展示；3.展示但误读；4.候选已生成但更新未提交；
5.状态落盘后focus未推进；6.已有答案却陷入审核/终止循环；7.审核误放/误拒；
8.生成预算被thinking/重试耗尽；9.评测或数据歧义；10.基础设施错误。

证据应指向run_id、decision_id/action_id、输入输出和源码位置。根因不确定时给出两种解释和能区分它们的最小实验，不编造确定结论。

最多4轮主要机制迭代；一轮只有单题改善、其他题退化，不能立刻宣布保留。基于整套冻结开发题做配对比较，旧结果不覆盖。API/model路由或共同底座改变后，相关baseline必须重跑。

连续两轮在开发集没有可信改善，停止无约束加规则；交付最好且最简单的版本、失败证据、剩余瓶颈。不要靠扩大样本或调参次数一直搜到一次幸运胜利。

达到阶段条件后，冻结最终代码、baseline、提示、预算、judge、选定ESR模式和样本，再打开一次性确认集。确认集结果不可用于继续调参；若据此改代码，该集合降级为开发集，旧结果仅作旧版本评价，新版本需要新的确认数据。

## 8. 评测：四种“成功”不能混用

正式主指标：

```text
accuracy = 正式提交且独立判分正确的episode数 / 全部预定episode数
```

abstain、动作/生成预算耗尽、外部超时、未提交草稿，主指标均不算正确。基础设施失败保持在主分母，另报告完整性和相同健康条件的辅助分析，不能偷偷剔除。

`draft_correct`、`ever_proposed_correct`、`audit_supported`、`submitted`分别作为诊断。不要将正确提案自动变成正确提交。

### 8.1 独立judge

先核对BC+官方评测实现和本地数据协议，固定judge模型、提示、版本与规则。不能继续使用任意子串包含做正式判分。采用官方答案判定或经检查的别名、数值单位等规则；任何自定义口径都要单独命名。

LLM judge只看原问题、已经结束的提交答案、参考答案及预定评分规则，不看实验臂、内部finding或审核结论；使用独立无历史会话。最好使用独立可靠离线judge；若只能复用同一API，标记相关误差风险并复核争议，不能把一致当客观真理。

答案正确性和证据充分性分别评估。审核误拒需证明现有原文足够，不能仅因为候选等于gold就说verifier错了。

### 8.2 真实工具与成本

同时报告：
- 模型发出的全部动作及分类：search/open/read/update/verify/submit、非法动作和缓存动作；
- 实际后端检索、取全文、取chunk等请求，重试次数和缓存命中；
- policy、auditor、模型辅助memory/repair/selection的请求数；
- 输入／输出／reasoning／缓存token，实际计费用量与未知保守用量；
- 全部在线环节的端到端时间，以及policy、审核、检索、等待、重试分项；
- 离线judge和研发调用另列，不计作部署时在线成本，但占本任务总API预算。

不能通过合并工具、改名字、隐藏一个reader、漏算审核、把多次API封装成一次动作宣称调用更少。动作数、后端调用数、模型调用数必须分别给出。

相同并发、时间块交错运行B/ESR，避免先跑baseline全冷缓存、后跑ESR全热缓存；共享索引和provider缓存的预热状态需要记录。精确检索缓存能力两臂都可用，不能将共同缓存收益全归于ESR。

### 8.3 收敛与统计

真实latency从接收原问题到合法终态计时；提前失败的低延迟不能算更快解题。报告全部episode的用量/时间，并补充两臂都答对题目的配对成本；说明后者是条件分析，不代表总体。

“首次正确候选／首次可提交时间”只能离线从完整前缀评估，不能让gold evaluator参与在线停止。失败无正确完成时间，应视为删失／到预算上限，而不是零时间。

开发阶段每题每臂可先1次，候选确认做2次；冻结的9题确认集目标每题每臂3次。支持seed时记录，不支持时记录replicate和provider request ID，不能伪造确定性。温度0重复同请求不当独立样本。

配对统计以题目为cluster，保留同题多次采样依赖；做分层配对bootstrap或等价分析，明确9题的置信区间通常很宽。不得把27次运行当27道独立题目。

预先登记的实际优化目标可设为：准确率点估计至少提高5个百分点、实际工具总量下降15%、正确完成相关耗时下降10%。这些是初始研究目标，不是保证能达到的阈值；不能见结果后偷偷修改。准确率优先，不用大量提前弃权换取低成本。baseline接近满分时明确报告天花板，不放宽成“更高准确率”。

最终结论必须选择并解释：
- 三目标在本小型确认集的点估计均达标；区间不足时仅称初步信号；
- 只有准确率／成本的某项改进，属于trade-off；
- 接口可靠性改善但效果未达标；
- 数据／服务不足，不能判断。

仅当相应配对区间也支持改善，才作相应统计判断；即使小确认集通过，也不宣称全量BC+或4B泛化已成立。

## 9. 预算：少量启动、有界扩大，不无限刷API

优先读取用户已有更严格的预算／计费限制。没有额外设定时使用以下**建议默认上限**，先写入配置；不是说现有CLI已支持这些全局参数：

```yaml
max_real_episodes_total: 240
max_auxiliary_connectivity_requests: 12
max_major_iterations: 4
max_concurrency: 1
max_actions_per_episode: 64
max_completion_tokens_per_episode_including_audit: 24000
max_completion_tokens_all_remote_calls: 6000000
max_input_tokens_all_remote_calls: 30000000
max_wall_seconds_per_episode: 900
max_transport_attempts_per_request: 2
max_protocol_repair_attempts_per_failed_proposal: 1
```

全部pilot、失败、重跑、审核、模型修复和离线judge计入对应总上限。未知用量保守占用；美元成本有可靠价目表才估计，没价格不能虚构。上述预算不代表Codex自身订阅／研究用量已被计入，应另行说明。

逐阶段执行，不一开始提交240局。先联通和已知问题小验证，再pilot与开发集，再少量迭代，最后留出确认；预留最后9题×2臂×3次=54局及judge预算。任一上限到达即停止新请求，保存已完成工作，不自动扩大。

正常能力失败不重新采样到正确为止；只有明确基础设施故障才按预设规则重试，保留原尝试和全部费用。连续相同系统性错误应触发暂停批跑，改做离线修复。

参数如上下文窗口、单次输出上限、thinking温度必须根据真实API确认并统一冻结；不要盲目沿用本地Qwen的2048输出设置，也不要只给ESR更大预算。

## 10. 交付物、版本管理与可恢复执行

优先复用已有目录与脚本，以下是建议交付，不代表它们现在存在：

```text
docs/research/strong_api_esr/
  EXECUTION_PLAN.md          阶段、预算、冻结规则
  RESEARCH_NOTES.md          查到的论文、日期、采用/拒绝理由
  DECISIONS.md               每轮机制、预测、结果、保留/回滚
  FINAL_REPORT.md            B与ESR比较、case、成本、限制
  HANDOFF.md                已完成、阻塞、命令与恢复入口
configs/strong_api_forward.yaml
scripts/                    薄的probe、抽样、paired-run、eval、export入口
api/                        统一provider adapter及安全说明
tests/                      合成契约测试、局部恢复和模式一致性测试
runs/strong_api_esr/<run_id>/   本地受限、不推公开仓库
  manifest.json
  dataset_splits/            仅允许的输入与分割清单
  experiment_registry.jsonl
  <arm>/<qid>/<replicate>/
    ledger.sqlite
    provider_requests.jsonl  脱敏后保留实际请求语义
    provider_responses.jsonl 完整允许记录的响应
    trajectory.jsonl
    summary.json
    stdout.log / stderr.log / exit.json
  metrics.json
  paired_results.csv
  failure_taxonomy.json
```

每局版本记录包括代码SHA及dirtydiff、完整依赖/解析器、实际prompt与schema hash、model/网关配置、索引与语料版本、采样参数、判分协议、样本split和预算。不要用operator_declared冒充已核实的模型或索引hash；无法验证就显式标识并降低复现主张。

原始日志不只截前200字符。导出包括完整动作args、精确error.message/path、state前后、可见视图、audit.cached、usage和stop_reason。更正报告不得覆写原始文件。

每轮代码先测再提交，通用修复、ESR机制和评测脚本分开；不为了通过而删除断言。最终报告写出真实执行命令、测试结果、运行范围与未完成事项。原先的180项通过不能代替本机新测试。

建立可恢复的进度文件，但不承诺会话结束后自动继续。中断时标记未结算请求和unfinished episode；恢复不能重复收费而不记账，也不能把已有失败文件当完成跳过。

## 11. 现在开始执行

首先定位仓库、当前SHA、生效指令及 `api/` 实际鉴权配置。用最少请求确认强API和检索服务，然后修复共同测量与动作提交问题，再建立冻结的少样本对照。

不要先写长篇综述，不要先重构整个harness，不要先跑全量题库。若API凭证、授权、服务或数据确实无法从现有环境解决，报告准确缺失项并完成可进行的代码／测试工作；不捏造服务、结果或路径，不反复询问已能自行查明的参数。

最终交付应回答：

**修复后的ESR，是否真的在同一个强API上，比一个经过合理配置的无ESR baseline答得更准、用得更省、完成得更快？若没有，同时明确：哪一层已经改善，哪一层仍然失败，下一项最小可证伪的改动是什么。**

---

# 编写依据与外部资料入口（供执行者核对）

本文件是任务规范，预算与阈值是建议默认，不是论文结论，也不是已经执行的实验。

- 当前已核对仓库快照：<https://github.com/homulillew/ESR-Tra/tree/a9ccd5180507f1dcf0e0a7b281c012975cc137a1>。
- `api/lanz_client.py` 与 `api/README.md`：以当前实际文件和本机获准的API配置为准，不能把历史网关行为视为现时保证。
- BC+官方项目：<https://texttron.github.io/BrowseComp-Plus/>。
- BC+问题数据说明：<https://huggingface.co/datasets/Tevatron/browsecomp-plus/blob/main/README.md>。
- BC+语料说明：<https://huggingface.co/datasets/Tevatron/browsecomp-plus-corpus>。
- Anthropic stop reasons：<https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons>。适配兼容网关时仍需验证支持情况。
- OpenAI对Codex指令、输入与工具循环的官方说明：<https://openai.com/index/unrolling-the-codex-agent-loop/>。

官方BC+数据说明包含防止解密benchmark明文公开传播的要求；本任务明确只在授权本地环境处理真实题库与原始轨迹。
