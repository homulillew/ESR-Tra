> 当前版本 a2；新增三项恢复机制分别做单变量对照，详见 [RECOVERY_A2](RECOVERY_A2.md)。尚无真实模型/BC+ 效果。

# STRIDE 的实验合同

## 1. 区分三层结果

离线契约测试证明实际输入下程序执行了什么，不证明模型会生成那个行动。固定前缀续程证明某一干预改变了后续行为，不证明完整未见任务收益。自然配对实验才用于判断固定强模型的准确率—成本变化。

本发布只完成第一层及本地 HTTP fixture。没有真实模型请求、BC+ rollout、隐藏确认集或训练。所有 fixture 中的目标答案都是明确的合成协议材料，不用于论文成绩。

## 2. 首轮只检验一个额外状态机制

建议的第一轮对照是：共同 STRIDE 执行内核、相同检索与终止合同；一臂 notes_enabled=False，一臂 True。这样能回答小便笺是否值得，不混入 auditor、检索器、模型或结束手续的变化。

两臂都具有 read/find/recall、同样的来源要求、预算内终答与相同上下文策略。它们是“STRIDE 内部 notes 消融”，不能自动命名为普通 ReAct 或无 harness baseline。外部强原生 baseline 需要另立同环境适配，当前没有实现所有外部项目的复现。

只有 notes 显示出净收益，才继续检验更细的上下文退出或分支。没有收益时关闭 notes，而不是增加强制登记字段。

## 3. 可冻结的差异

make_plan 允许 notes_enabled、reserve_finish、context_mode、max_batch、max_queries_per_search，以及 a2 的 nonblocking_notes、repair_context、delivery_preflight 在实验臂之间不同。model、retriever、计数器、来源要求、答案字面合同、总模型预算等必须一致。允许多字段差异是为研究模式准备，不代表可以一次改五项然后归因于其中一项；每轮应在文字预登记中明确唯一假设。

严格的串行宽度对照必须同时设 max_batch=1 和 max_queries_per_search=1。只限制 native 调用个数而保留三查询数组，仍不是单查询系统。

context_mode=full 与 rolling 的比较需要报告实际压力条件。极窄窗口里的 full 溢出不能证明正常强模型宽窗口的普遍收益。

## 4. 样本隔离

questions.jsonl 每行只能有 id/question。额外 answer、gold_docid、label 等字段直接拒绝，不悄悄读取再过滤。不从旧成功题/失败题选择最终确认样本，不将已研究 q790 等当成未见结果。

case/repeat/arm 在开始前冻结，题内臂顺序按登记的 seed 打乱，避免永远先运行同一臂。该 seed 控制队列，不代表云模型采样被固定；模型不可用的 seed/thinking 控制不能伪造。

冻结模型的请求名、版本标签、可选 expected_response_model、检索索引身份、计数器身份、全部参数、source_hashes 和完整队列。代码改变后必须新实验，不覆盖原计划。运行期间每个 slot 前再检查源指纹。

## 5. 预算和完整分母

run_plan 要求 max_total_model_calls 足以覆盖整个冻结队列的最坏模型请求数，不靠平均值启动一个注定不完整的大批次。计数包含所有模型尝试；没有额外 auditor 或摘要器；后端和 action 单列。

模型/服务/完整性错误停止后续队列，已产生结果与 NOT_RUN 槽位都保留。正常任务预算耗尽保留失败，然后继续队列。没有自动补跑、换账号、换模型或跨日重置预算。

源代码错误会记录 implementation_error 并停止队列，不标作“证据不足”。发生异常后原始 plan 仍足以进行只读汇总。队列级初始化/文件系统异常可能需要手动运行 summary；不会重发请求。

## 6. 独立判分

默认没有在线/离线答案判断模型。summary 的正式正确率在缺少必要判断或存在 NOT_RUN 时为 null，不能用“submitted”或“有来源”代替正确。

外部独立进程可在全部 rollout 结束后，用原题、正式答案与指定 benchmark 判分合同生成 judgments.jsonl。格式是：

```json
{"slot":"0000","head":"exact-final-ledger-head","correct":true}
```

judgment 只适用于 head 完全匹配且确实 submitted 的运行；重复、未知、未执行或过期 head 被拒绝。非提交终态计为该已运行槽位失败。NOT_RUN 始终不是一个虚构零成本完成；不计算完整队列准确率。

