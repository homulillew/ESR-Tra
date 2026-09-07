# 第二类 bad case 深挖：verifier「拒绝式放行」

> 数据：`results/local32b100/`（本地 Qwen3-32B 策略+verifier，随机 100 条，max_turns=100）
> 方法：逐轮重建代表性轨迹 + 对 verifier 判定链做模型无关的代码级归因 + 用 8002 的 32B 做「同证据异指令」能力对照。
> 回答的问题：已提交但答错的 36 局里，那些「证据不足/未提供/无法确定」类拒绝措辞答案，为什么会被 32B verifier 判 `supported` 放行？归因于实验配置 / ESR 方案 / 代码偏差？

---

## 一、事实盘点：有多少、错在哪

已提交 47 局，11 正确、36 错。36 错里，**~16 例提交的是拒绝式措辞（非实体/数值答案），且 16 例全部判错（0 正确）**：

- 纯拒绝措辞 16 例：`18/98/175/297/301/394/426/555/591/628/753/785/864/885/1076/1119`——答案都是「Not found / Insufficient evidence / The evidence does not provide... / 无法确定」这类**关于证据的话**，不是直接回答问题的实体/数值。
- 另有少数「把"找不到答案"当作事实陈述提交」的（如 `282/838/1211/1022` 的 `The series is not identified...`），与 16 例同源。既有的 deep-dive 按更宽的「非具体实体」边界记为 **18**；我这里按纯拒绝措辞计量为 **16**。**边界是模糊的，但稳定内核是：约 16±2 例"没给出答案却让 gate 放了行"，且 0 例正确。**

这类对精度是纯损耗：提交的是必错的答案，还占用了提交配额（它本可以不提交，留成 max_turns/未提交，反而对准确率无害）。

## 二、完整轨迹：拒绝式答案是怎么上去的（三个代表局）

### q18（gold=`Lillian Karabaic`，5 动作，首 verify 就 supported）

```
[t1] SEARCH  'founded annual bike ride 2008 presentation 2014...'   命中 70320/8772/57291
[t2] OPEN    docid=94524 → e1（其实是 Houston 城市维基页 —— 检索完全没对准人）
[t3] UPDATE  answer_changed=True（策略写："Not found in the provided evidence"）
[t4] VERIFY  supported  created=[] resolved=[]     ← 首验即放行
             rationale: 证据确认文档里没有提到符合描述的个人。
[t5] SUBMIT  "Not found in the provided evidence"   ← 交了个"没找到"当答案
```

### q591（gold=`German University in Cairo`，9 动作）

```
[t1] SEARCH  'university established between 2000 and 2003 founder scientist...' 命中 63685(Brandeis 维基)
[t2] OPEN    63685 → e1（Brandeis，不是 GUC；gold 不在证据里）
[t3] UPDATE  answer_changed=True
[t4] VERIFY  needs_revision  created=[g1..g5]（合理拒绝）
[t5] SEARCH  同词重搜（检索锚死、没换向）
[t6] OPEN    63685 dup=True（零新证据）
[t7] UPDATE  answer_changed=True（策略改写 answer="Insufficient evidence to determine the university's name."）
[t8] VERIFY  supported  created=[] resolved=[g1..g5]   ← 校验器把 5 个 gap 全清掉
             rationale: 答案"证据不足无法确定大学名"是 supported，因为提供的证据确实不含相关信息。
[t9] SUBMIT  "Insufficient evidence to determine the university's name."
```

### q555（gold=某 2003 小说的作者，9 动作）

```
[t4] VERIFY  needs_revision created=[g1]（拒了具体候选 All the Birds, Singing）
[t5] SEARCH  同词重搜 → dup open
[t7] UPDATE  改写 answer="There is no evidence in the provided text of a novel..."
[t8] VERIFY  supported  created=[] resolved=[g1]
             rationale: 答案正确陈述了证据中不存在符合描述的小说。
[t9] SUBMIT  拒绝式措辞
```

**三条轨迹的共同结构**：检索没对准 gold（第一类失败）→ 策略在被打回后不是继续换向检索，而是**改写成"证据找不到"作为候选答案 → 32B verifier 把"证据没有 X"这个【否定性陈述】认可为 supported → 空 gaps → gate 放行提交一个必错的非答案**。

## 三、归因：为什么会被放行，属于哪一层

### 决定性代码事实：这不是 32B 推理失败，而是规格缺口

`_submission_error`（`environment.py:1065`）是提交门禁的全部检查：
```
is_submitted / state None / missing directory / 空 answer / 无 supporting / gaps 非空 / 非 SUPPORTED
```
**其中没有任何"提交答案必须是具体实体/数值，而非拒绝式元陈述"的类型检查。** 所以只要：
1. 策略把"证据不足"写成 candidate answer（非空）；
2. verify 判 `supported` 且 `gaps` 空；

