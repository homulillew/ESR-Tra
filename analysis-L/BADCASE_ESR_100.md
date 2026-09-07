# ESR 侧 Bad Case 分析（实验1，100 条批）

日期：2026-09-02
数据：`exp100_report.json` 的 ESR 100 条（15 对 / 4 错 / 81 未提交，ExactMatch 判据）
复核：本文档中我做为语义 judge 对已提交 19 条逐条人工复核（4B LLM judge 因 `enable_thinking` 噪声不稳定，弃用）
诊断工具：`tools/inspect_tail.py <store.sqlite> [n]`

---

## 0. 总览：ESR 100 条的三种结局

| 结局 | 数量 | ExactMatch acc | 语义复核 acc |
|------|------|---------------|-------------|
| 已提交且答对 | 19 条提交，其中判对 15 | 15/100 = 15.0% | 17/100 = 17.0% |
| 已提交但答错 | 4 | — | 2（311/776 真错）|
| 未提交 | 81（含 19 条触顶 30 轮）| — | — |

已提交 19 条的**提交精度**：ExactMatch 78.9% → **语义复核 89.5%**（17/19）。

---

## 1. 已提交侧（19 条）：精度极高，但格式误判低估了它

### 1.1 我做为 judge 的逐条复核

| qid | ESR answer | gold | ExactMatch | 语义复核 |
|-----|-----------|------|-----------|---------|
| 102 | `53%` | `53%` | ✓ | ✓ |
| 241 | `Queen Marie of Romania (Marie of Edinburgh)` | `Queen Marie of Romania` | ✓(含) | ✓ 括号为别名 |
| 263 | `Simerly` | `Simerly` | ✓ | ✓ |
| 284 | `Come Into My Arms` | `Come into my arms` | ✓ | ✓ |
| 299 | `Baron Empain Palace` | 同 | ✓ | ✓ |
| **311** | `Magic Kids` | `Cocomiel` | ✗ | **✗ 真错** |
| 506 | `Patision Avenue` | 同 | ✓ | ✓ |
| 512 | `Sam Curran` | 同 | ✓ | ✓ |
| 563 | `Mikko Uusitalo` | 同 | ✓ | ✓ |
| 577 | `DN AGRAR GROUP SA` | `DN AGRAR Group` | ✓(含) | ✓ 实体一致（加 SA 后缀）|
| **581** | `90 g` | `90g` | ✗(空格) | **应判对**（同值不同书写）|
| **607** | `1lbs 6oz` | `1lb 6oz` | ✗(复数s) | **应判对**（同值）|
| 637 | `Fibrodysplasia ... (FOP) - 进行性...` | `Fibrodysplasia ossificans progressiva` | ✓(含) | ✓ 加缩写+中文翻译 |
| 643 | `Alicia Moruf, PharmD, MPH, RAC-US` | `Alicia Moruf` | ✓(含) | ✓ 加头衔 |
| 756 | `Thierry Dunter` | 同 | ✓ | ✓ |
| **776** | `Diamond Jenness` | `The Dorset Culture of the Eastern Arctic` | ✗ | **✗ 真错** |
| 815 | `One Red Rose` | 同 | ✓ | ✓ |
| 919 | `Charlotte Clark` | 同 | ✓ | ✓ |
| 1038 | `Wind farms, ...` | 同 | ✓ | ✓ |

**结论**：ExactMatch 把 581、607 两题因**格式差**（`90 g` vs `90g`、`1lbs 6oz` vs `1lb 6oz`）误判为错。语义复核下**提交精度 89.5%（17/19）**，真实错误仅 2 条：
- **311**：gold `Cocomiel`，答 `Magic Kids`——验证器把关后仍放过了，多跳到相近实体
- **776**：gold 是文化名 `The Dorset Culture...`，答了人名 `Diamond Jenness`——**答了相关但错误粒度的实体**

### 1.2 提交精度高的原因（为什么是 89.5% 而不是 baseline 的 17%）

19 条提交全部经过 verify 门控（平均 verify 次数≥1，全部 supported 才提交）。对比 baseline 83 条错误提交里 30 条是过程性垃圾——**ESR 的 verify 门控把"行为出口错误"（计划文本当答案）完全挡住了**。ESR 答错的多是"真找到证据但在最终实体对齐上错"（311/776），属能力层而非行为层。

---

## 2. 未提交侧（81 条）：ESR 真正的短板——覆盖

### 2.1 先分清：不是静止不动，是「推进到 verify 后卡住」

