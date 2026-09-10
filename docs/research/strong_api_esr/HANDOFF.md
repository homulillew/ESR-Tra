# 强 API 研究恢复入口（更新至 2026-09-10）

最新模型切换：用户随后指定 `Lanz-Medium`，配置已切换。一次原生工具测试返回 HTTP 200，响应模型标识 `DeepSeek-V4-Flash-0731`，合法 finish(API_OK)，输入 915、输出 45 token，耗时 3.57 秒，记录在 `probe_20260910T021146025933Z/model_switch_check.json`。该返回标识不等于已固定权重版本；尚无 Lanz-Medium 的完整 BC+ rollout 或审核测试，不能推定多工具问题已解决。234 项回归通过，日志 `tests-20260910-04.txt`。

本日继续实验已在 EB-GLM-5.2 上执行固定首题三臂：B、E-off 判对，E-soft 因 6 次多工具拒绝而未提交，总计 29 次在线请求和 2 次 judge。状态与费用在 `checkpoint_20260910_first_question.json`，批次暂停标记仍保留。请求总上限 1,403、当前检查点 1,105，现已使用 1,035；额度没有因切换模型而重置。新模型须建立独立同模型对照，不能拼接旧模型结果。联通和 judge 的请求模型字段现已跟随配置，旧模型运行禁止被新路由静默判分。

以下记录保留 2026-09-10 早些时候的恢复过程；当前模型和暂停状态以上述说明及私有 `LATEST_STATUS.json` 为准。

当前状态：2026-09-10 用户报告配额恢复并要求测试。一次真实原生工具联通请求返回 HTTP 200、模型标识 glm-5.2、合法 finish(API_OK)，耗时 3.85 秒，输入 757、输出 10 token。昨日 `PROVIDER_BLOCKED.json` 已带时间归档；`PAUSE_NEW_EPISODES.json` 保留，开发批跑尚未恢复。研究根目录由 `runs/strong_api_esr/CURRENT` 指向，最新状态见私有 `LATEST_STATUS.json`。此次成功只证明该次调用可用，不能保证剩余配额或整批可靠性。

最新功能修复为 `6d3684b`，比较保护为 `dc1a3a9`，223 项回归通过（`tests-22.txt`）。动态 ID schema 别名污染已修复；原始 1,001 份导出请求中 442 份受影响，18 局开发运行全部带警告。修复后的版本没有真实 rollout，原文片段审核也尚未实网验证。最终候选未选择，确认集 0/54，禁止提前打开其问题或 gold。详细结果见 [FINAL_REPORT.md](FINAL_REPORT.md)。

## 无需配额的本地核查

在仓库根目录执行以下导出。新导出使用独立时间目录，不覆盖旧记录；schema 核查只会给尚未标记的受影响运行添加警告。

```powershell
$researchRoot = (Get-Content runs/strong_api_esr/CURRENT -Raw).Trim()
git status --short
python -B -X utf8 scripts/audit_strong_api_receipts.py
python -B -X utf8 scripts/audit_strong_api_schemas.py
python -B -X utf8 scripts/summarize_strong_api.py
```

需要验证后续代码修改时，测试使用新的临时目录并保存完整日志。不要覆盖 `tests-22.txt`：

```powershell
$testStamp = Get-Date -Format yyyyMMddTHHmmssfff
python -B -X utf8 -m pytest -q --basetemp "runs/strong_api_esr/test-temp-$testStamp" *> "$researchRoot/tests-$testStamp.txt"
$testExit = $LASTEXITCODE
Get-Content "$researchRoot/tests-$testStamp.txt" -Tail 5
Write-Output "pytest exit=$testExit"
```

CPU 索引已建好，无需下载模型或重建，运行与重建说明见 [CPU_RUNBOOK.md](CPU_RUNBOOK.md)。密钥只从 `ANTHROPIC_AUTH_TOKEN` 或 getpass 读取，不写源码、命令行参数或报告。用户已有调用授权，无需重新索要权限。

## 同一路由配额恢复后的有限执行