门禁就无条件放行。`submit ⇒ must-be-concrete` 这条约束**在 harness 层根本不存在**，无论 verifier 是谁。

同源地，`VERIFY_INSTRUCTION`（`local32b_policy_drive.py:99`，与 api 驱动 `api_policy_drive.py:86` **逐字节相同**）只要求：
> "supported 要求：证据文本确实点名了答案所陈述的实体/事实，且逻辑链成立"

对一个**否定性答案**（"证据没有 X"），证据文本确实"点名"了"证据没有 X"这一陈述 → 校验器就合法地判 supported。**指令从未告诉校验器"拒绝式措辞不是合法最终答案"。**

### 同证据异指令的能力对照（8002 实测）

我用 q18 的真实证据（Houston 维基页，gold 确实不在其中）+ 真实拒绝答案，分别喂给 8002 的 32B：

| 条件 | 32B 判定 |
|------|---------|
| A) 现行 `VERIFY_INSTRUCTION` | `needs_revision`（列 gap：无符合描述的个人）|
| B) 加强制「答案必须具体实体，拒绝式一律 needs_revision」 | `needs_revision`（列 4 条要补的证据）|

两次都是 needs_revision，说明：**在干净、隔离的 prompt 下，32B 本身就能拒绝要它拒绝的东西**——它不是"看不懂拒绝"。但**真实轨迹里它却 certifed 16 次 supported**。差异来自运行时的构成不同：真实 verify 喂的是策略 update 时引用的 chunk-view 证据 + 策略的完整上下文，而非我离线构造的原始片段；在这些构成下 32B 的裁决定**不稳定**、落进"否定性陈述可 support"的灰色地带。

### 三层归因

| 层 | 判定 | 依据 |
|----|------|------|
| **实验配置** | 不是主因 | max_turns/窗口/裁剪不产生"拒绝被放行"；任意配置下门禁都会放 |
| **ESR 方案** | **是主因（结构性规格缺口）** | 提交门禁无"必须实体"类型守卫 + VERIFY_INSTRUCTION 未禁拒绝式，两者共同允许"证据不足"当答案提交 |
| **代码-ESR 偏差** | **无偏差** | api/本地驱动 VERIFY_INSTRUCTION 与 submit 门禁逻辑完全一致；release 全在既有 environment.py 内 |

**与强策略（api12）的对照**：同一套规格，api12 11/12 提交都判对，**没有拒绝式放行**。不是 32B verifier 比 api verifier 更呆（我的能力对照显示 32B 能拒），而是 **api 强策略从不把"找不到"写成候选答案**——它总能吐出实体。所以这个规格缺口在强策略下休眠，弱策略一触发（检索失败后放弃）就暴露。再一次印证本 batch 的第一类结论：**坏在哪一层，取决于策略-verifier 的组合姿态，而非 verifier 单点**。

## 四、治本点（模型无关、确定可复现）

1. **提交门禁加确定性的"必须具体实体/数值"守卫**（推荐，最小且 100% 有效）：
   在 `_submission_error` 里对 `state.answer` 做类型检查——含拒绝措辞标记（`not found / insufficient / cannot determine / no evidence / 无法确定...`）或"答案只是一句关于证据的话而非实体"即拒。
   **本节量化：这样一个启发式守卫能拦下 47 条提交里 23 条（16 纯拒绝 + 7 条"找不到当事实"），错拦正确提交 0 条。** 即：不碰 verifier、不碰检索，光在 gate 加一层，就把这类必错的提交全掐掉。
2. **VERIFY_INSTRUCTION 加硬约束**：明确"拒绝式措辞一律 needs_revision（missing_answer），并给出还需开什么证据"，从校验源头堵住灰色地带（32B 实测在收到这条后可正确拒绝）。
3. **策略侧 3 连**：检索失败后，guidance 应把"放弃→拒绝措辞"转为"换向检索"或"给出最佳候选并注明证据不足再 verify"，而不是让"找不到"成为可提交的最终答案。

## 五、一句话总结（供报告引用）

> 32B 下 verifier「拒绝式放行」不是 32B 推理能力缺陷——8002 能力对照显示它会拒，同指令、同预算的 api12 也没有该问题。它是 **ESR 方案的规格缺口：提交门禁 `_submission_error` 没有任何"答案必须是具体实体/数值"的类型守卫，`VERIFY_INSTRUCTION` 也未禁止把"证据找不到"这类否定性元陈述判 supported**。弱策略在检索失败后把"找不到"写成候选答案，校验器在灰色地带认可，空 gaps 后 gate 无条件放行。**一个模型无关的确定性守卫即可拦下 23 条、错拦 0 条**——这是三个 bad case 类别里修复成本最低、效果最确定的一个。