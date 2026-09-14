# 单题 API 交互核对与执行回执修复

日期：2026-09-14。真实运行基础提交 `a4926f3eeceda249817ef0cb93abb8e71d107e45`，运行时分支为 `research/esr-v3-auto-20260911T111515Z-f67a902`。独立审阅分支为 `research/single-question-harness-review-20260914`，从该提交创建。

本轮按用户要求只采集一个开发题的完整真实交互，随后分析工具交换问题。完整题目、响应、证据及逐轮报告保存在私有 `runs/single_api_trace/20260914T032110Z_q26/`，不进入公共仓库。没有读取参考答案、运行 baseline、重新挑题或在失败后重复采样。

## 实际链路和结果

使用用户指定的 OpenAI 兼容路由和 EB-GLM-5.2，网关返回标识为 glm-5.2。本机使用已有 CPU SQLite FTS5 BM25 索引，模型在远端运行，无需本地显卡。采集器只增加传输记录、独立持久预算和本地索引接入，真实运行期间 v3 核心源码保持不变。

29 次 HTTP 请求均成功；41 次原生工具调用全部处理，其中 12 次响应包含两个调用。下一轮所需的 40 个回执按原始 ID 和完整内容送达；最后一次提交回执留在本地，无额外请求。40 次动作成功、1 次参数拒绝，最终 submitted/unverified。没有正式判分，不能报告准确率或正确完成速度。

实际 policy/auditor/judge 请求为 29/0/0；用户本轮上限 100，剩余 71。输入 422720 tokens，输出 3301，输入中含缓存 355328。后端调用 36 次，整局 184.569 秒。费用金额缺少结算依据，不作推断。上下文采用字节保守计数，因此本次不构成等 token 预算比较。

## 真实问题与最小修复

一次 open_page 同时给出 cursor 和 query，在 schema 校验阶段被拒绝，后端未调用，旧回执却报告 executed=true。策略下一轮自行去掉 query 成功恢复，拒绝本身符合契约，标记不符合实际执行阶段。

`src/esr_harness_v3/engine.py` 增加 dispatched 标记，在进入 `_dispatch` 前设置 true。解析、参数校验或审核动作预算检查失败时返回 executed=false。executed 表示是否进入工具分发，不表示后端调用或成功提交；后两者分别以 backend_request 和 action_commit 判断。

`tests/harness_v3/test_receipt_execution.py` 用合成 cursor/query 反例验证拒绝标记、后续调用的 not_executed 回执、后端计数及下一轮传递。反向用例覆盖进入分发后拒绝：executed=true 可以与后端计数 0 同时成立。

另外新增 `scripts/trace_single_v3.py` 和 `tests/harness_v3/test_single_trace_capture.py`，保存实际请求/响应、工具结果、未知失败和持久计数，凭证只从 ESR_API_KEY 读取。测试使用本地 HTTP fixture，不调用远端。

真实轨迹在修复之前采集，原始错误标记保留。修复后仅做离线验证，未用新的真实请求宣称模型行为改善。

## 验证记录

1. 采集器验证：3 通过。
2. 修复前合成反例：1 失败、1 通过，复现 executed 错误。
3. 首次修复后联合测试：274 通过、1 失败；失败来自新增测试误用 Decision.request，纠正为实际 Decision.payload。失败记录未覆盖。
4. 最终 `python scripts/validate_v3.py --include-legacy --output runs/single_api_trace/20260914T032110Z_q26/validation-final`：v2/v3 联合回归 **275 通过**，compileall、schema、smoke、只读 replay、export 全部通过。远程请求 0。

最终验收 manifest、每条命令输出和 JUnit 均在该新目录。真实账本只读回放命令：

```powershell
python -m esr_harness_v3 replay --db runs/single_api_trace/20260914T032110Z_q26/attempt01/episode.sqlite
```

复用验收命令时使用新的输出目录。原始完整报告为私有目录中的 INTERACTION_ANALYSIS.md，逐轮全文为 FULL_INTERACTION.md；采集命令、实际配置和全部成本均在报告中。

## 决定与边界

保留采集器和 executed 修复。协议检查通过仅说明本次调用没有丢失，不能证明整体无 bug。真实轨迹另显示：本地 OR 检索不支持模型使用的 site/短语语义；合法编号仍可选错文档；压缩可能移除尚未写入持久结论的重要证据；已送达原文不保证最终引用覆盖全部断言。详细证据及因果推断的限制见私有报告。

本轮未修改检索排名、上下文压缩、引用切分、状态写入规则或审核触发。没有新的算法对照、正式 judge 或训练。下一项可证伪假设是：仅明确描述本地搜索的范围和查询语义，在其余条件固定时，能否减少无效查询并保持完整任务结果。尚未执行，不能报告收益。

## 给独立审阅者的入口

从本文件开始，结合 [逐轮分析与排查问题](20260914_single_api_review.md) 和 [脱敏运行统计](20260914_single_api_metrics.json) 阅读本分支相对基础提交的 diff。代码链接：

- [采集器及本地检索接入](../../../scripts/trace_single_v3.py)
- [工具执行和回执](../../../src/esr_harness_v3/engine.py)
- [参数与工具描述](../../../src/esr_harness_v3/protocol.py)
- [上下文构建](../../../src/esr_harness_v3/context.py)
- [状态和答案来源](../../../src/esr_harness_v3/state.py)
- [最小反例测试](../../../tests/harness_v3/test_receipt_execution.py)
- [采集器测试](../../../tests/harness_v3/test_single_trace_capture.py)

公开记录提供逐轮行为概述、原文句段关系的说明、成本与核对结果；真实题目、答案、provider 原文和完整付费轨迹按仓库执行规范保留在本地 private runs。远程审阅者可以检查实现和反例，不能仅凭公开统计独立重验全部真实 HTTP 内容。请将这种证据可见范围与已在本地完成的逐字核对区分开。
