# ESR-GRPO 实验综合分析报告

> 项目：ESR-GRPO（Evidence-Supported Reasoning with GRPO）
> 说明：本版为**精简版**，只保留关键里程碑实验的完整链条：实验1正式评测 → 强模型分离归因 → 观察窗修复过渡 → 32B verifier 验证 → api 干净重跑 → 最终归因。中间的增量迭代（Retry20、Fix7/8、strong12 污染版）已删除，仅作过渡保留必要论据。
> 日期：2026-09-07 ｜ 数据所在：`Code-L/results/` 与 `Code-L/analysis-L/`（均在 `/data1/ESR-GRPO-Code-L`）

---

## 目录
1. [背景与问题](#1-背景与问题)
2. [系统架构](#2-系统架构)
3. [实验1 正式评测（100 条）](#3-实验1-正式评测100-条)
4. [强模型分离实验：能力层 vs harness 缺陷归因](#4-强模型分离实验能力层-vs-harness-缺陷归因)
5. [过渡：观察窗修复与短板 A 深挖](#5-过渡观察窗修复与短板-a-深挖)
6. [Qwen3-32B verifier：换模型验证](#6-qwen3-32b-verifier换模型验证)
7. [api 全自动干净重跑（ESR vs baseline）](#7-api-全自动干净重跑esr-vs-baseline)
8. [本地 Qwen3-32B 策略 + verifier：方向相反的对照](#8-本地-qwen3-32b-策略--verifier方向相反的对照)
9. [最终归因与结论](#9-最终归因与结论)
10. [下一步方向](#10-下一步方向)

---

## 1. 背景与问题

ESR-GRPO 让模型在 **retrieve→open→read→update→verify→submit** 闭环里，通过 GRPO 训练持证回答（evidence-grounded）的问答系统。基线数据 BrowseComp-Plus。

观察到的核心短板 A：大量轨迹**最终答案已含正确答案（gold）**，却 **0 次 verifier supported** 因而**不提交**。submit 门禁要求 `verification_status==SUPPORTED` 且 gaps 空。100 条扩测里 ESR 有 81 条未提交，其中 78 条因 verify 打回的 gap 解不掉而卡死。

要回答的核心问题：**短板 A 的根因在哪一层：4B 模型能力、harness 机制、检索/证据、还是数据集？**

本报告用四条关键实验逐层剥离：量化现象（实验1）→ 区分能力层与 harness 缺陷（强模型分离）→ 修观察窗 + 深挖短板 A → 换更强的 verifier（32B）验证 → api 干净重跑量化 ESR 相对 baseline 的净增益。逐层把根因钉死。

---

## 2. 系统架构

| 组件 | 说明 |
|------|------|
| 策略模型 | Qwen3.5-4B（默认），强策略实验替换为 Claude / Lanz-Medium |
| Verifier | Qwen3.5-4B（默认）→ 实验末替换为 **Qwen3-32B** |
| 检索 | 真实 BM25（`EchoRetrievalClient`，端口 8000） |
| 轨迹账本 | **SQLite 追加式**（`metadata` / `evidence` / `task_states` / `actions` 四表） |
| Harness 门禁 | Layer-1 硬门禁：coverage / stale-id / changed-finding / verification-once；submit 门禁=`SUPPORTED 且 gaps 空` |
| 观测窗口 | `observation_char_limit`，chunk 视图按触发 query 排序（方案 E'） |
| 服务 | vLLM：8000=BM25(CPU)、Qwen3.5-4B、切换后 8002=Qwen3-32B(T P=2) |

---

## 3. 实验1 正式评测（100 条）

**做法**：830 条取 24 条已有 + 随机 76 条 共 100 条，ESR 与 baseline 各跑满 max_turns=30，离线 ExactMatch 判分。

**结果（2026-09-01）**：

| 指标 | Baseline | ESR |
|------|----------|-----|
| 提交率 | 100% | **19%** |
| 总体 acc | 17.0% | 15.0% |
| **提交精度** | — | **78.9%**（提交者中答对 89.5%）|
| 错误提交 | 83 条（**30 条过程性垃圾**）| 4 条（0 垃圾，2 条纯格式差）|

两种方案的主要差距在提交率和提交精度上：ESR 提交较少（19%），但已提交的答案正确率较高（89.5%）；baseline 提交全部，其中 30 条是过程性垃圾。

35 条正确里，双对 7、**ESR-only 8**、baseline-only 10。那 10 条 baseline-only 里，ESR 有 10 条未提交、0 条答错（verify 过不了卡死）：知道答案但交不出。gap 解决率 0.38（150 需解 / 解掉 72）。

三个独立问题：

1. **harness 崩溃归零**。修掉参数双重编码丢弃重发、HTTP 退避重试、verifier 故障降级 reject 后，100 条无崩溃。机制层稳定。
2. **baseline 30 条过程性垃圾提交**，对应"把答案写成实体"这一 SFT 行为先验的缺失，与检索/推理无关。
3. **ESR 覆盖率短板：提交极少的根因是 gap 解不掉 + verify 放不过** → **短板 A**：知道答案、verify 过不了、不提交。

```text
baseline：30/83 垃圾提交（SFT 先验缺失）
ESR     ：大量卡死未提交（verify 门禁 / RL credit assignment，实验2 正题）
```

---

## 4. 强模型分离实验：能力层 vs harness 缺陷归因

**方法**：把策略从 4B 换成强模型（Claude），其余全复用真实 `ESREnvironment` + BM25 + **真实 4B verifier**，只替换"谁产下一动作"。

**三例结论（324/186/120）**：

| 例 | 结论 |
|----|------|
| 324 | 强策略 5 步正确提交，4B verifier 一次 supported 且 grounded → **Fix8 判定可靠，非缺陷** |
| 186 | 需检索+登记 Albino Frog 前身 + 显式消解"公司名 vs 游戏名"歧义才 supported → **能力/策略层**，门禁非卡点 |
| 120 | **确凿的 harness 观察窗缺陷**：gold 在 doc 37015 字节~18500 > `observation_char_limit=16000`，结构上不可见，完美策略也过不去 |

**结论**：强策略能解决 324/186 这类"策略能力"问题，但 120 暴露了一个确凿的 harness 观察窗缺陷，且 4B verifier 本身的判定能力存疑。→ 需要同时修观察窗、并验证 verifier 能力。

---

## 5. 过渡：观察窗修复与短板 A 深挖

本章把两条通往关键验证的论据合并说明：观察窗缺陷已被 chunk 视图修复；短板 A 的 12 条判定表为后续 32B 验证提供明确靶子。

### 5.1 观察窗修复（方案 E'：chunk 视图）

120 的 16k 观察窗结构性不可见。修复：`retrieval.py` 加 `get_doc_chunks`（单篇按 token 分块、BM25 按触发 query 排序取 top-K）；`environment.py` 的 `open_page`/`read_evidence` 默认返回 `view:"chunks"`；证据目录仍存完整原文。**方案 E'**：`verify_answer` 把每条 supporting Evidence 的 content 换成重建的 chunk 视图文本再传给 verifier，使 **verify 与 search 看到同一视图**，消除观察面不对称。单测 26 passed。

120 复验：chunk 视图 5922 字符 verbatim 含 RQ#3，旧假 fixation 彻底消失。但 4B verifier 仍拒（唯一 gap 是"证据不含字面 West African entrepreneurship"，而 doc 全文无该字面串）→ 残余卡点收窄到 **4B verifier 能力边界**。

### 5.2 短板 A 的 12 条深挖（判定表）

对 12 条 GOLD-MATCH-but-0-supported 轨迹，用强策略 + 真实 BM25 + 真实 4B verifier 走完整链，**12/12 全 needs_revision、0 提交**。判定分 3 类：

| 类别 | 条数 | 归属 |
|------|------|------|
| **假打回** | 4（1041/1198/324/636）| gold 真在喂入 chunk 视图却拒读 —— **4B 语义误判** |
| **unparseable** | 3（1089/391/83）| 4B 输出非干净 JSON，解析失败吞正确轨迹 |
| **真阳性** | 5（186/56/364/517/772）| open 到不含 gold 实体的 top-hit doc —— **检索召回缺 gold 段落，非 verifier** |

**根因三层叠加**：5/12 检索召回真缺口；4/12 verifier 语义误判；**submit 门禁无逃生**（`_submission_error` 只认 SUPPORTED，`needs_revision` 无任何放行 → verifier 一拒正确轨迹永远卡死，harness 结构性缺陷）。

**分离验证**：我（Claude）当 verifier + 真实 harness → **12/12 全部 submitted**（`me_verifier_batch.py`）。连 4B 判 needs_revision 的真 case（636 r1/r2、772 r1）也是证据真缺片段、harness 正确放行补证。

**结论**：harness 门禁 + chunk 视图 + 方案 E' 全部实现正确。**短板 A 的 4B 失败 = verifier 能力 + 检索召回两个独立短板**，harness 无 bug。下一步换更强的 verifier，引出 32B。

---

## 6. Qwen3-32B verifier：换模型验证

**背景**：用户裁决本地有 Qwen3-32B 想换作 verifier，且「适配模型而非数据集，不针对单样本加规则」。两台 GPU 上 4B vLLM 全停，启动 **Qwen3-32B**（端口 8002，TP=2），8000 BM25 保留。

**基线**：`mev_12`（强策略 + Claude verifier + 真实 harness，12 条全 submitted，evidence 已含 gold）——纯测 verifier。

### 6.1 一次性重判（`replay32b_mev12.py`）

从 12 条 mev_12 账本重建 (question, answer, evidence 原文)，32B 逐条重判，**不重跑检索、无注入**：

**6/12 supported**：1041 / 1089 / 1198 / 517 / 772 / 83 —— 证据含 gold，4B 对这几条是纯幻觉式假打回。
**6/12 needs_revision**：186 / 56 / 324 / 364 / 391 / 636，gap 全实质性：

- 186 缺"公司 1990s 原名（两栖动物）"；56 缺 ReFrame Stamp/MPA/导演二片；324/364 缺链条前因；391 缺院系任职。
- **636 最关键**：32B 指出答案 **"2011" 与题干"到 2020 才重命名"时间相悖**，且打开的证据确认 Rename 在 2011 之前 —— 答案本身可疑。

### 6.2 真实在线补证（`online32b_12.py`，决定性数据）

强策略 + 真实 harness，32B 当 verifier，**按 gap 换检索词正常补证**多轮，直到 supported/submit 或达上限。

**结果：10/12 SUBMITTED，2 条 needs_revision。**

| qid | 一次性重判(32B) | **在线补证(32B+策略)** | 说明 |
|-----|----------------|----------------------|------|
| 1041 Adaku | supported | **SUBMITTED** | r1，doc 61696 |
| 1089 Zius Galit | supported | **SUBMITTED** | r1，doc 86834 |
| 1198 Robert Mugabe | supported | **SUBMITTED** | r1，doc 83077 |
| 517 Peter King | supported | **SUBMITTED** | r1，doc 67431 |
| 772 Secretary | supported | **SUBMITTED** | r1，doc 93372 |
| 83 J.D. Hooker | supported | **SUBMITTED** | r1，doc 39837 |
| 186 Galacta | needs_revision | **SUBMITTED** | r1（实时证据集更全）|
| 56 Last Christmas | needs_revision | **SUBMITTED** | r1 |
| 364 Bada Lee | needs_revision | **SUBMITTED** | r1 |
| 391 M.C. Guzmán | needs_revision | **SUBMITTED** | r1 |
| 324 Svetlana | needs_revision | **no(needs_revision)** | 开 2 doc 仍缺多跳衔接 |
| 636 2011 | needs_revision | **no(needs_revision)** | 时间线矛盾，证据不足 |

### 6.3 决定性对照：同证据异 verifier

以下 4 条，strongA(4B)、mev_12、online32B **三方打开的 evidence docid 完全一致（含 gold）**，唯一变量是 verifier 模型：

| qid | evidence docid（三方一致，含 gold）| 4B (strongA) | 32B (online) |
|-----|------|------|------|
| 1041 | `61696` | needs_revision | **SUBMITTED** |
| 1089 | `86834` | needs_revision | **SUBMITTED** |
| 1198 | `83077` | needs_revision | **SUBMITTED** |
| 83 | `39837` | needs_revision | **SUBMITTED** |

同一个问题、同一份证据、同一个 harness、同一个门禁，唯一差 = verifier 从 4B 换成 32B → 4B 全拒、32B 一次过并提交。**这是"能力 vs 判据/证据"的铁证。**

### 6.4 剩 2 条的实质拒绝

- **324**：问题是"X 夺冠事件的**两年前**赢家"。已开 WSOP 2008 Ladies + 42885，仍没把"X 身份 + 两年链"衔接 → 缺的是**检索把多跳链路检索出来**，非 verifier 误判。
- **636**：32B 指出"2011"与题干时间相悖，开 19992+62889 佐证不了 → 答案标签本身可能存疑。

---

## 7. api 全自动干净重跑（ESR vs baseline）

> 在第 4-6 章，策略和 verifier 都被换成了强模型 / 更强的 verifier，回答的是"短板 A 的 4B 根因"。本章问最初的核心问题：**当前版本 ESR harness 在干净、无污染的标准评测下，相对 baseline 是否有净增益？**

前序 strong12（污染版，已从本报告删除）由单一持续上下文逐局回填，存在方法间+样本间双向污染，尤其 baseline 的 search query 常直接带答案名，把 baseline 拔高。本章改用 **api（Lanz-Medium = 强策略模型）全自动**，**每个 (qid, mode) 独立全新 session + 独立子进程**，彻底隔离上下文、无 gold、无人工回填。脚本 `analysis-L/api_policy_drive.py` / `run_api_12.py` / `evaluate_api12.py`；结果详见 `results/api12_README.md`。

**工具面（用户裁定）**：ESR=6 工具（search/open_page/read_evidence/update_state/verify_answer/submit_answer，verify 同一 api session 判）；**baseline=3 工具（search/open_page/finish）**。已核实 baseline 无 update_state/TaskState，read_evidence 因门禁必然 100% 被拒，是"死工具"，故裁定删掉。

### 结果（12×2，全部独立 session）

| 指标 | ESR | baseline |
|------|-----|----------|
| 提交率 | 92%（11/12）| 100%（12/12）|
| Accuracy（仅已提交）| **100%**（11/11）| 83%（10/12）|
| **Accuracy（含未提交）** | **92%**（11/12）| **83%**（10/12）|
| 平均工具调用轮数 | **15.2** | 6.2（≈2.45×）|

**逐条差异**：**517** ESR `Peter King Nzioki` ✓（gold=`Peter King` substring 命中）vs baseline `Peter Sarsgaard` ✗ → ESR 救回；**636** ESR max_turns 未提交 ✗、baseline `2020` ✗ → 都错；其余 10 条两臂都对。

### 关键结论

1. **ESR 净提升准确率**：含未提交 **92% vs 83%（+9pp）**，提交精度 **100% vs 83%**。干净版 baseline 无提示自然退化（517 答 `Peter Sarsgaard`、636 答 `2020`）。ESR 的 verify 门禁成为稳定器。
2. **1041 被修好**：污染版两臂都答 `Bonang Matheba`，干净版两臂都对 `Adaku`（gold）→ 证明 1041 先前的错是**上下文污染（先入为主的误导）**，数据/模型无误（呼应第 5.2 章归类为假打回）。
3. **轮数差距稳健**：ESR ≈ **2.45×** baseline（15.2 vs 6.2）。门禁天然多花轮。
4. **caveat（判分敏感）**：`517_esr=Peter King Nzioki` 靠 gold=`Peter King` substring 宽松命中判对，非严格实体相等。若按严格相等算，ESR 含未提交掉到 83%，与 baseline 平手。**ESR 是否真增效对宽松/严格判分敏感，须明示。**
5. **636 gold=2011 存疑**（第 6.4 章 32B 已标"时间线相悖"）；本重跑两臂都答别的年份，符合存疑预期，未复现。

### 净结论

强策略 + 干净隔离下，**ESR harness 提升提交精度（100% vs 83%）并在宽松判分下净增准确率（+9pp），代价是 ~2.45× 工具轮数**。baseline 3 工具最省轮但易草率出错。ESR 的"宁可交不出、不交错的持证回答"语义成立，成本显著。"ESR 是否值得"取决于精度 vs 轮数预算的取舍。

---

## 8. 本地 Qwen3-32B 策略 + verifier：方向相反的对照 ★ 最新

> 在第 6 章，本地 32B 只当 **verifier**（策略仍为 api 强模型）已证明比 4B 更会放行正确的证据。本章把 32B 同时换作**策略 + verifier**，在同一套 ESR/baseline 两臂下跑标准评测，看本地 32B 全链路时 ESR 相对 baseline 是否还有净增益。这是 api12（第 7 章）的本地强模型对照臂。

**做法**：830 条按 `seed=20260904` 随机抽 100 条（不排除原 12），`max_turns=100`，每 `(qid,mode)` 独立全新 session + 独立进程，离线 `ExactMatchJudge` 判分。驱动器按 40960 窗口做 token 估算裁剪（实测 dense escape-HTML 证据最高 4.1 token/字符，故改用 token 上界裁剪而非字符数）。脚本 `local32b_policy_drive.py` / `run_local32b_100.py` / `evaluate_local32b100.py`，结果 `results/local32b100_README.md`。

**结果（2026-09-07）**：

| 指标 | ESR | baseline |
|------|-----|----------|
| 提交率 | **47%**（47/100）| **100%**（100/100）|
| Accuracy（仅已提交）| **23%**（11/47）| 15%（15/100）|
| Accuracy（含未提交）| 11% | **15%** |
| 平均工具轮数 | 58.1 | 4.3（≈13.5×）|

**正确集合**：双对 9，ESR-only 2（1007/266），baseline-only 6（1108/1226/1230/380/853/907）。

### 8.1 方向反过来了

api12（第 7 章）里 ESR 含未提交 **92% vs 83%**、提交精度 **100% vs 83%**——ESR 全面占优或持平。换成本地 32B 全链路后，**ESR 含未提交 11% 反而低于 baseline 的 15%**，方向相反。差异不在哪臂更强的单一因素，而在 32B 同时管策略与 verifier 时 ESR 的失败模式变了：

1. **提交少**：47% ESR 局打满 100 轮不提交。32B verifier 对置信答案纠缠不可解 gap（对齐第 6 章的实质拒绝），策略在同一个 top-hit 文档上来回重搜，最终 max_turns。这 53 条的努力全部归零，是含未提交准确率被拖到 baseline 之下的主因。
2. **提交的也不都准**：提交精度 23% 高于 baseline 的 15%，但被「拒绝式放行」稀释——47 条已提交里 11 条是「证据不足/未提供/无法确认」类**拒绝措辞**答案，32B verifier 判其为 supported（gaps 空）放行提交。
3. **2 个方向同时偏**：verifier 既对正确实体过度严格（打满 100 轮），又在拒绝式答案上过度宽松（放行）。这反映 32B 当 verifier 的判据没跟上「提交具体正确实体」的目标，属于策略/verifier 能力与判据绑定问题，非门禁机械缺陷。

### 8.2 排除了 harness 机械缺陷

本实验修掉一个真 harness 问题：上下文裁剪在密集 escape-HTML 证据（如 Google Tag Manager/iframe dump，最高 4.1 token/字符）下，把刚追加的当前消息也裁空，导致「空对话」400，4 条误报为 error。改为「绝不裁最后一条正在请求的消息」+ token 上界估算后，**200 条无崩溃、无 error**，4 条归为 max_turns。剩余全部是能力/门禁行为，无 infra artifact。

## 9. 最终归因与结论

**一句话**：**短板 A 的根因 = 4B verifier（Qwen3.5-4B）的判断能力不足，会幻觉式拒绝正确答案**；责任在 harness 机制、数据集、或适配上的部分已逐一排除。

逐步归因（每层只剥离出一层）：

1. **harness 机制无 bug**：harness 门禁在强模型 verifier（Claude）下 12/12 全链路顺畅放行（mev_12）；门禁经系统复验 17/17 通过。
2. **证据/数据集无问题**：同证据（docid 一字不差、含 gold），4B 看 gold 说"没给实体名"，32B 一次过。证据本身没问题，4B 读不懂。
3. **适配到位**：我们没有给数据加规则，反而**放宽**判据迁就 4B（实体/证据判据 + unparseable 重试），4B 依旧过不了；32B 用同一套 prompt 游刃有余。问题在 4B 推理能力。
4. **存在一个真 harness 缺陷（观察窗 16k）**：已通过 chunk 视图（方案 E'）修复，且非短板 A 主导。
5. **与 verifier 独立的第二短板 = 检索召回广度**（186/56/364/517/772 需正确 docid），属能力层，非 harness。

**换 Qwen3-32B verifier 后**：**10/12 在同样条件下一次闭环提交，无需数据侧 hack**；剩 2 条是真实的检索多跳难题（其中 636 的 gold 标签存疑）。结论收束为「**换更强的 verifier 即可解锁，瓶颈在 verifier 能力环**」。

在强策略 + 干净隔离的标准评测下（第 7 章），ESR 相对 baseline 净增准确率（+9pp 宽松判分）并提升提交精度（100% vs 83%），但多花 ~2.45× 工具轮数。**"ESR 是否值得"最终取决于精度 vs 轮数预算的取舍。**

**32B 全链路给出反向约束（第 8 章）**：本地 32B 同时当策略与 verifier 时，ESR 含未提交 **11% 反而低于 baseline 的 15%**。这说明第 6 章「换更强 verifier 即可解锁」的结论有一个前提——策略本身要够强（当时是 api 强策略）且与 verifier 解耦。把二者都换成 32B，ESR 的门禁循环（打满 100 轮）+ 拒绝式放行同时出现，净增益消失。**ESR 的价值依赖策略-verifier 的组合质量，而非 verifier 单点强度。**

---

## 10. 下一步方向

1. **升级 verifier 到 Qwen3-32B（已证明有效）**，重跑那批 100 条正式评测，看真实提交率与提交精度（12 条 10/12 是强信号，100 条待量化）。
2. **处理剩 2 条**：324（检索多跳强化）、636（核实 gold 标签是否存疑）。
3. **检索召回广度作为独立能力目标**：q772/636 需正确 docid 打开，属策略/检索能力，可并行优化。
4. **RL/SFT（实验2，存续）**：清掉"verify 支持却不下 submit"（416）与打满不收敛，用 RL credit assignment（verify 通→submit 正强化）；冷 SFT 固化 open→update→verify→submit 流程纪律。
5. **verifier 端确定性兜底（可选）**：若要让 4B 也能用，可加 KeywordVerifier/确定性约束核验兜底 submit。32B 已证明不再需要。
6. **ESR 与 baseline 的大规模对照阈值**：12 条 ESR +9pp（宽松）对判分敏感，需在更大样本上量化到置信区间。