| 成因桶 | 数量 | 说明 |
|--------|------|------|
| ③ verify 打回但 gap 解不掉 | **78** | open 正常，建立 state，push verify，但残留 gap 收尾失败无法提交 |
| ② open 了但没到 verify | 3 | 95/202/383，接近但没走完 verify 流程 |
| ① search 死绕 (open=0) | **0** | 已根治！ESR 不再有纯 search 从不 open |

**关键**：ESR 的覆盖短板**不是"不找东西"**——81 条里 78 条都正常 open、建 state、verify，是**"找到证据后卡在 verify 打回的 gap 上，收尾解不掉"**。这与 baseline 的病（search→open 断裂、过程语言交差）完全不同。

### 2.2 gap 解决率：没有任何一条能「全解决」

未提交 78 条的 gap 解决状态：

| 状态 | 数量 |
|------|------|
| 全未解决（1 个 gap 卡死）| 32 |
| 部分解决 1/2 | 36 |
| 部分解决 2/3 | 7 |
| 部分解决 3/4~6/7 | 3 |
| 已全解决却没提交 | **0** |

**「已全解决 gap 却没提交」为 0** ——这是最重要的一点：模型一旦走到 verify、被打回，就几乎再也收不了尾。它缺少「围绕剩余 gap 定向补充证据→update_state 回填→再 verify」的收敛闭环。

### 2.3 卡住的两种具体机制（轨迹尾部实证）

**机制 A：verify 打回后退回换词重搜（23）**
```
search → (update_state) → verify: needs_revision
  → 清一色近义换词重搜: "2021 movie... police scam" / "2020 film... police corruption" / "2022 film..."
  → verify 打回 → 再换词
（gap 从没被 update_state 针对性地推进，最后空转 29 轮）
```

**机制 B：非法 read_evidence 死循环（170）**
```
... → verify 打回（gap 未解）
  → 后 7 个动作全是 read_evidence: legal=False（被拒）
  → 模型困在"读证据但读不到该读的"→ 消耗轮次 30 触顶
```

两种机制同源：**verify 产生 gap 后，模型不知道「补哪些证据、在 update_state 里怎么回填 gap」**，于是陷入换词重搜或非法读取的空转。这不是 4B 完全不会，而是**缺少一个「gap→定向检索→回填」的结构引导**。

### 2.4 覆盖短板的误判排除

- 81 条中 **46 条 gap≥2**（验证器判定需要多步拆解的深题）——**这些本就该难**，baseline 对同批题也一样大部分错
- 32 条「单 gap 但 verify≥1 次都解不掉」——这些是**最可惜的**，只差一点点就收敛，但没闭环
- 19 条触顶 30 轮——**max_turns=30 确实限制了**（详见 §4）

---

## 3. 平均工具调用轮数（用户重点要求）

### 3.1 已提交侧：ESR 更省

| | BL | ESR |
|---|----|----|
| 已提交数 | 100 | 19 |
| 平均 turns | 19.4 | **11.8** |
| 平均 search | 12.1 | **4.7** |
| 平均 open | 1.8 | 1.8 |

**ESR 一旦提交，轮数更少、搜索更精准**（4.7 vs 12.1）——因为它结构化推进，不盲目乱搜。

### 3.2 双方都答对的 7 条：ESR 略省但有方差

| qid | BL turns/search/open | ESR turns/search/open |
|-----|---------------------|----------------------|
| 102 | 19/5/4 | 10/4/2 |
| 284 | 6/4/1 | 13/5/2 |
| 506 | 16/4/2 | 6/2/1 |
| 563 | 11/9/1 | 9/4/2 |
| 643 | 5/2/2 | 5/1/1 |
| 756 | 6/3/2 | 27/13/5 |
| 815 | 27/7/4 | 8/4/1 |
| **平均** | **12.9/4.9/2.3** | **11.1/4.7/2.0** |

双方都答对的条件下，**ESR 平均 11.1 轮 vs BL 12.9 轮，略省**；但 ESR 方差大——506 只需 6 轮极快，而 756 被 verify 门控中途打回拖到 27 轮（这是交精度换覆盖的代价）。815 是 ESR 修复的经典 win：BL 27 轮，ESR 8 轮。

### 3.3 含未提交的全量：ESR 轮数相近但 verify 开销真实

| | BL | ESR |
|---|----|----|
| turns | 19.4 | 20.9 |
| search | 12.1 | 10.7 |
| open | 1.8 | 2.8 |
| verify | 0 | 2.3 |