判分工具、模型、版本和费用应由外部评测报告记录。当前代码不自动验证人工标签来源，绑定 head 只防误用旧记录，不证明 judge 正确。

## 7. 运行范例

先生成合成计划验证接口：

```bash
python -m stride_search cohort-fixture --output /tmp/new-stride-cohort
python -m stride_search summary --output /tmp/new-stride-cohort
```

真实计划应由实际部署对象的 identity 构建，不能照抄示例假指纹：

```python
from stride_search import Config
from stride_search.experiment import make_plan, read_cases, write_new

# model/retriever/counter 必须来自本次已验收部署；这一步只构建计划，不请求模型。
wrapper = make_plan(read_cases('/private/questions.jsonl'),
    Config(max_model_calls=24, context_limit=100000, response_reserve=8192),
    {'notes_off': {'notes_enabled': False}, 'notes_on': {'notes_enabled': True}},
    model_identity=model.identity, retriever_identity=retriever.identity,
    counter_identity=counter.identity, repeats=1, seed=20260914)
write_new('/private/new-plan.json', wrapper)
```

也可用 CLI `plan --questions ... --config ... --arms ... --identities ... --output ...` 从明确 JSON 配置生成。随后 `cohort` 使用与计划匹配的 live 连接参数、--allow-network、--accept-counter-estimate 和 --max-total-model-calls。身份不匹配时不发送模型请求。

```bash
stride-search cohort \
  --plan /private/new-plan.json --output /private/runs/new-cohort \
  --allow-network --accept-counter-estimate --max-total-model-calls 480 \
  --base-url http://127.0.0.1:8000/v1 --model served-model \
  --model-revision frozen-deployment-label --model-api openai \
  --retrieval-url http://127.0.0.1:8001 --index-id actual-index-fingerprint \
  --counter utf8_bytes
```

480 仅为示例上限，不是对本项目旧授权的复用。代码会检查它是否覆盖实际 plan.maximum_model_attempts；不足时在创建输出目录和发送请求之前拒绝。

## 8. 必须报告的指标

| 指标 | 实现/来源 | 解释边界 |
|---|---|---|
| formal accuracy | 外部 judgment 绑定 terminal head | 完整分母，缺失判分不猜测 |
| model_attempts | 每次发送前登记 | 包括失败尝试；fixture 不是供应商调用 |
| backend_attempts | 实际检索/正文请求前登记 | 缓存命中不计新后端请求 |
| actions_recorded / executed | 原生每项回执 / 实际调度 | 并列工具、数组查询与模型轮数不同 |
| usage_known / unknown | 原始响应字段 | 不能把 unknown 当零；cache 单列 |
| final_phase_requests | 请求中的明确阶段 | 不是正确完成数量 |
| rounds_receiving_new_raw | 完整响应确认过的交付 | 不是模型已理解或证据已充分 |
| compaction_requests | 实际上下文重建 | 不是压缩质量 |
| unchanged_note_updates | 字符与引用完全相同的写入 | 不能把所有 noop 都当错误 |
| elapsed_seconds | Harness 建立到终态 | 不包括安装/服务启动/tokenizer 预热 |

额外的“首次充分证据”“第一次错误承诺”“首次可正确提交”应由离线逐段诊断给出，不由 qrels 文档命中直接自动推导。它们只用于研究，不作为运行时 gold oracle。

## 9. 实验决策

主目标是在相同总预算下提高正式准确率，并检查模型请求、后端请求与总成本是否下降；同等准确率附近再比较成本前沿。只减少工具或增加提交率不能判定成功。

开发阶段可预登记成本可负担的成对任务与重复数；最终确认样本量应根据目标效应和 pilot 的配对差异决定，不机械复用七题或九题来声明统计显著。开发题与确认题分离，计划冻结后不挑成功局补报。

外部不变量测试不能代替概率能力验证。反向样本至少包括无需便笺的短任务、错误便笺、多个类似实体、旧方向被推翻、来源片段足够但输出格式错误、长文中目标位于后半段，以及末轮仍有潜在有效检索的任务。

任何机制若只提高中间合法率却没有改善正确提交与净成本，应该回退该机制，而不是改变 judge 或追加更多控制字段。
