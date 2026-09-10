# 原生工具调用、文本动作与 focus 失败恢复验收

执行日期：2026-09-10。生产补丁：`1658bd656fc495af6760b720b5d78f3363e3627d`，分支 `research/strong-api-esr-20260909`。本阶段是共同执行基础设施修复，没有引入新的 ESR 研究机制。

**上次复核确认的两个缺陷已修复，新增离线流程能走到正式提交。完整回归通过 288 项；本阶段新增远程 API 请求为 0。** 当前证据支持这两个缺陷得到修正，不能据此宣称所有链路无 bug，也不能宣称 ESR 的准确率、成本和速度已经优于 baseline。

ESR（Evidence-State Research，保存原始证据、可修订结论和待解决问题的研究方法）使用 focus 指定当前要解决的关系。本地 harness 负责校验、执行、提交状态、交付结果与记账；自然 rollout 的 policy 和 auditor 仍由用户指定的 Lanz-Medium API 承担。本阶段的本地脚本策略只用于合成回归，没有作为被测强模型或 BC+ 效果样本。

## 修复内容

| 场景 | 修复前的行为 | 当前行为 |
|---|---|---|
| baseline 先收到原生调用，再收到严格文本 JSON 动作 | 容量预演从已提交日志寻找尚未提交的动作，抛出 `StopIteration` | 已提交动作保存真实日志位置；预演副本为新动作分配后续位置，保持历史顺序且不写入真实日志 |
| 文本 open 的内部容量预演 | 内部探测事件可能没有 `decision_id`，无法按统一历史格式渲染 | 预演补充空决策标识；正式提交仍保存实际决策标识 |
| 第一项 search 的 focus 修改失败，后项隐式使用该 focus | 后项可能在旧 focus 下执行并记录错误研究目的 | 组记录每项预期 focus；执行前检查已提交状态，缺失依赖时返回 `dependency_failed` 和 `execution=not_executed` |
| 第一项有其他参数错误，focus 本身有效 | 准备阶段可能忽略该 focus 提案，使后项退回旧状态 | 即使另一字段非法，也保留后项预期依赖；不把未提交的修改当成当前状态 |
| 同一 focus 的 need 存在首尾空格 | 规范化前后比较不一致，可能错误拒绝整组 | 按状态接口同样的规则规范化后比较，原始模型参数完整保留 |

后项能独立建立同一 focus 时可以执行，例如第二项 search 自己显式提供有效 focus。第一项失败但所需 focus 本来就已存在时，也不会阻止独立检索。目录读取不使用 focus，因此不增加无关依赖。对于现有契约允许保留 focus 的 `retrieval_error`，只要修改已提交，后续检索可以继续；容量、预算和结果未知的服务故障仍按原有停止规则处理。

每个合法原生调用 ID 仍有对应回执，失败与未执行分别保存。前项已成功的结果不会因为后项失败被删除。没有替模型改写查询、补造引用或自动重放结果未知的调用。

## 离线验收与真实证据的界限

新增 24 项回归，覆盖以下行为：

- B 与 E-off 从任一种响应格式开始，多次切换原生调用和文本 JSON，依次搜索、打开、重读、继续搜索并正式提交；检查实际适配后的请求内容、正文与 ID 配对。
- baseline 通过日志回放重建完整历史顺序，容量拒绝不提前提交搜索结果，也不改变之前的原生结果。
- 第一项在参数校验、focus 校验或运行时引用检查失败，后续 search/open/read 返回未执行；断言跳过的调用没有后端 I/O，也没有伪造已开始记录。
- focus 正常提交、已经存在、由下一项显式建立，以及检索错误后保留 focus 等可继续执行的分支。
- 策略下一轮收到两个错误回执，显式修复 focus，再完成打开、引用、答案更新和提交。这个流程使用本地固定响应和同一个真实 adapter/runner，没有远程模型调用。
- 重启只读回放保留预期 focus、已完成回执和最终状态；离线检查器识别缺少正文的负例。

开发测试的全部输出都保留。第一轮为 15 失败、6 通过，其中两个失败来自测试把含换行的原文直接与 JSON 序列化字符串比较；不能把这两个测试错误统计为生产缺陷。生产补丁后四个格式切换场景均走到正式提交，但同一个测试断言仍报错。随后将检查改为解码实际请求后逐字比较正文，并修复离线检查器对“相邻 user 消息合并为多个 JSON”的读取方式。针对性检查通过 53 项，再补充恢复及检查器负例，完整回归通过 288 项。所有失败日志均未覆盖。

