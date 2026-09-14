# Codex 执行提示词：STRIDE a3 的 q26 单题自然复测

> 目的：使用已经发布的 `research/stride-a3-cpu-evidence-20260914`，对此前旧 ESR 分析过的开发题 q26 做**一次**新的自然运行，记录完整交互并只读分析。不要重新设计 harness，不训练模型，不增加 Agent，不通过反复调 prompt 把已知题跑到成功。

## 1. 版本门禁：失败就停止，不要在旧 a2 上冒充 a3

仓库：`homulillew/ESR-Tra`

目标分支：`research/stride-a3-cpu-evidence-20260914`

a2 基底：`badc82df9bfabc374ded7e8cf1b281815c46be88`

开始任何付费请求前：

1. `git fetch` 后记录目标分支实际 HEAD；它必须是 a2 的后继且不能等于 a2。
2. 核验 `harnesses/stride/src/stride_search/cpu_index.py`、`search_support.py`、`diagnostics.py` 存在。
3. 核验 `stride_search.__version__ == "0.1.0a3"`，`contract.PROTOCOL == "stride-search-3"`，import 路径来自当前 worktree。
4. 核验 CLI 存在 `--sqlite-index`、`--evidence-shelf-size` 和 `diagnose`。
5. 先运行完整 pytest；任何失败都停止真实运行，封存日志。
6. 记录当前 release SHA、Python、SQLite、依赖版本、源文件 hash。不要把分支名当作版本证明。

工作区有未保存改动时不 reset、不 clean、不覆盖；使用独立 worktree 或返回阻塞。

## 2. 历史信息只能用于事后分析，禁止泄露给被测 policy

新方案需要先读：

- `harnesses/stride/README.md`
- `docs/DESIGN.md`
- `docs/RECOVERY_A2.md`
- `docs/CPU_EVIDENCE_A3.md`
- `docs/EXPERIMENTS.md`
- `docs/VALIDATION_A3.md`
- `contract.py / context.py / engine.py / archive.py / providers.py / cpu_index.py / search_support.py / diagnostics.py`

历史单题分析固定在 `ac8d1bb9a158efb4c442e7bd59d08d50ac5b5354`：

- `docs/v3/iterations/20260914_single_api_review.md`
- `docs/v3/iterations/20260914_single_api_metrics.json`
- `docs/v3/iterations/20260914_harness_openai_contract.md`
- `scripts/trace_single_v3.py`

旧完整私有记录预期位于 `runs/single_api_trace/20260914T032110Z_q26/`，先核实是否真的存在。

**严格隔离：**新运行的 policy 只能接收原始问题、a3 正常构造的 system/control state 和本轮工具结果。不要把本提示词、旧答案、已知候选、旧有效查询、旧原文、gold、人工笔记或旧 bad-case 结论注入模型。不要预填 notes，不指挥它打开某个已知文档。旧完整轨迹只在新运行结束后做对照。

如果找不到原始 q26 question-only 输入，就停止，不猜题、不重建题目。

## 3. 保持 CPU 后端，不升级检索器

本轮的目标之一就是检验：**明确 CPU LocalIndex 的真实查询能力 + a3 上下文/恢复机制，是否改变搜索过程。**

因此：

- 使用已有的只读 CPU SQLite FTS5 生产索引；不重建、不写库。
- 不增加 GPU、embedding、reranker、Web Search 或新的检索模型。
- 不把 OR 改成 AND，不增加短语过滤，不增加 site 域过滤。
- 核验 metadata、文档数、tokenizer、SQLite runtime、索引路径及 index_id；旧报告数字只能当待核对值。
- a3 的 `SQLiteFTS5` 应保持：小写 → `\w+` 提词 → 首次出现去重 → 单词 OR → SQLite `bm25(search)` → docid 同分排序。

记录每个 query 的原始字符串、实际 compiled terms/expression、top_k、equivalence key、cache hit 和结果文档。

`compiled_query_cache=False` 保持默认关闭。不要为了使结果好看而开启缓存；缓存只应该在另一个消融中测试。

## 4. 模型与一次性运行合同

优先保持旧实验服务条件：OpenAI-compatible Chat Completions，请求模型 `EB-GLM-5.2`，期望返回标识 `glm-5.2`，temperature=0。

注意：当前 `stride-search run` 没有 temperature 参数，而 OpenAIModel 默认值不是旧实验的 0。请新增一个**薄采集入口**显式构造 `OpenAIModel(..., temperature=0)`，只负责配置、持久预算和完整记录；不得修改 engine、工具定义、CPU 排名或 policy 输入。

