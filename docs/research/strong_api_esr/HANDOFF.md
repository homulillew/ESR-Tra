# 强 API 研究执行入口

研究目录由 `runs/strong_api_esr/CURRENT` 指向。密钥通过 ANTHROPIC_AUTH_TOKEN 环境变量或 getpass 无回显读取，勿写命令行、源码或报告。用户已授权真实调用，无需重新索要权限。

CPU 索引已建立在 `D:/AgentSearchAssets/BrowseComp-Plus/indexes/esr-sqlite-bm25-20260909.sqlite`。现有默认 Python 可以运行检索；建索引使用已有的 `D:/AgentSearchAssets/.venv-download/Scripts/python.exe`（含 pyarrow）。重建须指定新路径，禁止覆盖旧索引。

```powershell
python -B -m pytest -q --basetemp runs/strong_api_esr/test-temp-NEW
python -B -u scripts/strong_api.py probe --native
python -B -u scripts/strong_api.py fixture
$researchRoot = (Get-Content runs/strong_api_esr/CURRENT -Raw).Trim()
python -B -u scripts/strong_api.py run --questions "$researchRoot/dataset_splits/known-regression.questions.jsonl" --qid 120 --arms B E-off E-soft
```

每局使用唯一时间 ID；完整 SQLite 和 JSONL 保留实际 provider 请求与原始响应。global_budget.sqlite 包含所有本轮实际模型请求的预留/结算和 episode 注册。中断后先检查是否有正在运行的进程、未结算请求及无终态的 episode，不直接重新运行相同问题。恢复时未知用量仍占预算。当前脚本不会自动接续未完成的 episode。

官方 grader 模板已保存至研究目录 evaluation_protocol，并记录来源和哈希。评价使用独立进程 `scripts/evaluate_strong_api.py --run-dirs <已结束运行目录名>`，只评价指定运行。相同模型路由充当 judge 的相关误差必须保留为限制。

确认集问题文件已经锁定；最终冻结之前禁止运行/展示其详细内容。开发集已锁定，已有部分真实开发结果，但尚无完整冻结对照或确认集结论。任务未结束时本文件只作为恢复入口，不代表后续阶段已完成。


2026-09-09 pilot 的 30 次额度全部执行完并完成独立判分，禁止再跑 pilot。两次强制中断已记为 operator_paused，未知请求仍占用预算。正文重复、搜索结果提交容量检查、JSON 尾标记问题均已保存原始失败并修复。开发集已冻结为 9 题，全为暂列中等，未完成可靠的三档平衡校准。确认集仍封存。当前准备运行 development --replicate 0 --take 9 --arms B E-off E-soft；候选选择规则在私有 candidate_selection_preregistered.json，按第一遍结果选择 E-off 或 E-soft 后，再运行 B 与候选的 replicate 1。

freeze_development.py 只读 baseline pilot，按预登记规则冻结开发题。compare_strong_api.py 要求完整、同源的显式配对队列，按题目聚类 bootstrap。freeze_final_strong_api.py 只接受 9 题、B 与候选各 2 次的开发比较；确认批次会核对冻结的源码、配置、样本和 judge 模板。实际确认尚未执行，不能把脚本存在写成已得到结果。

需要暂停未来批次时，在研究根目录创建 PAUSE_NEW_EPISODES.json，执行器会在当前局结束后停止。保留暂停文件并重命名归档后才能继续。无显卡部署说明见 CPU_RUNBOOK.md。

2026-09-09 当前恢复点：原生 policy 工具与 audit_report；共享提示 research-2.1.5。DEVELOPMENT_FREEZE_v4.json 保存当前源码和配置。tests-19.txt 为 214 项通过。旧三个开发版本分别执行 3、8、2 局后停止，全部完成独立判分；这些队列不与当前版本混算。文本接口在完整 E-off 轨迹中 31 个动作有 18 个非法，故拒绝，详情见 DECISIONS.md。另有 8 次固定前缀诊断和 4 次联通/容量探针，均保留原始记录与费用。不得继续增加接口探针或轮换格式以挑选成功输出。

当前执行固定 9 题、B/E-off/E-soft 的 replicate 0。恢复前先查当前进程和实际已完成目录；同一源码版本的已注册 replicate 禁止重复。全部结束后用独立 evaluator 判分，再按既定规则选择 ESR 候选，运行 B 与候选的 replicate 1，做完整配对比较后才能冻结确认集。

```powershell
python -B -X utf8 scripts/audit_strong_api_receipts.py
python -B -X utf8 scripts/evaluate_strong_api.py --run-dirs <已结束运行目录名>
python -B -X utf8 scripts/compare_strong_api.py development --esr E-off --replicates 1 --reference-run <当前版本B目录名>
```

记账核对脚本验证全局预留/结算、SQLite 原始响应与 JSONL 导出是否一致。运行中缺少导出不等于丢失：当前局结束后才导出。计数接口的单独探针使用 request.json/response.json，不在 episode ledger 中；它的未知用量仍占预算。最终交付前应在无在途请求时再核对一次。
