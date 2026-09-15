# 参数校验错误的基底复现

本实验只检查一个问题：在接受和拒绝条件保持不变时，把既有校验错误定位到字段与类型，能否为模型自行修复提供更准确的信息。本轮为 OFFLINE_ONLY，真实模型、付费 judge、生产索引查询和既有全局额度消耗均为 0。

资料提交固定为 `749c505110741d828c7f54fdfb865c37b19627b3`，自然运行核心 release 固定为 `5d7752be94a9d40aa757383d8899504bc0f81e81`。独立分支从前者建立，未以 main 或附件中的代码替换被测实现。修改前逐一比较 q778 manifest 的 14 个核心 SHA-256、release Git blob 和新 worktree 文件，全部一致；公开包的 3,015 个清单条目通过哈希核验。

公开 SQLite 的 head 为 `1bb75f4b1e55f681d290240a7646808f5362a40d9e89fae16cdfc9e7cd480aba`，与资料中的公开 head 映射一致。`trajectory.jsonl` 比 SQLite 事件多一个派生的 UTC 注释；排除该注释后，每个原始事件字段完全相等。第一次检查错误地把该注释也用于字典相等比较而产生 AssertionError，尚未进入 validate 复现或基底测试；这项检查脚本错误和处置记录保留在 [首次检查记录](report/INITIAL_CHECK_FAILURE.json)。没有发现原始轨迹行为与任务描述不同。

## 原 validate 的复现结果

原始错误树保存在新的本地输出目录，公开 [错误树结构](report/BASELINE_ERROR_STRUCTURE.json) 保留 validator、相对/绝对路径、schema 路径和 context 子树，去除可能回显实例值的叶子 message。公开记录也保存原始错误树文件的 SHA-256。此处 schema-only 字符串比较只是独立校验案例，没有执行 finish 或修改原始工具参数。

| 输入形状 | 原 schema 结果 | 顶层错误 | 真实子错误 |
| --- | --- | --- | --- |
| finish.answer 为 JSON 数字 | 拒绝 | oneOf，根路径 `[]` | `/answer`，type 要求 string |
| finish.answer 为合法字符串，refs 形状合法 | schema 接受 | 无 | 执行层仍需校验交付来源等条件 |
| refs 为字符串 | 拒绝 | oneOf，根路径 `[]` | `/refs`，type 要求 array |
| answer 仅含空白 | 拒绝 | oneOf，根路径 `[]` | `/answer`，pattern 不满足 |
| 同时有 answer/refs 和 abstain/reason | 拒绝 | oneOf，根路径 `[]` | 两个分支分别违反 additionalProperties |
| search.queries 为字符串 | 拒绝 | type | `/queries`，要求 array |

原错误消息为 `finish: invalid fields near []; follow the supplied schema`。jsonschema 的 `ValidationError.context` 已经提供字段级的 type 错误，信息在原格式化过程中丢失。准确行号见 [代码位置表](report/CODE_LOCATIONS.json)，该表同时列出 release 与当前实现，避免用改动后的行号冒充原代码位置。

## 实际触发链路

1. `contract.loads()` 使用原始严格 JSON 解析器；重复 key、NaN/Infinity、不可解析文本在此拒绝。
2. `engine.Harness._step()` 先占动作槽，再执行 `loads(arguments)` 和 `validate(name, args)`。schema 失败发生在 `_dispatch` 之前，故工具未执行，但动作槽已占用。
3. `_step()` 捕获 `ContractError`，生成 `arguments_invalid`、`blocks_finish=true` 和最长 500 字符的 message；将它复制到 `control.feedback` 并增加 `no_automatic_parameter_repair=true`。随后工具 result 加入 `executed=false`、`action_slot_charged=true`。
4. `recovery.make_group()` 保留原生调用 ID，把 result 编码为工具回执。`context.build()` 将完整结果组和控制状态放入下一请求。q778 R4 的 action_execution/action_result 分别在事件 76/78，R5 的 model_request 在事件 80。R5 实际 HTTP 正文中的两处 message 相同。

注意：旧实现先复制 feedback，再向工具 result 加 executed/action_slot_charged。因此不能假设 feedback 和 result 的全部字段集合相同。本实验只要求对应 message 相同，保持原有字段及其缺省状态。

`repair_context=true` 并不表示这次参数错误触发了修复视图。`remember_response()` 在非致命响应解析失败或没有显式工具动作时调用；参数 validate 失败走工具异常回执路径，没有调用它。R5 中 `uncommitted_response_not_evidence` 为 null，与该代码路径一致。模型已经看见原文和错误回执，本次排查不把问题归因于证据丢失。

## 续程能恢复什么

隔离入口从空的新 Harness 开始，用实际 R1–R4 响应和与每个历史请求精确配对的后端返回，重新执行原引擎步骤。它不读取最终 SQL 表来装配状态，不查询生产索引，也不给重放模型历史后缀。R5 原始请求仅在重建结束后作为比较对象。

A 臂 R1–R4 请求及 R5 请求的原 serializer 字节均一致；79 个前缀事件的所有非耗时 payload 一致。恢复了完整历史组、交付集合、文档/证据编号、查询缓存、导航状态、计数、usage、phase 和输出余额。剩余模型调用 60、动作 196、后端 113、输出额度 47,648，phase 为 RESEARCH，原 Config 的 64 次上限没有改变。

**精确时间余额无法恢复。** 原采集器在 archive append 完成后记录 UTC，初始化时的 `Harness.started=time.monotonic()` 和 R4 结束时的对应差值未持久化。UTC 事件间隔为 18.538888 秒，既不包含同样的初始化区间，也不是同一种时钟；各次 HTTP/后端 latency 的和还会遗漏引擎处理时间。离线重放用零时钟生成请求，明确不将其用于真实时间预算。

因此 [前缀检查](report/PREFIX_REPLAY_CHECK.json) 的总体状态是 **BLOCKED_PREFIX_RECONSTRUCTION**，即使离散状态和 R5 输入已经精确通过。不得把 UTC 近似值、最终 R64 耗时或文件复制耗时替代原前缀时间余额。只批准 16 次调用也不会自动解除这个数据缺失问题。
