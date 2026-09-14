# a3 单题采集与事后判分工具

这些脚本为固定 release 的自然运行提供完整采集和只读分析。它们不会自动获得真实调用授权；执行前必须准备原始 question-only 输入、现有生产索引、模型环境和既有持久预算。完整实验合同见 [CODEX_Q26_RETEST_PROMPT.md](CODEX_Q26_RETEST_PROMPT.md)，已完成的脱敏观察见 [THREE_CASE_REVIEW_A3.md](THREE_CASE_REVIEW_A3.md)。

## 文件

| 脚本 | 用途 |
|---|---|
| `examples/trace_q26_a3.py` | 保留实际 q26 采集版本，固定 qid=26 |
| `examples/trace_question_a3.py` | 按冻结计划检查任意一个 qid；模型仅接收 question |
| `examples/trace_pair_a3.py` | 两题启动前核对全部预算覆盖和冻结输入；顺序运行，任一未提交即停止队列，不自动重试 |
| `examples/analyze_q26_a3.py` | 名称保留历史用途；实际支持任意上述 episode 的只读工具、查询、shelf、find、recall 和 finish 检查 |
| `examples/audit_trace_supplement_a3.py` | 完成后的响应对应、工具执行关联、原文生命周期及 usage 缺失字段规范化 |
| `examples/judge_frozen_a3.py` | 使用仓库 judge，对已封存的正式答案各调用一次；结果绑定原始 Archive head |

采集器保存实际 HTTP 请求／响应 body，不保存秘密请求头；如响应回显凭证，保存替换后的版本、明确标记 sanitized_response 并停止。发送前在现有 SQLite 总账原子占账，失败和未知状态仍计数。不会创建新真实总账绕过既有额度。

## 固定版本与私有计划

两个自然运行采集器刻意要求 HEAD 等于 `5d7752be94a9d40aa757383d8899504bc0f81e81`。它们是复测工具，不能直接在新增文档提交的 HEAD 上启动真实 episode。若另有授权，需要创建该 release 的独立 worktree，将本提交的采集脚本复制过去，安装该 worktree 的 STRIDE，再冻结所有哈希。不要为了运行而删除版本检查。

计划是私有 JSON，包含 worktree、output、qid（通用版）、question_path／question_sha256、source_hashes、collector_sha256、完整 Config、base_url、budget_path、index_path／index_id／index_identity。输出目录必须不存在。question 文件只能含 qid 与非空 question。凭证来自 ESR_API_KEY，base_url 与 ESR_BASE_URL 必须一致；本脚本的模型身份与 Config 固定为本次复测设置。

总账使用既有的 budget(cap) 单行表和 requests(id, run, role, status, http_status, usage) 表；单题启动前要求余量覆盖 32 次。两题计划的 plans 包含两个 path／sha256，入口预检要求同时覆盖 64 次，并拒绝重复题号、不同总账和已存在输出。每次发送仍检查全局和单次运行上限，因此并发消费者耗尽余量时会停止。该两题包装器比通用实验队列更保守：所有非 submitted 终态都会停止后续题目。

从仓库根目录运行，路径为使用者自行准备的私有计划：

```bash
python harnesses/stride/examples/trace_question_a3.py --plan /private/question.plan.json
python harnesses/stride/examples/trace_pair_a3.py --pair /private/pair.json --preflight-only
```

以上不是随附的可直接启动生产请求的配置。题目、地址、生产身份与预算都必须由实际环境提供并冻结。

## 完成后分析

```bash
python harnesses/stride/examples/analyze_q26_a3.py /private/completed-episode
python harnesses/stride/examples/audit_trace_supplement_a3.py /private/completed-episode
```

两个分析脚本不调用模型、不查询生产索引。它们读取已保存的事件、原始 HTTP 和 snapshot，输出机器检查。补充分析先保存原 metrics 副本，再增加 usage_normalized，将供应商未报告字段记为 null；应在最终封存前执行。导出文件采用排他创建，不用于覆盖已经封存的目录。

完整交互和表格不会自动取代人工论证审计。最终 claim→refs→原文是否支持、错实体还是错范围、未找到证据还是未继续检索等，需要根据实际轨迹单独判断。不得将搜索卡片或未读全文加入正式引用。

## 事后 judge

judge 计划冻结 cases_path／cases_sha256、judge_source／judge_source_sha256、capture_source／capture_source_sha256、runner_sha256、既有预算和新输出目录。每个 case 包含 qid、slot、source_run、source_manifest_sha256、head、原始 question、response 和基准 correct_answer。它检查已提交 Archive 的题目、答案和 head，不替调用者加载或核验基准数据；准备阶段必须验证 query_id、原题及基准来源哈希。

judge 使用 `src/esr_grpo/judge.py` 的现有提示词，不自动增加过程评审。每题一次、temperature=0、top_p=1、max_tokens=2048；响应模型必须为 glm-5.2，finish_reason 必须为 stop，correct 必须是真正 JSON 布尔值。解析失败、截断、身份变化或 HTTP 错误停止队列并保留已完成判断，不补跑。

```bash
python harnesses/stride/examples/judge_frozen_a3.py --plan /private/judge.plan.json
```

结果为独立的 judgments.json 和 slot/head/correct 标签，不修改原 episode。slot 只在对应 roster 内有效。项目返回结果中的默认 confidence 不得误报为模型置信度。默认将 gold、最终答案、请求／响应和预算记录留在私有目录；本次用户事后明确授权公开完整轨迹，发布副本见[完整资料](../artifacts/20260914-three-case-a3/README.md)，密钥和真实预算数据库仍不上传。

## 公开副本

`examples/publish_trace_bundle_a3.py` 校验源封存清单后生成新目录。它仅替换部署主机与本机用户路径，拒绝改写 content-addressed objects 和原始 HTTP body。SQLite 只允许模型身份元数据变化，并重算事件链；公开 head 与原始 head 的对应另存。`reading_views` 生成按轮阅读文件及独立文档／证据文本，所有内容仍来自已完成 Archive，不调用模型或后端。

## 只用合成数据验证

从仓库根目录运行：

```bash
python -m pytest -q harnesses/stride/tests \
  harnesses/stride/examples/test_trace_q26_a3.py \
  harnesses/stride/examples/test_trace_question_a3.py \
  harnesses/stride/examples/test_trace_pair_a3.py \
  harnesses/stride/examples/test_judge_frozen_a3.py
```

测试使用 localhost、合成问题、单文档索引与独立合成预算；自然运行器的 expected release 只在合成 fixture 内设为测试 checkout 的 HEAD，使新增提交后仍可测试。生产脚本的固定 release 常量保持不变。Windows 上应给 pytest 指定新的可写 basetemp，并让 localhost 绕过代理。