**关键**：未提交的 81 条平均 23 轮、2.5 次 verify——**这些轮次大部分花在「push verify→打回→再试」上**，是数据实际显示 ESR 全面轮数与 baseline 相近的原因。ESR 在未提交案例上烧了大量轮次在 verify 打回的 gap 空转上，这是 max_turns=30 下覆盖上不去的直接原因。

---

## 4. max_turns=30 的公平性反思（对比 ECHO/AREX 100-200 轮）

用户提出的点非常关键：**当前 max_turns=30，而主流 research-agent 评测（ECHO、AREX 等）用 100-200 轮**。对 ESR 的影响：

1. **19 条恰好触顶 30 轮被截**——其中不少（含 gap 接近解决的）如果多给 30-70 轮，完全可能「再搜一轮证据→update_state 回填→verify 通过→提交」。max_turns=30 实质性压低了 ESR 的可达上限。
2. **ESR 结构性更耗轮次**：baseline 是「搜→猜→交」20 轮完事；ESR 要「搜→open→update_state→verify→(打回)→再搜→再 update→再 verify」,每轮有结构化开销。在 30 轮里 ESR 能覆盖的深度天然比 baseline 浅。
3. **判断**：30 轮是 baseline 说得过去、但**对 ESR 不公平**的下限。应在**扩大轮数的实验（如 max_turns=100）里重跑 ESR**，看「gap 死循环」是否会被更多轮次救活、提交率是否明显上升。若扩大后覆盖显著回升，则证明当前覆盖短板**部分是 max_turns 造成的人工瓶颈**，而非纯能力天花板。

---

## 5. 分层归因与处置建议

| 现象 | 层 | 处置 |
|------|----|------|
| 提交精度 89.5%（已显著） | — | 保持，verify 门控有效 |
| 581/607 格式误判 | **评测** | ExactMatch 对数值/单位应宽容（`90g`≡`90 g`）；换 LLM judge 或规范化 |
| 311/776 实体对齐错 | RL/能力 | 最终实体选择需更强判别；可加候选实体消歧 SFT |
| **gap 解不掉死循环（78条主因）** | **harness 可大幅缓解** | 见下「gap 闭环引导」 |
| verify 服务不可用被当正常打回 | harness 副作用 | 「服务不可用」reject 应带特殊标记让模型知道是元故障，避免误导 |
| 覆盖受 max_turns=30 限制 | **实验设计** | **重跑 max_turns=100** 对照，量化轮数对覆盖的影响 |
| baseline 的过程语言垃圾 | SFT | 已有 `sft_sample_815.md`；BADCASE_BASELINE_100.md 详析 |

### 最重要的改进点：gap 收敛闭环引导（harness 层）

ESR 卡住的核心是「verify 打回产生 gap 后，模型没有围绕 gap 定向工作的闭环」。可加：
1. **verify 打回后 guidance 明确列出待解 gap 清单 + 引导**："当前剩余 gap：G1 xxx；请 open 与 G1 相关的新文档，在 update_state 中针对 G1 补充 answer/evidence，然后再 verify"。
2. **gap→检索桥**：把待解 gap 文本注入下一步 search 的 query 建议（模型常因 gap 太抽象而换词重搜不到）。
3. **非法 read_evidence 死循环断环**：类似 `_search_open_break`，检测连续非法 read/换词 search，强制"open 新 doc→update_state 针对 gap 回填"。
4. **verify 服务不可用标记**：reject 里带 status=service_error，模型可识别为"稍后重试"而非"我答错了"。

这些是**确定性 harness 改动**（实验1 已验证 `_search_open_break` 同类机制能显著改善结构），预计能实质拉升提交率、缓解覆盖短板，且不牺牲精度。

---

## 6. 结论

ESR 在 100 条上呈现「**又准又省但覆盖不足**」：
- **准**：提交精度语义复核 89.5%，验比 baseline 17% 高 5 倍，零过程语言垃圾
- **省**：已提交平均 11.8 轮 vs BL 19.4；双方都答对数位基本打平但略省
- **但不覆盖**：81 条未提交，主因是「verify 打回后 gap 解不掉死循环」（78 条）+ max_turns=30 触顶（19 条）。这不是"不干活"，是"干到位了却收不了尾"。

**最关键的一个可行动结论**：覆盖短板大概率可被 (a) 更大 max_turns（重跑 100 轮对照）+ (b) gap 收敛闭环引导（harness 确定性改动）实质缓解，而非纯 4B 能力天花板。这两个是下一轮实验最值得先做的。