同一路由已于 2026-09-10 经一次真实调用验证可用，provider 阻断标记已归档。实际恢复开发队列前，核查没有在途请求和未关闭 episode，再将剩余批次暂停标记以新时间名归档，保留原内容。响应没有给出剩余配额或重置时刻；若再次收到每日限额错误，源码会重新持久阻断。一般传输错误仅按固定规则重试。

pilot 已完成 15 题各两次，跨版本 30 局上限用完。确认集和开发集原始选择不变，不再跑 pilot、不按 ESR 结果重新分层或换题。四轮主要机制预算已用完，不增加新的接口探针。旧开发版本不能接在当前版本后充当同源队列。

当前修复版本尚未注册开发 rollout；配额恢复后从固定顺序开始第一遍：

```powershell
python -B -X utf8 -u scripts/strong_api_batch.py development --replicate 0 --start 0 --take 9 --arms B E-off E-soft
```

调度器串行交错运行并保存预登记顺序，遇到系统性故障会暂停。若中途暂停，先检查真实完成目录、错误与预算；同一在线源码/题号/臂/replicate 不得重复。不能重跑直到成功，也不能跳过失败题来拼完整比较。

仅在 rollout 结束后，用独立 evaluator 对指定目录判分；已保存判分只读。当前另有 7 个 BC+ 提交未判分，清单在 `blocked_status_metrics.json`，仍计研究 judge 预算：

```powershell
python -B -X utf8 scripts/evaluate_strong_api.py --run-dirs <已结束运行目录名>
python -B -X utf8 scripts/compare_strong_api.py development --esr E-off --replicates 1 --reference-run <当前版本B目录名>
python -B -X utf8 scripts/compare_strong_api.py development --esr E-soft --replicates 1 --reference-run <当前版本B目录名>
```

尖括号是需替换的实际文件/目录参数，不能原样执行。比较要求固定 9 题、完整同源配置与判分，并拒绝 schema 警告队列。按预登记规则选择准确率较高的 ESR；同分依次比较实际后端请求、模型请求、占用输入 token，仍同分选 E-off。随后将 `<候选>` 替换为选定的 E-off 或 E-soft：

```powershell
python -B -X utf8 -u scripts/strong_api_batch.py development --replicate 1 --start 0 --take 9 --arms B <候选>
python -B -X utf8 scripts/evaluate_strong_api.py --run-dirs <第二遍已结束运行目录名>
python -B -X utf8 scripts/compare_strong_api.py development --esr <候选> --replicates 2 --reference-run <当前版本B目录名>
python -B -X utf8 scripts/freeze_final_strong_api.py --comparison <两遍开发比较JSON路径> --reason <依据固定规则的选择说明> --tests <最新通过测试日志路径>
```

只有最终冻结成功，才能运行最初封存的 9 题、B 与候选各三次确认：

```powershell
python -B -X utf8 -u scripts/strong_api_batch.py confirmation --replicate 0 --start 0 --take 9 --arms B <候选>
python -B -X utf8 -u scripts/strong_api_batch.py confirmation --replicate 1 --start 0 --take 9 --arms B <候选>
python -B -X utf8 -u scripts/strong_api_batch.py confirmation --replicate 2 --start 0 --take 9 --arms B <候选>
python -B -X utf8 scripts/evaluate_strong_api.py --run-dirs <确认运行目录名>
python -B -X utf8 scripts/compare_strong_api.py confirmation --esr <候选> --replicates 3 --reference-run <确认B目录名>
```

每一步都需要上一步完成和预算允许，不能把这组命令直接作为无条件大批执行脚本。确认结果不能用于继续调参；失败与未提交保留在完整预定分母，按题目聚类分析，不把同题三次运行当成三道独立题。

全局目前登记 67 个预算单位、1,003 个远端请求（含 2026-09-10 用户要求的恢复测试），未知的 4 笔用量仍占用预算。新增测试属于明确授权的联通核查，不是新的接口或研究机制迭代；昨日比较与费用快照保留原值。恢复测试的请求、响应与结算在 `probe_20260910T014153882384Z`，确认预留 54 局没有动用。预算、样本、索引、grader、实际请求、逐局轨迹和版本摘要均在私有研究根目录；不公开原始数据、不推送远端，不承诺会话结束后后台执行。
