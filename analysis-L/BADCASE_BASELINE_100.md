# Baseline Bad Case 分析（实验1，100 条批）

日期：2026-09-02
数据：`exp100_report.json` 的 baseline 100 条（17 对 / 83 错，全量提交）
诊断工具：`scripts/experiment1_pipeline/inspect_tail.py <store.sqlite> [n]`（看动作序列尾部）

---

## 总览：83 条错误提交的三类分解

| 类别 | 数量 | 占错误 | 占全部 |
|------|------|--------|--------|
| A. 过程语言当答案 | 53 | 64% | 53% |
| B. 纯实体错（可评估的事实断言但错） | 30 | 36% | 30% |
| C. 近似对（格式/裁剪差） | （含在B内 1 条） | — | — |

**一半以上的查询（53%）baseline 交的根本不是一个"答案"**，而是计划文本、自我怀疑、或对系统提示的复述。

---

## A 类：过程语言当答案（53 条）—— 两个子模式

### A1. 早期放弃（9 条，≤10 轮）：「检索不中 → 计划文本塞进 finish」

轨迹形态（1193 为代表，sqlite 4 个动作）：
```
search×3 (BM25 全 miss) → finish(answer="我应该搜索关于板球锦标赛…的信息，或者搜索…")
```

6/6 抽查确认同一模式：**连续 search miss 后，模型把"下一步搜索计划"直接写进 finish.answer**。
它把 finish 当成了"说出下一步想法"的出口，而不是"提交最终答案"。检索受挫是触发器。

- 触发点：3-5 次 search 全部 miss（BM25 对长尾查询召回差）
- 表现：answer 里带引号的待搜索词（"或者让我搜索 X 和 Y"、"也许我需要搜索…"）
- 这类查询 ESR 同样处理不了检索，但 verify 门控把它挡住了不提交

### A2. 晚期放弃（44 条，>10 轮）：耗尽后的挣扎文本

- 30 条 open=0：**baseline 也有 search→open 断裂**（与 ESR 修复前同构！）——纯 search 刷 25-30 轮从不 open，最后把中途的思考文本交了（250: s=29/rd=0、804: s=30/rd=0）
- 14 条 open>0：open 了但 read 后被信息淹没，最后交"系统提示我当前有2个证据：e1（docid 42885）…"这类**系统状态复述**当答案

**关键结论：search→open 断裂是 4B 模型本身的通病，不是 ESR 结构引起的。** baseline 一样有 19 条纯实体错 + 30 条过程语言错是 open=0。ESR 的 `_search_open_break` 断环器对 baseline 模式同样适用（若移植），但 baseline 无 guidance 结构可挂。

---

## B 类：纯实体错（30 条）—— 真实的检索/推理失败

- 19 条 open=0：搜了一堆没打开，然后**瞎猜一个实体**交（1094: s=2 o=1 t=4 就交了 "Ruben Neves" vs gold "Andrea Pirlo"；796: s=26 全 miss 后猜 "Coppa Italia 2013 winner: Lazio"）
- 11 条 open>0：打开了文档但读错段/张冠李戴（546: o=2 rd=4 交 "Mark Selby" vs gold "Ding Junhui"；517: o=3 rd=12 交 "Peter Nzioki" vs "Peter King"）
- 仅 1 条近似对（577: "DN AGRAR" vs gold "DN AGRAR Group"，判错是裁剪问题）
- 特点：**答案形态正常、事实错**——这是真实的"找证据能力不足"，RL/SFT 都难完全救，检索质量是上限

---

## 分层归因（harness / SFT / RL）

| 问题 | 层 | 处置 |
|------|----|------|
| A1 检索不中→计划当答案 | **SFT（行为先验）+ harness（可加校验）** | SFT 示范"检索不中时换策略而不是交计划"；harness 可在 finish.answer 检出"让我/搜索"模式时拒绝一次 |
| A2 search→open 断裂 | **harness（已对ESR修）** | baseline 无 guidance 挂点；SFT 示范"search 后必 open top hit" |
| A2 系统状态复述当答案 | **harness 可修** | finish.answer 含 "系统提示/evidence_id/docid" 时拒绝一次（同 ESR 偏差1的校验思路） |
| B 类检索/推理失败 | **RL + 检索质量** | 这是 4B+BM25 的能力上限，credit assignment 教它"何时放弃"而不是"硬猜" |

## 与 ESR 对照（为什么 ESR 把 83 错压到 4 错）

| 同样的问题在 ESR 侧 | ESR 的处理 |
|--------------------|-----------|
| 检索不中想交计划文本 | verify 门控 + answer 非计划文本校验 → 拒绝，转为 gap 继续找 |
| search→open 断裂 | `_search_open_break` 断环器强制 open |
| 想交系统状态复述 | TaskState.answer 结构化，系统状态在 context 里模型不当答案 |
| 瞎猜实体 | verify 独立审计实体身份 → needs_revision 打回 |

**即 ESR 的 4 道结构化防线各自拦住了一类 baseline 病**。baseline 83 错中约 53 条（A类）是"行为出口错误"，SFT 一版冷启动示范（正确的放弃姿势=交"未找到"而非计划文本；正确的收尾=实体答案）预计可显著压掉。

---

## 附：抽查确认的代表轨迹

- 1193: 3 search miss → finish(计划文本) —— A1 模式代表
- 250: s=29 open=0 → finish(比赛过程流水账) —— A2 断裂+乱交
- 1094: s=2 o=1 t=4 → finish("Ruben Neves") —— B 类瞎猜
- 546: o=2 rd=4 → finish("Mark Selby") —— B 类读错段
- 577: finish("DN AGRAR") —— 唯一近似对，judge 裁剪问题