四份此前完成的真实轨迹也通过了只读检查：共 18 份策略请求、20 项工具回执、18 次历史调用配对检查、4 次正文交付检查，均未发现缺失。这是旧轨迹在当前回放代码下的兼容性证据，不是当前补丁重新调用模型的实验。

最新真实 rollout 的生产版本仍是 `4a889fe467574f63464bcda6f1be93e7056566ea`，请求模型 Lanz-Medium，21 份在线响应返回 `DeepSeek-V4-Flash-0731`。它们包含一份合成流程和同一道开发题的 B/E-off/E-soft，详见[真实多工具验收](NATIVE_TOOL_TURN_ACCEPTANCE_20260910.md)。本阶段没有强迫远程模型重新生成已知错误分支，也没有把合成恢复轨迹计入准确率。

## 费用与研究状态

本阶段没有新远程调用。全局账本仍为 **1,089 次请求**；总上限 1,403，当前检查点 1,137，检查点内剩余 48 次。四笔历史未知用量继续占用预算。只读用量核查验证了 1,085 份已结算回执和 250 份导出，没有用量不一致或缺失导出；一份历史计数探针使用独立记录，不在 episode ledger 内。

CPU 全语料检索索引、模型路由、提示、采样、三臂能力、开发样本和判分口径均未更改。本阶段没有再次运行 BC+，也没有读取确认集。最终研究版本尚未冻结，确认集仍为 0/54。

两项已知程序缺陷已解除。扩展实验仍需单独登记能落在剩余预算内的范围；现有暂停标记保留，以避免恢复脚本自动启动旧批次。现有证据只有单题的同模型三臂结果：E-off 的模型请求和 token 多于 B；E-soft 的模型成本与耗时也多于 B。准确率、实际调用成本和正确完成速度三项目标仍未达到验收条件。

下一步最有价值的线上工作是固定版本、固定开发题和对照预算后的有限比较。当前补丁的两条异常路径已经能确定性离线检验，重复远程请求来等待模型碰巧触发它们不会增加相应机制验证的确定性。

## 记录与复现

私有记录目录为 `runs/strong_api_esr/20260909T085343Z/`，原始数据不进入本地代码提交：

- 修复前：`native_transition_edges_20260910.json`，对应历史[链路复核](NATIVE_CHAIN_REVIEW_20260910.md)。
- 修复后：`native_transition_edges_release_20260910.json`，记录生产提交 SHA 和干净源码状态。
- 测试：`tests_native_transitions_red_20260910T133404664.txt`、`tests_native_transitions_green_20260910T133529961.txt`、`tests_native_transitions_checked_20260910T133700516.txt`、`tests_native_transitions_full_20260910T133837446.txt`；提交后的最终日志由私有 `NATIVE_TRANSITION_FIX_CHECKPOINT_20260910.json` 定位。
- 旧真实轨迹只读检查：`native_transition_delivery_replay_20260910.json`。
- 用量核查：`receipt_audit_20260910T053958421431Z.json`。
- 当前状态：`LATEST_STATUS.json`；旧状态及暂停标记均带新时间戳归档。

在仓库根目录执行：

```powershell
python -B -X utf8 scripts/reproduce_native_transition_edges.py --expect fixed

$testStamp = Get-Date -Format yyyyMMddTHHmmssfff
$testRoot = "runs/strong_api_esr/20260909T085343Z"
$testLog = "$testRoot/tests_native_transitions_$testStamp.txt"
python -B -X utf8 -m pytest -q --basetemp "$testRoot/analysis-temp-transitions-$testStamp" *> $testLog
$testExit = $LASTEXITCODE
Get-Content -LiteralPath $testLog -Tail 8
Write-Output "pytest_exit=$testExit log=$testLog"

python -B -X utf8 scripts/audit_strong_api_receipts.py
```

诊断脚本当前默认断言修复后行为。历史 `ac82036` 中的脚本及当时生成的 JSON 保留原缺陷复现，不将旧报告改成通过记录。以上命令均不调用远程模型。