实际 base_url 和 API key 只使用用户已经配置的私有环境。不要打印密钥、不要搜索其他账号、不要切换模型。返回模型身份变化则停止。

本轮只运行 q26 **一次**：

- 不跑 baseline；
- 不跑 shelf=0 等消融；
- 不跑多 seed；
- 不调用 auditor 或 judge；
- 不失败后修改 prompt 再重跑；
- 不采样到成功。

## 5. 在开始前冻结完整 Config

建议单题配置：

```python
Config(
    max_model_calls=32,
    max_actions=100,
    max_backend_calls=60,
    max_batch=4,
    max_queries_per_search=3,
    max_output_tokens=4096,
    max_total_output_tokens=24000,
    context_limit=96000,
    response_reserve=4096,
    read_chars=3000,
    max_seconds=900,
    context_mode="rolling",
    notes_enabled=True,
    reserve_finish=True,
    require_sources=True,
    nonblocking_notes=True,
    repair_context=True,
    delivery_preflight=True,
    disclose_retriever=True,
    compiled_query_cache=False,
    evidence_shelf_size=3,
    recall_navigation=True,
    centered_recall=True,
    answer_prefix="",
    answer_suffix="",
)
```

未列字段使用 release 默认值，并把最终 `Config.to_dict()` 全量写进 manifest。

使用 `ByteCounter` 时明确 `context_limit=96000`、`response_reserve=4096` 的单位是 UTF-8 bytes，不是 provider token；`max_output_tokens=4096` 是模型输出参数。不要把二者写成统一 token 预算。

模型 HTTP timeout 建议 180 秒；CPU SQL deadline 45 秒，分别配置，不共用一个 CLI timeout 偷偷改变旧 SQL 条件。

## 6. 先检查授权和持久总账

在发出第一次真实模型 HTTP 前：

- 核对本轮明确授权；
- 核对已有项目级持久总账和剩余额度；
- 不允许通过新建一个预算数据库重置历史额度；
- 本轮最坏按 32 次模型尝试预留。余额不足则返回 BLOCKED_BUDGET，不发送请求。

每次真实 HTTP 发送前原子占用预算；未知是否计费的失败继续占账。401/403/429、超时、截断、模型身份变化或完整性错误发生后封存并停止，不自动重试，不换账号，不开第二局。

## 7. 只补采集层，不修改策略

允许新增类似：

- `harnesses/stride/examples/trace_single_question_a3.py`
- 独立只读 export / analysis 脚本
- loopback 与预算正反测试

采集层可以：读取 question-only、构造固定 Config、构造 `OpenAIModel(temperature=0)`、记录实际请求/响应、管理持久额度、导出分析。

采集层不能：给模型指定 query、ref、candidate、notes 或答案；不能替模型改错参数；不能根据旧 q26 自动设置格式约束；不能改变工具描述、检索排序、上下文保留、终答或缓存开关。

代码先离线测试并冻结 hash，再开始真实 episode。运行期间不得改代码。

## 8. 私有产物必须完整保存

新目录，例如：

`runs/stride_single_api_trace/<UTC>_q26_a3/`

若目录存在则拒绝覆盖。

至少保存：

- `manifest.json`：release SHA、采集 commit/hash、完整 Config、模型/索引/计数器身份、预算合同；
- `question.txt/json`：仅 qid + 原始 question，不含 gold；
- 每次真实 HTTP request/response body、UTC、耗时、returned model、finish_reason、usage；
- `episode.sqlite`；
- `trajectory.jsonl`；
- `FULL_INTERACTION.md`：逐轮实际输入、可见 eN、shelf、搜索卡、模型输出、tool_call、action_execution、action_result、下一轮回执、预算；
- `ROUND_TABLE.csv`；
- `QUERY_EXECUTION.csv`；
- `VISIBILITY_TABLE.csv`；
- `EVIDENCE_AUDIT.md`；
- `INTEGRITY_CHECKS.json`；
- `INTERACTION_ANALYSIS.md`；
- `result.json`、`metrics.sanitized.json` 和文件 SHA256 清单。

使用 `Archive.load_request()` 对照真正发出的 request body。若序列化不保证字节完全相同，要写“结构等价”而不是“原始字节相同”。SQLite 在关闭后复制，或用一致性 backup，不能漏 WAL。

