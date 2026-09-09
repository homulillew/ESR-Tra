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

确认集问题文件已经锁定；最终冻结之前禁止运行/展示其详细内容。还未产生新题开发集或确认集效果结论。任务未结束时本文件只作为恢复入口，不代表后续阶段已完成。


2026-09-09 pilot 的 30 次额度全部执行完并完成独立判分，禁止再跑 pilot。两次强制中断已记为 operator_paused，未知请求仍占用预算。正文重复、搜索结果提交容量检查、JSON 尾标记问题均已保存原始失败并修复。开发集已冻结为 9 题，全为暂列中等，未完成可靠的三档平衡校准。确认集仍封存。当前准备运行 development --replicate 0 --take 9 --arms B E-off E-soft；候选选择规则在私有 candidate_selection_preregistered.json，按第一遍结果选择 E-off 或 E-soft 后，再运行 B 与候选的 replicate 1。

freeze_development.py 只读 baseline pilot，按预登记规则冻结开发题。compare_strong_api.py 要求完整、同源的显式配对队列，按题目聚类 bootstrap。freeze_final_strong_api.py 只接受 9 题、B 与候选各 2 次的开发比较；确认批次会核对冻结的源码、配置、样本和 judge 模板。实际确认尚未执行，不能把脚本存在写成已得到结果。

需要暂停未来批次时，在研究根目录创建 PAUSE_NEW_EPISODES.json，执行器会在当前局结束后停止。保留暂停文件并重命名归档后才能继续。无显卡部署说明见 CPU_RUNBOOK.md。
