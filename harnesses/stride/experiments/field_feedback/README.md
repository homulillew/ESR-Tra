# 字段级校验反馈：离线实验准备

本轮模式为 **OFFLINE_ONLY**。唯一产品改动是一个有界的 ValidationError 消息格式化函数，以及默认保留旧消息的实验开关。真实模型调用和既有额度消耗均为 **0**。原始 12 题正式得分 6/12、q778 的 model_budget/空答案和已发布 artifacts 保持原样。

先读 [基底复现](BASELINE_REPRO.md)、[验证结果](VALIDATION.md)、[前缀检查](report/PREFIX_REPLAY_CHECK.json)、[A/B 请求差分](report/REQUEST_DIFF_A_B.json) 和 [冻结计划](report/EXPERIMENT_PLAN.json)。

## 实现与实验开关

`Harness(..., validation_feedback="legacy")` 为默认行为。独立实验入口可以显式使用 `validation_feedback="field"`；直接调用校验器时对应参数为 `validate(name, args, feedback="field")`。开关不进入 Config 或模型请求，没有新增系统指令、工具描述或供应商参数。

完整 [产品 diff](report/PRODUCT_DIFF.patch) 仅包含消息选择入口与纯格式化模块；[代码位置表](report/CODE_LOCATIONS.json) 标出原 release 和本实验的对应位置。

格式化器从真实 `ValidationError` 提取 JSON Pointer（JSON 文档中的字段路径）、校验规则、预期类型/约束和实际类型。分支判断使用既有 schema 的类型、属性集合和 const/enum 判别字段；不能唯一定位时报告分支冲突或有限备选，不按错误数量猜测回答/弃答意图。消息最多 420 字符、3 条诊断，路径最多 64 字符；过长路径报告明确标记的祖先指针，避免生成不合法的截断转义。引擎现有截断上限为 500 字符。

解析器、schema、动作接受集合、成功回执、FINAL、温度、tool_choice、shelf/notes/recall、检索与查询规则均未改动。没有数字到字符串的自动转换，也没有代 policy 调用 finish。SCRIPTED 合成往返只能证明“错误回执送达后，脚本提供下一条合法动作可提交”，不能说明真实模型已经修复。

## 离线命令

从仓库根目录运行，使用已安装 `pytest` 和 `jsonschema` 的 Python。`PYTHONPATH` 必须指向当前 worktree，避免加载其他 worktree 的 editable 安装。为本地 HTTP 合成测试显式绕过代理；这些设置只作用于当前 PowerShell 进程。

```powershell
$env:PYTHONPATH = (Resolve-Path 'harnesses/stride/src').Path
$env:NO_PROXY = 'localhost,127.0.0.1,::1'
$env:HTTP_PROXY = ''
$env:HTTPS_PROXY = ''
$env:ALL_PROXY = ''
$env:ESR_API_KEY = ''
$env:ESR_BASE_URL = ''
python -m pytest harnesses/stride/tests harnesses/stride/examples -q --basetemp runs/field-feedback-new-test
python harnesses/stride/experiments/field_feedback/prepare.py --artifacts harnesses/stride/artifacts/20260914-hard12-a3 --private-output runs/field-feedback-new-private --report-output runs/field-feedback-new-report
```

所有输出目录必须是新目录。prepare 不发送请求，不读取密钥、不打开全局预算库，也不查询生产索引。真实前缀的 SQLite 状态和 A/B 准备请求留在 private-output；公开 report-output 只有哈希、诊断、差分与计划，不重复发布原题、正文或原始 HTTP。

若要再次复现未修改的基底，请从精确资料提交另外建立干净 checkout，把 `PYTHONPATH` 和 `reproduce.py --repo` 都指向它。该脚本有 14 文件身份门禁，在已经改过 contract/engine 的实验 worktree 中不会冒充原基底。原始错误树仅写入指定的新本地目录。

## 待另行批准的续程

冻结顺序为 A1 → B1 → B2 → A2，每条最多 4 次新模型尝试，总上限 16，成功即止。四条独立续程从同一个 R4 前缀开始。这个外层观察上限不改变原 Config、不进入模型控制状态，也不提前触发 FINAL。达到局部上限只记 `local_continuation_cap`，不得伪造 model_budget 或自动弃答。

**当前全部槽位为 LIVE_NOT_RUN，发送入口被阻塞。** 离散状态和 A/B 首请求检查通过，但缺少原前缀精确单调时钟耗时。本提交提供只读门禁入口，没有发布能够发送真实请求的执行器。

下面命令只检查门禁，当前返回 LIVE_NOT_RUN：

```powershell
python harnesses/stride/experiments/field_feedback/pilot_gate.py --plan harnesses/stride/experiments/field_feedback/report/EXPERIMENT_PLAN.json
```

下面是后续审批入口的形式，**当前执行会报 BLOCKED_PREFIX_RECONSTRUCTION 并退出，不会发送任何请求**。命令行开关不构成用户授权，也不能解除时间余额缺失。

```powershell
python harnesses/stride/experiments/field_feedback/pilot_gate.py --plan harnesses/stride/experiments/field_feedback/report/EXPERIMENT_PLAN.json --execute-approved-pilot
```

只有先解决该精确重建问题、审阅真正的续程执行器并获得单独授权，才可开展计划。真实发送前还须核对原私有 manifest 的哈希与部署身份、生产索引、既有全局账本当前余额，并在每次发送前原子占账。449 只是历史记录；本轮未读取或预占余额。完整停止条件、局部/全局预算与时间语义列在 EXPERIMENT_PLAN 中，当前这些真实发送门禁仅被登记为要求，不宣称已经在生产条件下验证。

没有新 judge 就不生成新官方标签。后续应分别评价结构修正、正式答案信息保持和来源有效性。当前实验到离线准备与阻塞报告为止，不自动进入其他优化。
