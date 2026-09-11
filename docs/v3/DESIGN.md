# ESR v3 低编号负担完整方案与实现规范

## 1. 定位与当前入口

ESR v3 是可修订的证据工作区：**原文可恢复，局部理解可修订，修订实际影响下一次上下文，模型可以明确直接提交。** 编号只是定位手段，不应成为模型的主要任务。

本分支增加独立包 `src/esr_harness_v3`。旧 `esr_harness`、`esr_grpo` 和旧账本保持原语义。运行新版本用 `python -m esr_harness_v3` 或 `esr-harness-v3`；旧入口 `esr-harness` 未被改指向新包。

协议身份是 `esr-v3-reference-light-1`，新句柄从 d1/o1/c1 开始，不将旧 c0 或旧 schema 静默迁移。来源规格是会话中的《ESR_v3_低编号负担完整方案.md》；本页同时给出实际实现决策与未验证边界。

## 2. 三个职责层

| 职责 | 当前实现 | 不做的事情 |
|---|---|---|
| Archive | 原文快照、窗口、搜索命中、事件、交付、历史 claim、审核与成本 | 不将全部历史全文放进每轮 prompt |
| State | 草稿、少量 requirement/finding、前提、focus、note、局部适用性 | 不把 finding 自动判真，不要求全档案清账 |
| Context | 稳定研究段、近期原生交互、内容邻接、局部反馈、恢复入口 | 不额外调用总结器或规划器 |

`store.py` 是 SQLite 追加式哈希链；`state.py` 是局部事务和引用；`context.py` 是请求构造；`engine.py` 管六工具与真实执行；`audit.py` 管独立核对；`adapters.py` 提供外部服务接入；`training.py` 只导出训练所需真实信息，不实现 GRPO 优化器。

## 3. 模型侧状态

原题始终完整保存，不允许通过改 focus 或删除 claim 改写任务义务。初始可以没有 claim，focus 可空。

模型只需维护当前问题、值得以后使用的 finding、必要草稿和少量研究备注。记录应写清实体、时间和关系，避免跨轮只用“她”“这个候选”。没有证据的计划和猜测放在 note，不伪装成有依据 finding。

程序维护 ID、版本、来源路径、哈希和事件序号。内部可观察量多，不表示模型必须填写这些字段。

## 4. add / revise 与统一 refs

新建不填编号：

```json
{"add":[{"requirement":"赛事与年份","finding":"X 在 2014 年赢得赛事 E。","refs":["this"]}],"focus":"查同一赛事两年前的冠军"}
```

回执会返回新 c 编号及对应内容。修改已有记录才选择其句柄：

```json
{"revise":[{"claim":"c7","finding":"此前判断有误，应为 2015 年。","refs":["o18"]}]}
```

`refs` 只表达明确依据：o12 / o12:p2 为直接原文，c7 为具体版本的前提，this 为当前请求声明的原文。d4 只是导航，不能进入证据 refs。

后台分别保留 `direct_refs`、`premises`、展开的 `sources` 与原始选择 trace。选择 c7 不会被自动纠成 o7；祖先原文可以由已声明前提展开，不要求再抄全部 o ID。记录结构有来源不代表语义已支持。

修改 finding 必须同时给 refs；省略字段表示不改。只改 requirement 而不给新 finding，会将旧解释留在历史，当前 finding 清空。draft 按 answer 与 refs 成对保存，draft=null 只清空草稿，不擦掉审核历史。空 finding+空 refs 可以表达尚未解决的工作项。

## 5. this 的严格含义

请求中会明确显示 `this -> o12`，且对应完整观察窗口就在本次输入中。模型仍要明确写 refs=["this"]；省略 refs 不作推断。

只有一次完整阅读结果批次中恰好有一个成功的原文窗口、没有阅读错误时，才建立候选。多原文批次不选择最后一页，也不因裁剪只剩一页就获得资格。新的失败读取清除旧候选。

映射在 `Decision` 请求中冻结。同一响应先打开新页、再 refs=["this"]，仍引用生成这个决定时声明的原文，不读取运行时 latest_result。没有新阅读时，纯 update/审核/格式修复可以保留同一候选，但只有原文仍实际呈现在新请求里才提供 this。