这些真实材料保持私有，不推公共仓库；公开仓库只能提交采集代码、合成测试和脱敏汇总。

## 9. 运行后逐轮回答七组问题

### A. 工具落地

逐轮核对原生 tool call ID/顺序/参数 → `action_execution` → `action_result` → 下一实际请求中的 tool receipt。

区分：

- 工具真正未执行；
- 后台提取成功但 a2 `delivery_preflight` 因容量撤下；
- 已形成回执但下一请求没送达；
- 末次 finish 正常终止，不需要再花一次模型请求回传回执。

### B. CPU 查询语义

逐条列出原始 query、compiled terms/expression、top_k、结果、equivalence key、cache 状态。

检查模型是否仍写引号、`site:`、AND/OR，并且是否理解 capability 声明。不要把编译相同自动判为无效搜索；还要看结果集合和后续证据是否改变。

### C. 原文连续性

对关键原文分别标记：

1. 后端取得；
2. eN 创建；
3. 第一次实际放进请求；
4. `delivery_ack`；
5. shelf 中保留／被容量驱逐；
6. 最终是否引用。

重点看：在类似旧第 16–18 轮的错误阅读之后，早期主线 eN 是否仍进入后续请求；是否因为 shelf 付出明显额外输入；是否保留了错误原文导致锚定。

### D. 错页与导航

当模型说想读人物 A，却选择 dN 时，对照该轮实际 dN、URL/title/snippet。区分非法 ID 和合法但语义选错对象，绝不能根据模型散文替它改 ref。

检查 `recall_navigation` 是否找回以前已收到但没打开的 search hit；导航仍不能直接引用，必须 read。

### E. notes / recall / find

记录 notes 写入、替换、删除、noop 和 anchors；不要因为本题曾经晚写状态，就强制模型现在提前写。

记录 recall 命中来自 evidence / search_hit_navigation / note 哪类；centered excerpt 是否实际展示查询词；`find(ignore_case)` 是否使用，偏移是否对应原文。

未触发机制写 `NOT_EXERCISED`，不要为了测试功能强迫模型调用。

### F. 最终引用充分性

运行结束之后再把正式回答拆成原子断言，逐条核对 `finish.refs` 对应的准确 eN 文本，标记：

- supported；
- contradicted；
- not_established。

必须区分“模型曾经看见的材料”和“正式声明的 refs”。若为了复核另外读取邻接内容，标记 `posthoc_expanded_evidence`，不能回填成原提交依据。

这只是开发证据审阅，不是官方 judge；`formal_correct` 继续保持 null。

### G. 终止与成本

记录：

- 进入 FINAL 的轮次；
- 是否真的发出 FINAL request；
- 是否返回合法 `finish`；
- 是否 submitted / abstained / budget/error；
- model decisions、真实 HTTP attempts、native tool calls、search 内 queries、backend SQL/get_document、cache、input/output/cache tokens 和时间。

一项 search 里三条 query 是三次后端检索，不要记成一个。缓存输入不要重复加到总输入。未知 usage/cost 保持 unknown。

## 10. 与旧 q26 只能做描述性对照

旧 ESR 公开记录：29 policy 请求、32 search、7 open_page、1 update_state、1 submit_answer、0 audit/judge、36 backend，约 184.569 秒，终态 submitted/unverified。

新旧工具、状态、上下文、query 批宽、cache 与终答规则不同，因此只能描述：

- 新运行用了多少请求；
- 关键原文是否持续可见；
- 查询是否仍存在等价重复；
- 是否重搜了已经取得的主线；
- refs 是否覆盖最终断言。

不要据单题差值写“准确率提升 X%”或“STRIDE 因果减少 Y 轮”。本轮不运行 judge，不能把 submitted 当正确，也不能把 abstained 当错误答案以外的正式判分。

## 11. 发生 bug 时如何结束

发现代码/传输 bug：

1. 立即封存这一局；
2. 保留原请求、响应和数据库；
3. 离线构造最小复现；
4. 写修复建议；
5. **本轮不要修完后重新跑 q26 到成功。**

最终报告将问题分为：

- 已核验代码 bug；
- 按设计执行但代价不合算；
- 模型已得到正确输入但选择错误；
- 后端/语料没有足够材料；
- 只有相关性、尚无因果证据的解释。

下一步最多建议一个主要机制实验，单独预登记预算，不在这次单题之后偷偷追加调用。
