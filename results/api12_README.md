# api 驱动强策略标准评测 12 条（ESR vs baseline）—— 干净重跑

> 日期：2026-09-04
> 方法：全自动 api（`Lanz-Medium` = 强策略模型）驱动，**每条样本独立全新 session**，无人工回填、无 gold 泄露、无跨样本/跨方法污染。
> 数据：`results/api12/raw_results.jsonl`（24 行）、`results/api12/stores/*.sqlite`（24 个轨迹）、`results/api12/eval_report.md`、`eval_summary.json`。
> 驱动/编排/评测脚本：`analysis-L/api_policy_drive.py`、`run_api_12.py`、`evaluate_api12.py`。

---

## 为什么要重跑

上一版 `strong12`（`results/strong12`）由**我（Claude，单一持续上下文）**逐局文件回填出牌，24 局共享同一上下文 → **方法间（ESR→baseline）+ 样本间（12 条共享 session）双向污染**。尤其 baseline 的 search query 常直接带答案名（如 `'Bada Lee ...'`、`'Peter King ...'`），非纯线索检索 → "ESR 不提升准确率"即便方向稳健，绝对数字不可作严格量化。

本次改用 **api 全自动** 执行同一批 12 条、同一 `ESREnvironment`（真 BM25）、同一评测（离线 `ExactMatchJudge`），但**每个 (qid, mode) 独立全新 LanzClient session + 独立子进程** → 彻底隔离上下文。

## 工具面（用户裁定）

- **ESR**：6 工具 `search/open_page/read_evidence/update_state/verify_answer/submit_answer`（verify 判定由同一 api session 产出）。
- **baseline（BC+ 基础工具）**：**3 工具 `search/open_page/finish`** —— 用户裁定**删掉 `read_evidence`**。已核实：baseline 无 `update_state`/TaskState，`read_evidence` 因门禁（`current_state` 必须非 None 且 id 须在 evidence_directory）**必然 100% 被拒**，是"死工具"，列为 allowed_actions 会误导模型空转浪费轮次。

## 结果（12×2，全部独立 session）

| 指标 | ESR | baseline | 说明 |
|------|-----|----------|------|
| 提交率 | **92%** (11/12) | **100%** (12/12) | ESR 636 未提交（max_turns） |
| Accuracy（仅已提交） | **100%** (11/11) | 83% (10/12) | ESR 提交者全对 |
| **Accuracy（含未提交）** | **92%** (11/12) | **83%** (10/12) | ESR 净高 **+9pp** |
| 平均工具调用轮数 | **15.2** | 6.2 | ESR ≈ **2.45×** |
| 平均 search / open | 4.0 / 2.9 | 3.2 / 2.1 | ESR 多 |
| 平均 update_state / verify | 5.0 / 2.2 | 0 / 0 | 门禁开销 |

## 逐条判定（ESR vs baseline）

| qid | ESR | baseline | 差异 |
|-----|-----|----------|------|
| 186 | ✓ | ✓ | 平 |
| 56 | ✓ | ✓ | 平 |
| 1041 | ✓ `Adaku` | ✓ `Adaku` | **双对**（污染版两臂都答 `Bonang Matheba` ✗；干净版修好）|
| 1089 | ✓ | ✓ | 平 |
| 1198 | ✓ | ✓ | 平 |
| 324 | ✓ | ✓ | 平 |
| 364 | ✓ (30轮) | ✓ (19轮) | 平，ESR 慢 |
| 391 | ✓ | ✓ | 平 |
| **517** | ✓ `Peter King Nzioki` (42轮) | ✗ `Peter Sarsgaard` | **ESR 救回** |
| 636 | ✗ 未提交(max_turns) | ✗ `2020` | 都错，ESR 未收敛 |
| **772** | ✓ `秘书（secretary）` | ✓ 长句含 secretary | 平 |
| 83 | ✓ | ✓ | 平 |

## 关键结论