`enable_this=False` 单独关闭快捷引用。this 与显式 o12 解析相同后可共享答案包身份，但原始两项选择都记录，不计成两份独立证据。

不能用编辑距离纠号、自然语言标题猜对象、c/o 同号互换或丢弃非法 refs 来提高表面合法率。

## 6. 真实观察与历史恢复

文档快照以原始返回内容保存；窗口有原始 start/end、全文长度、内容、段落范围与生成动作。旧窗口不会被后续网页变化覆盖。续读 cursor 绑定保存的文档快照，不重新解释成新网页。

`open_page` 只能打开先前收到的搜索句柄。新窗口尚未进入策略请求时不允许引用。同一决策里 open 返回的 o ID 不能被后面预先生成的调用猜测使用。

当前 HTTP 检索器兼容旧 main 的 `/retrieve` 与 `/get_doc`。正文选窗使用有界、确定性的本地字面查询匹配；它不是复现 BM25 chunk ranking。比较实验必须对各臂使用同一选窗规则，不能把选窗变化算作状态收益。`MemoryRetriever` 只用于离线 fixture。

`read_evidence` 可按已发布 c/o 句柄恢复，按 query 搜本 episode 历史，或用已发布 cursor 翻页。历史检索包括已交付观察、旧搜索命中和明确 note；目前是确定性词面查找，不保证语义召回。列表 excerpt 是导航，不形成新的原文曝光。恢复原文返回同一不可变窗口。

原文存在、返回完成、请求构造、响应到达与语义使用分开。准备请求不立刻宣称交付；收到该决策响应后才将实际输入中的完整窗口加入 exposed。请求失败不会凭空获得新来源权限。阅读材料无需先写 finding，不要求 focus 或 pending 清账。

## 7. 局部版本与依赖

每条实质变更保存不可变版本。解释版本与记录版本分开：仅增加直接来源、而陈述和前提不变时，可保持解释资格；后补来源不会回填成旧依赖当时已经使用的证据。

requirement、finding 或前提发生变化时，解释版本增加。移除来源采用保守的新解释版本，防止来源断裂不传播。A→B→A 不回退版本；退休 ID 不复用。

前提边存所选记录版本。上游被替换后，沿已声明关系判断下游适用性。独立事实和所有原文保留；导航链不参与删除传播。缺少 refs 中的 claim 前提，不被当成已经证明无依赖。

一个 update 可原子修改多个已有 claim；同事务依赖被修改的已有节点时，绑定提案版本，其余绑定决策快照。先验证整个提案、来源和无环性，再提交。新 claim 之间不能在同一事务猜测编号互引。一次响应最多一个 update；它成功后，后续操作可引用其对已有 claim 的明确修改，trace 标注 `own_committed_update`。

## 8. 上下文构造

模型看到原题、当前问题、草稿、相关记录、原文与局部反馈，句柄与内容相邻。程序按明确依赖组织相邻条目，不生成新的“因此”或支持事实。

研究段内保持 header 稳定，追加完整的 user 控制范围、assistant 原生调用及全部 tool 回执。控制消息明确只有当前这一条定义 this，历史映射不可当当前快捷词。改变 state 的回执在历史中给出最新记录。

容量不足时，建立新 header，保留有界的近期完整回合；逐组减少旧回合与工作记录，不能拆坏原生调用/结果组。最新完整结果组不能为了缩小输入而被伪装成交付成功。放不下最小合法请求，明确报 context_capacity。

默认使用最近的有来源当前记录及其显式前提；前提没展开时给出 missing/unexpanded 句柄，不把结论显示成自足证明。当前 this 的原文要么仍在保留回合中，要么在新 header 明确重新呈现。记录未选入当前上下文不等于失效。

解释被明确替换或退休时启动修订边界：旧研究段不原样续接，保留有效状态、明确备注、原文恢复入口以及本次修订回执。当前实现对所有已有解释的实质修订采用保守重建，而不仅仅对被选中的工作项重建；需要在后续消融中测量过度重建和桥接丢失。只增加独立事实、focus/note 改变或仅补来源不会触发这种边界。

