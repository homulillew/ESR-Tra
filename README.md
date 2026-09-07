# ESR-GRPO-Code-L

ESR-GRPO 项目（短板 A / 短板 B 归因、harness 门禁、verifier 可靠性迭代）的**规整快照**。
本目录把「正在调试/运行的代码 + 轨迹数据 + 分析文档/脚本」从散落在 `/data1/ESR-GRPO/`、`/data1/ESR-GRPO-Code/`
两处的内容，按用途集中到一处，便于回溯与迁移。

> 说明：这是**复制**产生的快照，原目录保留。修改本目录不影响原运行环境；
> 反之，继续跑实验应修改原目录（`/data1/ESR-GRPO/ESR-GRPO/src/esr_grpo/`），本快照仅供归档/审阅。
> 若你的入口脚本从本目录 import，请注意保留 `PYTHONPATH` 指向真正的源码。

---

## 目录结构

```
ESR-GRPO-Code-L/
├── README.md                # 本索引
├── src/
│   └── esr_grpo/            # ESR 业务库（environment.py/store.py/verification.py/retrieval.py/rollout.py 等，19 个 .py + integrations）
├── tests/                   # 单元测试（test_environment 14 个 + browsecomp/credit/diagnostics/echo/model_download）
├── analysis-L/              # 分析工作区：harness 门禁验证、短板归因、驱动/重放脚本、分析 markdown + 结果 json
│   ├── HARNESS_IMPLEMENTATION.md
│   ├── HARNESS_WORK_CHECKLIST.md
│   ├── ITERATION_LOG.md          # 迭代日志（含「七、短板 A 强策略深挖」「八、多轮少样本实验」）
│   ├── drive_harness.py          # 强策略驱动脚本（stdin JSON 命令）
│   ├── replay_shortboardA.py(+result)   # 短板 A 离线重放
│   ├── verify_chunk_harness_gates.py    # 全景门禁回归 17/17
│   ├── strongA_12_result.json    # 强策略 12 条（单轮）驱动结果
│   ├── multiA_drive.py(+result)  # 少样本多轮实验驱动（补约束证据后是否放行）→ 4/4 仍卡死
│   ├── me_verifier_harness.py    # 【决定性】我(Claude)当 verifier + 真实 harness 分离实验(q324 pilot)
│   ├── me_verifier_batch.py(+mev_12_result.json)  # 12条扩测:12/12 提交→harness完美,短板A=4B verifier
│   ├── constraint_coverage.py    # 约束链覆盖率量化（对强策略 vs 4B evidence）
│   └── drive_120/ 186/ 324/      # 逐条驱动产物
├── results/
│   ├── exp1/                # 实验1 全部轨迹/报告/log（1088 文件，含 exp100_merged_esr/stores/*.sqlite 轨迹账本）
│   ├── strongA_runs/        # 强策略完整 ESR 轨迹 12 条（sqlite 账本 + README 判定表，2026-09-03 重跑可复现）
│   ├── multiA_runs/         # 少样本多轮 4 条轨迹账本（q324/186/364/636，2026-09-03）
│   ├── mev_pilot/           # 我当 verifier 分离实验 pilot（q324 提交成功 + README）
│   ├── mev_12/             # 12条扩测(12/12提交)轨迹账本 + README【短板A终极归因】
│   ├── exp1_small/         # 实验1 小规模对比轨迹（esr/baseline × 785/787/790/847，stores sqlite + runs.json + metrics，2026-09-04 补录）
│   └── experiments/        # 早期 smoke 轨迹（exp1_esr_smoke*/stores 785/787/790/781 + runs/trajectory/log + policy 日志，2026-09-04 补录）
├── docs/                    # 顶层设计/分析文档
│   ├── bad_case分析与ESR-GRPO方案.md     # 原始设计思想（原 bad_caseхИЖ...md 的正确名副本）
│   ├── ESR-GRPO_V1_Design.md
│   ├── IMPLEMENTATION_ANALYSIS.md
│   └── Codex_ESR-GRPO_Implementation_Prompt.md
```

---

## 关键组件（src/esr_grpo）

| 文件 | 职责 |
| --- | --- |
| `environment.py` | 状态机、工具、门禁、chunk 观察视图、方案 E'、确定性 guidance |
| `models.py` | 不可变数据协议 + enum（Evidence/TaskState/ActionRecord） |
| `store.py` | SQLite 追加式事件账本 + 不可变触发器 |
| `verification.py` | Verifier 协议 + KeywordVerifier + OpenAICompatibleVerifier(4B) |
| `retrieval.py` | Retriever 协议 + InMemoryRetriever + EchoRetrievalClient(+get_doc_chunks) |
| `rollout.py` | OpenAIChatPolicy + AgentRunner（外层推进/打捞/Budget/Baseline） |

## 运行前提（沿用原环境）

- 源码真正的运行位置：`/data1/ESR-GRPO/ESR-GRPO/src/esr_grpo/`（本 `src/` 是其副本）
- venv：`/data1/ESR-GRPO/ESR-GRPO/exper/arex_bcplus_native/.venv/bin/python`
- 依赖服务：检索 `EchoRetrievalClient`(:8000)、4B verifier(:8005/:8006 均 Qwen3.5-4B)
- 驱动脚本需 `PYTHONPATH=/data1/ESR-GRPO/ESR-GRPO/src`；前台 `&` 会被回收(exit 144)，用后台任务租户跑

## 最近状态（2026-09-03）

**短板 A 归因——终极定论：harness 完美（12/12 可提交），卡死 100% 在 4B verifier**
- 强策略单轮 12 条：12/12 needs_revision→blocked、0 提交（检索缺口+verifier语义误判+unparseable 三层叠加）。
- 少样本多轮（q324/186/364/636，补约束证据）：4/4 仍卡死 → 根因不是检索不足。
- **分离实验（决定性，12 条全测）**：我(Claude) 当 verifier + 真实 harness（`analysis-L/me_verifier_batch.py`），
  **12/12 全部 submitted**（186/56/1041/1089/1198/324/364/391/517/636/772/83）。
  其中 636/772 我判 needs_revision 的真 case 都因 evidence 另缺关键片段，补证后 supported。门禁无 bug。
  → **harness 门禁+chunk视图+方案E' 全部实现正确、无需再改。短板 A 100% 归因 4B verifier**
  （multi-hop逻辑误判、unparseable、实体身份过严、字面约束过苛）；检索召回广度是独立的第二短板。
- 详见 `analysis-L/ITERATION_LOG.md` 七/八/九/十。