### 1. 干净重跑改变结论：ESR **净提升准确率 +9pp**（不再是污染版的"平手"）
- **Accuracy(含未提交) 92% vs 83%**，且 `Accuracy(仅已提交) 100% vs 83%`（ESR 提交者 11/11 全对）。
- 与 `strong12`（污染版 92% vs 92%）**相反**。原因清晰：污染版里我已知答案，baseline 的 search query 被"喂"了正确路径（`'Peter King ...'`、`'Sarsgaard'` 是错的但污染版可能从我的上下文拿到正确线索），baseline 被拔高；干净版 baseline 无此提示 → 自然退化：517 答 `Peter Sarsgaard`、636 答 `2020`。
- **ESR 的 verify 门禁在干净版里是稳定器**：517 靠多轮 update+verify（7 次 verify）收敛到含 `Peter King` 的答案；baseline 一次 search 就 `finish` 出错。

### 2. 1041 被干净重跑修好（污染版误答的关键坏例）
污染版两臂都答 `Bonang Matheba`（把主题人物名当采访者名），新判断它是"主题人物 vs 采访者"的真实归因失误。**干净版两臂都答 `Adaku`（gold）** —— 因为干净 session 不受我先前的"Bonang"误导。这直接证明此前 1041/两臂的错是 **上下文污染（我先入为主的误导）**,不是模型能力或数据问题。

### 3. 轮数差距稳健：ESR ≈ 2.45× baseline（15.2 vs 6.2）
与污染版（ESR 8.2 vs baseline 3.3 ≈ 2.5×）**几乎相同倍数**。这是"ESR 门禁天然多花轮"的稳定信号：baseline 3 工具 max_turns=6 内 finish，ESR 必须 update_state+verify_answer(submit 门禁) 才能过。

### 4. 成本换质量：ESR 用 2.45× 轮数换取 100% 提交精度
- ESR 未提交的唯一一条 636（max_turns 30 没收敛），baseline 提交但错（`2020`）。都是错，但 ESR 更"谨慎"（宁可交不出不交错的）——这符合 ESR 的持证回答语义。
- **trade-off**：ESR 把"低置信正确/高置信错误"都挡在门外（提交精度 100%），代价是可能该答而答不出（636）+ 多费轮数。

### 5. 隐性 caveat（诚实性）
- **517_esr = `Peter King Nzioki`** 靠 gold=`Peter King` 的 **substring** 命中判对，非 ground-truth 完全一致，多了 `Nzioki`。这是一条**宽松 ExactMatch 命中**，非严格实体相等。若按严格相等算，517_esr 应算 **错**，则 ESR Accuracy(含未提交) 会掉到 **83%（10/12）**，与 baseline **平手**。→ **结论对"宽松 vs 严格判分"敏感**，必须明示。
- 636 的 gold=`2011` 本身在 32B verifier 归因时已被标注"时间线相悖，答案标签存疑"（见 EXPERIMENTS_REPORT 第 10 章）；本重跑两臂都答别的年份，未能复现，符合存疑预期。
- 772 baseline 是**长句答案**（非简洁 entity），靠内含 `secretary` 判对，本就不是理想提交，但与 ESR 一致判对。

## 与既有归因链的关系
- **不推翻** 第 9/10 章"短板 A = 4B verifier 能力 / 检索召回"：那是本地 4B verifier + 真实环境下的归因。本实验把**策略与 verifier 都换成强模型 api**（与 strong12 一致），回答的是"**harness 作为流程本身，在强策略下有无净增益**"这个问题。
- 净结论：**强策略 + 干净隔离下，ESR harness 能提升提交精度（100% vs 83%）并净提升准确率（+9pp 宽松判分），但成本是 ~2.45× 工具轮数**。基线 3 工具最省轮但易草率出错。

## 可复现
- 运行：`PYTHONPATH=src python analysis-L/run_api_12.py --dataset <jsonl> --workers 4 --max-turns 50`（每 (qid, mode) 独立子进程 + 全新 session；api 请求内部指数退避重试；子进程整体可重跑）。
- 评测：`PYTHONPATH=src python analysis-L/evaluate_api12.py --dataset <jsonl> --root results/api12`。
- 单条调试：`api_policy_drive.py --dataset <jsonl> --query-id <qid> --mode <esr|baseline> --store <path>`。
- 关键设计点（防污染）：每条 1 个 LanzClient 只服务 1 个 (qid, mode)；gold 仅评测期进判别，运行期策略/verifier 都不见 gold。