## 9. 六工具契约

| 工具 | 主要参数 | 关键规则 |
|---|---|---|
| search | query, top_k | 无 claim/focus 前置；同索引同参数缓存仍计 policy 请求 |
| open_page | ref, 可选 query；或 cursor | 新旧入口互斥，来源句柄必须先交付 |
| read_evidence | ref / query / cursor 三选一 | 原文、目录、备注保持不同身份 |
| update_state | add, revise, retire, focus, note, draft | 省略不改；新建无 ID；局部事务全有或全无 |
| verify_answer | answer+refs；或空对象使用已有草稿 | 空状态本地拒绝，不远程空审 |
| submit_answer | answer+可选 refs；或 decision=abstain+reason | 明确外化，不自动从 finding 捞答案 |

Schema 是固定 canonical contract 的深拷贝；不共享可变 enum 字典。网络使用原生 OpenAI-compatible tool_calls，实际 message 与回执都保留。参数不合法给本地具体错误，不取自由文本里的第一个 JSON，不修补证据。

重复/缺少原生调用 ID 时不发出伪造配对，不执行该响应；返回可恢复协议说明。正常多调用逐项有回执。超过组上限时整组未执行、逐项说明；不静默截取前几项。前项失败则停止后缀，已成功的前项保留。

verify 是反馈边界，之后的预生成操作不执行；submit 是终止边界。所有失败/未执行也保留账目。句柄存在但内容选错，仍然是需要模型实验评价的语义错绑。

## 10. 审核与统一答案包

独立 auditor 只得到原题、明确答案、待审记录、原文及相关已知异议，不得到全部策略自信推理。同模型另开上下文不代表错误独立。

`checks` 使用键映射，不按数组位置猜对象。完整答案必须有 target、coverage；明确选用的 claim 也须完整返回。所有行含 verdict/explanation/refs。取消旧 status/need 空值配对；局部支持/反对要有该 claim 允许的真实原文路径，不能从另一 claim 的引用集合借用。

原文只按实际包范围展开。报告不合法或服务失败不产生候选错误结论；协议修复最多两次，保留原包、原输出和全部成本。不是循环到出现 supported。

答案包包含准确字符、共同任务契约、直接原文、前提版本、对应来源与相关冲突、检查集合。缓存再绑定审核模型身份与 prompt。只有完全匹配的包能附带该报告。审 A 不替 B 背书，局部全真不代替整题全真。

审核自己刚产生的异议不会反过来使自身报告立刻失效；匹配时只排除该报告自己新生成的意见，其余新证据/独立异议仍改变审核输入。清空草稿不删除旧意见。同答案新材料可以重新核对，但旧异议属于历史，不自动永久淘汰候选。

默认 diagnostic 允许明确未审/有争议提交，分别记录 audit_status 与正式答案。hard 要求匹配的完整 supported；off 不调用 auditor。hard 仍可能误拒正确答案，这不是结构能免费消除的风险。

## 11. 反馈与停止

局部反馈并置具体问题、被审核候选、来源句柄、最近动作以及 answer_changed / changed_claims。只改 focus 不表示改了 answer。程序提供字符事实，不补引号、不归一化单位、不从说明文字推测已经修复。

合法 noop 允许且不刷新版本；changed 不是语义成功。错误审核反例必须进入测试。若反复同参，按共同固定预算结束，不自动延长失败 episode。

模型请求预算统一包含 policy、audit 和审核格式修复；每次真实请求先记尝试，usage 缺失保留 unknown_calls。服务不自动重试；失败可能已计费，保留尝试不伪造 token。后端调用另计，不和模型轮数混为一谈。

启动审核前，剩余请求必须覆盖本次审核最大尝试与至少一次后续策略决定。缓存也保留一次策略反应预算。最后一次策略决定可以直接 submit；若仍选择读取，系统不自动替它提交。

模型答案原样保存。省略最终 refs 表示本次没有明确外部依据，不继承草稿来源。`require_sources=True` 可冻结有来源契约；编号专项必须使用这一模式。budget/service/interrupted 终态保留草稿，正式答案为空。

## 12. 存储、回放与进程边界

