# 强策略标准评测 12 条 —— ESR harness vs 无 ESR baseline

实验日期：2026-09-04 ｜ 触发者：我（Claude）作为强策略模型，标准评测模式（不给 gold）

## 目的

前一个实验（强模型+harness 归因）证明 **4B verifier 是短板根因**，但那个实验给了 gold、且 verifier 由脚本/我代管，
没回答本实验的核心问题：

> **在强策略 + 真实检索 + 不喂 gold 的标准评测下，当前版本的 ESR harness 是否真的能提升准确率、同时减少工具调用轮数？**

## 方法

- 同一批 **12 条** BrowseComp-Plus 查询，各跑两臂：
  - **ESR**：严格当前版本 harness（search→open→read→update_state→verify_answer→submit_answer，全部门禁）
  - **baseline**：同一个 `ESREnvironment` 的 `mode="baseline"`（仅 search/open_page/read_evidence/finish，无门禁）
- 策略 = 我（Claude）逐条文件回填；ESR 的 verify 判定也由我回填（遵循用户"我回填判verify"决策）。
- 检索 = 真实 BM25（`:8000`），从 search hits 里选 docid 打开（诚实检索，无 gold/gold-docid 入策略）。
- **评测**：离线 `ExactMatchJudge`（gold 归一化子串 ∈ submitted_answer）。gold 只在 eval 阶段出现。

## 结果（12×2 = 24 局，全部 submitted）

| 指标 | ESR | baseline | Δ |
|------|-----|----------|---|
| 提交率 | 100% | 100% | 0 |
| **Accuracy (含未提交)** | **92% (11/12)** | **92% (11/12)** | **0** |
| Accuracy (仅已提交) | 92% | 92% | 0 |
| **平均工具调用轮数 total** | **8.2** | **3.3** | **ESR 多 2.5×** |
| 平均 turns | 8.2 | 3.3 | ESR 多 |
| 平均 search | 2.2 | 1.1 | 2× |
| 平均 open_page | 1.9 | 1.2 | ~1.6× |
| 平均 read_evidence | 0.6 | 0.0 | ESR 独有 |
| 平均 update_state | 1.4 | 0.0 | ESR 独有 |
| 平均 verify_answer | 1.2 | 0.0 | ESR 独有 |

## 核心结论

**在当前版本、强策略(我) + 标准评测下，ESR harness 既不提升准确率，也不减少工具调用轮数 —— 恰好相反。**

1. **准确率零增益**：两臂同为 92%（11/12）。唯一错误 qid **1041** 是我的**真实归因失误**（不是数据集 bug）：题目问的是被采访者 Bonang Matheba 的那篇访谈里，**采访者**的名字；我们两臂都答了 `Bonang Matheba`（主题人物名），而 gold 文档（docid 61696）里 Bonang 第一句话就叫采访者 **Adaku**（"Hi Adaku, its no problem at all"）。gold `Adaku` 正确，应判错。因此 12 条里两臂都真实只答对 11 条，**92% 是诚实准确率**。

2. **工具调用轮数不降反增**：ESR 平均 8.2 轮 vs baseline 3.3 轮 ≈ **2.5× 更多**。多出的 ~5 轮/局全部来自门禁与本轮观察窗：
   - `update_state` + `verify_answer` 各 1+ 次（baseline 为 0）。
   - **观察窗截断导致的失败-重试循环**（qid 83 最典型）：`read_evidence` 被拒（evidence 未入 directory）→ 需先 update_state → `verify` 判 needs_revision（e1 开头命名的 fragment #0 被窗口截断，名字看不到）→ 重读/重更新 → 重 verify → 才 submit。这类循环占了 ESR 视角下最多的冗余轮。

3. **为什么与"harness 应该有验证价值"矛盾？** ESR 的 verify 门禁价值依赖**策略/验证者自身无法独立把关**的情形。之前实验里 harness 有效，是因为策略用的是**弱 4B 模型**（它不会自己"想清楚证据是否足够"），verify 的 SUPPORTED/gap 反馈确实帮它收敛。而本实验策略 = 我（强模型），我自己已经完成证据推理与答案核验，verify 门禁只是**重复劳动 + 额外轮数的纯开销**。

## 对harnesting 路线的一句话结论

> **在强策略足以自我核验的场景，ESR 当前版本是负担不是收益：准确率持平、工具轮数翻 2.5 倍。**
> 它的价值定位应限定在**弱策略/弱验证者**（如 4B 本地模型）需要显式证据门禁来防幻觉的管线里；
> 对强策略，门禁与观察窗修正是主要成本，应优先修观察窗偏移/截断，而非继续加门禁。

## 待办 / 依赖

- ~~数据集 1041 的 gold 错配~~ —— **已核实 gold 正确，是我答错**（题目问采访者名字，我答了被采访者 Bonang Matheba；gold 文档里 Bonang 称采访者为 Adaku）。撤销此前"gold 错配"的误判。两臂 1041 皆为真实失误，92% 为诚实准确率。
- 观察窗截断（16k 窗口丢 fragment #0）是经本实验再次暴露的真实 harness 缺陷，属可修项。
- 本实验结论与 git 提交待用户提供完整 git 规则后再落地。