SQLite 每个事件有序号、前哈希和内容哈希，写入采用 BEGIN IMMEDIATE 与预期 head 检查。内存更新在数据库 commit 之后发生。并发写入不会静默覆盖，需要重新加载；不是多 worker 共享可变研究状态系统。

完整 state 快照随关键事件保存，回放只读并核验事件链，不执行历史工具。此版本偏重可核查性，长轨迹快照有存储放大，不宣称已优化大规模吞吐。哈希链是完整性检查，不是对恶意重写全库的认证。

`resume=True` 只恢复已完整结束的决策边界，并核对原题、配置、检索身份和容量单位。若进程在请求/动作组中断，标记 interrupted 而不重新发送未知是否完成的调用。旧 v2 数据库不迁移、不覆盖。

## 13. 外部运行入口

离线：

```bash
python -m pip install -e '.[test]'
python -m pytest tests/harness_v3 -q
python -m esr_harness_v3 smoke --db /tmp/esr-v3-smoke-new.sqlite
python -m esr_harness_v3 replay --db /tmp/esr-v3-smoke-new.sqlite
python -m esr_harness_v3 schema
```

真实前向需显式授权网络与预算，并使用部署侧已有 tokenizer：

```bash
python -m pip install -e '.[model,test]'
# ESR_API_KEY 从环境读取，不能写进仓库或命令回显。
python -m esr_harness_v3 run \
  --allow-network --question-file /private/question.txt \
  --db /private/runs/new-episode.sqlite \
  --base-url http://127.0.0.1:8000/v1 --model served-model \
  --retrieval-url http://127.0.0.1:8001 \
  --index-fingerprint ACTUAL_FROZEN_INDEX_HASH \
  --tokenizer /models/local-tokenizer \
  --max-model-calls 24 --max-actions 80 \
  --context-limit 32000 --output-reserve 2048 \
  --audit-mode diagnostic --require-sources
```

API 接口仅声明 OpenAI-compatible chat-completions；没有声称验证了 Lanz/Anthropic 原生格式。真实模型模板、工具 schema 接受度、输出预算参数和 token 计算需先做 provider 联通验收。`hf_counter` 禁用 remote code、只用本地 tokenizer；它必须与服务端模板核对。离线默认计数是 UTF-8 字节，明确不是 provider token。

本轮没有发起上述真实运行。CLI 没有内置从 BC+ gold 计算奖励；外部评测必须独立、冻结。

## 14. GRPO 与后续学习

`training_export` 导出真实请求、this 绑定、原始响应和动作记录。只有采样端显式提供 token_ids、old_logprobs、action_spans、tokenizer_identity 且通过结构检查，才标记记录采样完整；`--require-rl` 在信息不全时拒绝导出为 RL-ready。OpenAI 适配器当前不会凭响应文字重新 tokenize 来补齐这些量。

这不是完整 GRPO/verl 训练接入，不包含优化器、reward 或已训练权重。后续先建立均匀全链 GRPO，再测试有界来源调制与等集中度随机对照。程序自动上下文重建不算策略 read，后台失效不算模型修复。直接选择、继承来源、导航和因果贡献分开。

恢复 SFT 要使用策略自己的坏前缀，包含真实修复、错误审核、无需记忆、相似来源消歧和短结束。不能在封存题上构造补丁，不能以固定 c1/o1 身份作为捷径。

## 15. 测试与迭代范围

具体结果见 VALIDATION.md。此次测试直接导入新包，覆盖结构、引用快照、依赖、事务、审核、预算、历史恢复、SQLite、原生 HTTP 往返和导出。合成 fixture 的答案只测执行可达，不是 BC+ 成绩。

仍待实测：模型是否会选对来源、this 是否真能减负、关系图缺边率、修订后的线索丢失、审核误拒、强 API 简单题是否降低总成本、真实 tokenizer 与 provider 是否一致、全库吞吐。旧 v2 源码保持原样；旧全集测试是否执行必须单独报告，不将新测试数冒充全仓测试数。

后续严格按 ITERATION_PROMPT.md：先契约，再固定前缀，最后自然配对。不能在同一次实验同时替换接口、模型、检索、审核和奖励，然后把收益都归为 ESR。
