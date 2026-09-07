# 32B 全链路 ESR bad case 统一归因（第一类+第二类+第三类合并）

> 数据统一来源：`results/local32b100/`（本地 Qwen3-32B **策略+verifier 双弱**，随机 100 条 × `max_turns=100`，200 条无崩溃无 error）
> 分册：
> - `local32b100_retrieval_nonconvergence.md`（第一类：检索策略不收敛，53 例）
> - `local32b100_verifier_release.md`（第二类：verifier 拒绝式放行，~16 例）
> - `local32b100_entity_value_release.md`（第三类：实体/数值错，~11–13 例）
> 本文把三类的【完整轨迹 → 机械机制 → 三层归因 → 治本点】收敛成一份统一叙事，回答同一个问题：**问题出在实验配置 / ESR 方案本身 / 还是代码与 ESR 有偏差？**

---

## 〇、总览：一个"坏结果"树

100 局 ESR 最终结果（含 1 条重复 qid 会计为 101 条 × 独立 session）：

```text
ESR 100 局
├─ 提交 47
│   ├─ 正确 11
│   └─ 错误 36
│       ├─ 第二类·拒绝式放行   ~16（答案=证据不足/未找到，0 正确）
│       ├─ 第三类·实体/数值错   ~11–13（具体但错的实体/数值）
│       │   ├─ 子机制A 表面/部分匹配放行  ~9–11
│       │   ├─ 子机制B verifier自算算术错  2
│       │   └─ 判分粒度伪影  2（380/1139，非真错）
│       └─ 第二类变体(拒绝里嵌实体) ~6
└─ 打满100轮不提交 53
    └─ 第一类·检索策略不收敛（主导）
        ├─ gold 从未召回进证据 43（检索锚死错误假设）
        └─ gold 已召回但未 supported 10（策略选错实体、verifier 正确拒）
```

三类占比：**第一类 53（主引擎）> 第二类 ~16 > 第三类 ~11–13**。

---

## 一、三类各自的完整轨迹与机械机制

### 第一类：检索策略不收敛 = 错误假设锁死 + harness 信息停滞断环器失明

**数据分界**（submitted 47 vs max_turns 53）：

| 指标 | submitted | max_turns |
|------|-----------|-----------|
| 平均 search | 2.8 | **59.5** |
| 平均 distinct query | 1.8 | 3.9 |
| 平均重复打开同一 doc | 0.7 | **19.0** |
| 平均「no-op update→verify」空转 | 0.4 | **3.7** |

**完整轨迹（3 代表局，同一个锁死模式）**：

```
q1201(gold=Govardhan Asrani)：第1词合理改写 → 答案锁死 "Dr. Tatiana Toro"(错)
    → verify rationale 把错名回读 → query 被错实体锚定 → 同词重搜 60 次、开同 doc 全 dup
q161 (gold=Kune Rima)：    → 锁 "Neil Young"(错) → 'Neil Young born in 1940s' 重搜 ~84 次
q199 (gold=Gae Lowe)：     → 先整段题干堆 query → 锁错专辑 "Tunnel of Love" → 2 词重搜 ~59 次
```

**机械机制（三步组成一个死循环）**：
1. 策略锁错候选 → verify 的 rationale 把这个**错的**实体名写回给策略；
2. 下一轮 query 被错实体锚定，同一 query 反复重搜，每次 open 同一 top-doc（`dup=True`，零新证据）；
3. 在 `answer_changed=False` 的空转 update 后重 verify，永远 `needs_revision`，直到轮数耗尽。

**harness 两个漏洞让它死循环能无限持续**（`environment.py`）：
- **`_search_open_break`（:697）对"dup-open 掩护"结构性失明**：它只数"连续 ≥3 个 search-only 动作"；而坏局是 `search→open(dup)→…`——dup-open 是合法非 search 动作，把连续-search 计数器打断，断环器**永不触发**。它检测**动作种类重复**，不检测**信息增益停滞**。实测仅 8/53 在末端真以 ≥3 连续 search 收尾，其余全被 dup-open 掩护到 100 轮。
- **`update_state` 无条件重置 `UNVERIFIED`（:443）+ 对空转不设防**：`answer_changed=False` 的 update 就把状态重置成 UNVERIFIED，`_verification_error`（:1059）只查 UNVERIFIED 就放行 → **同一答案同一证据无限次 re-verify 全部合法**。`metadata` 里 `answer_changed / support_changed / changed_finding_ids` 全记录了，却从不用于阻止空转重验。

### 第二类：verifier 拒绝式放行 = submit 门禁无"实体"类型守卫 + 校验灰色地带

**完整轨迹（3 代表局）**：
```
q18 (5 动作)：1 search → open 错 doc(Houston 城市页) → 首 verify 即 supported → 提交 "Not found"
q591(9 动作)：search→open(Brandeis)→拒→同词重搜→改写 "无法确定大学名" → verify 把 5 gap 全清掉 → supported → 提交
q555(9 动作)：拒具体候选 → 改为 "证据中不存在该小说" → supported → 提交
```

**机械机制**：
- 策略检索失败（第一类）后，不是换向检索，而是**把"证据找不到"写成候选答案**；
- `VERIFY_INSTRUCTION`（local:99 / api:86 **逐字节相同**）只要求"证据文本确实点名了答案所陈述的实体/事实"——对一个**否定性答案**（"证据没有 X"），证据确实"点名"了这个否定 → verifier **合法地**判 supported；
- **`_submission_error`（environment.py:1065）没有任何"答案必须是具体实体/数值，而非拒绝式元陈述"的类型守卫**：只要非空 + SUPPORTED + gaps 空就无条件放行。

**决定性能力对照（8002 实测）**：用 q18 真实证据+拒绝答案，分别喂现行指令和加"拒绝式一律 needs_revision"的指令，32B **两次都正确 needs_revision** → 它并非看不懂拒绝，是运行时构成让它落进灰色地带、裁决定不稳定；是**规格没写死**。

**量化修复收益**：一个**模型无关的确定性"拒绝措辞守卫"** 拦下 47 条里 23 条（16 纯拒绝+7 条"找不到当事实"），**错拦正确提交 0 条**。

### 第三类：实体/数值错 = verify 无"唯一目标·逐约束·复算"约束（拆成 A/B 两子机制）

**先划界**：36 错里 16 纯拒绝(第二类) + ~6 拒绝里嵌实体(第二类变体) + **~11–13 具体但错**(本类) + 2 判分伪影。

**子机制 A · 表面/部分匹配放行（~9–11 例）**：
```
q580(gold=You're the Worst, ans=Friends)：1 search→open Friends页→首 verify 即 supported
    reason: 证据确认 Friends 是情景喜剧，与题干情节点吻合   ← 只做表面核对，不逐约束消歧
```
- 证据浮现**主语/近似候选**，verifier 只查"证据点名所述实体"的表面核对，不查"题干全部约束连乘下的唯一解"。
- **能力对照**：把 32B 塞进"唯一目标+逐约束核对+检查季数"指令后，它立刻指出 **"Friends 有 10 季，与题干'少于 10 季'矛盾"** → needs_revision。那条能推翻答案的约束**就摆证据里**，现行指令从不要求逐条核对。

**子机制 B · verifier 自算算术错（2 例）**：
```
q624：证据 Grants=28498/总=43487，verifier 自算 65.53% 却舍入成 66% 并认可 (gold=65%)
q778：verifier 自己推年龄差得 22 (gold=21)，认可自己的错算
```
- `supported` 判定**把除法/舍入/年龄差整个押给 32B 自推**，无确定性复算兜底。

**判分伪影（2 例，非真错）**：380（`46.30cm`= `46.30centimetres` 本质同数）、1139（近邻术语 `ulwaluko`/`Ukudlanga`）。

---

## 二、统一三层归因（回答"配置 / 方案 / 代码偏差？"）

## 结论先行

| 层 | 判定 | 一句话依据 |
|----|------|-----------|
| **A. 实验配置** | **不是主因，只放大耗时** | max_turns/窗口/裁剪让 53 条能烧满 100 轮；submitted 局同配置下 2.8 search 就收敛 |
| **B. ESR 方案本身** | **是主因（规格软，四处）** | 见下表 4 处缺口 |
| **C. 代码与 ESR 有偏差** | **无偏差** | 机制全在既有 environment.py；api/本地驱动检索与校验逻辑逐字节一致 |

### 方案规格的 4 处软缺口（逐个对应三类）

| # | 方案缺口（environment.py / 驱动） | 只管源码 | 喂给哪类 |
|---|-------------------------------|------|--------|
| 1 | **_search_open_break 只数动作种类重复，不检测信息增益停滞**（dup-open 掩护 → 永不触发） | `:697` | 第一类 53 |
| 2 | **update_state 无条件重置 UNVERIFIED + 空转不设防** → 无限 re-verify 合法 | `:443,:1059` | 第一类（续命机器）+ 第二类 |
| 3 | **submit 门禁无"答案必须实体/数值"守卫** → 拒绝式元陈述可提交 | `_submission_error:1065` | 第二类 ~16 |
| 4 | **VERIFY_INSTRUCTION 无"唯一目标+逐约束消歧+数值复算"约束** → 表面匹配 & 自算错被认可 | `:99`(local)/`:86`(api) | 第三类 A/B ~11–13 |

### 决定性证明：这 4 处是"规格软"而非"32B 不可修复的能力墙"

- **api12（强策略 + api verifier，同一 spec）无任何坏现象**：同一门禁、同一 VERIFY_INSTRUCTION，强策略 2.8 search 收敛、无拒绝式放行、无实体错。**强策略下这 4 处缺口全部休眠** —— 因为强策略不锁错假设、不写拒绝当答案、候选本就近对。
- **32B 能力对照实测 `可`**：被要求"拒绝式一律 needs_revision"或"唯一目标+逐约束核对"时，32B **能**正确拒/消歧。说明 32B 不是不能，是 spec 没约束、运行时不稳定地落进灰色地带。
- 因此：**坏在哪一层取决于"策略–verifier 组合姿态"，而非单点能力**。4B 时代是"verifier 幻觉式假打回"，换 32B 后 verifier 诚实了，但**策略弱 + 规格软**的组合把 bad case 从「校验器说谎」换成了「检索锁死 / 拒绝放行 / 表面放行」。这是**同一方案规格连续两代弱模型下暴露出的第二轮症状**，不是回归。

---

## 三、治本点（按杠杆合并收敛）

四个缺失的确定性接口，能同时堵住三类的大部分：

1. **信息停滞断环器**（治第一类）
   替代只数动作种类的 `_search_open_break`：连续 N 次 `search→dup-open`（零新 `created_evidence_ids`）＝零进展轮，直接强制换向；查询词与最近 M 次相同 → guidance 点名"该词已重搜 N 次、命中不变，改换关键词提取法"。
2. **update_state 空转设防**（治第一类续命机器）
   `answer_changed==False and changed_finding_ids==[] and support_changed==False` 时不重置 UNVERIFIED（或 gate 判"无实质改动则不得再 verify"），掐掉空转 re-verify 的无限续命。
3. **submit 确定性"必须实体/数值"守卫**（治第二类，收益最确定）
   `_submission_error` 对 `state.answer` 做拒绝措辞/元陈述类型检查。**量化：拦 23 条、错拦 0 条**，不碰 verifier、不碰检索。
4. **VERIFY_INSTRUCTION 加"唯一目标 + 逐约束核对 + 数值复算"**（治第三类 A/B）
   `supported` 须同时满足——(i) 该实体是题干**全部约束**连乘下的候选；(ii) 逐条核对约束、任一矛盾即 needs_revision；(iii) 含数值时先做确定性复算、算术不完全即不空 gaps。32B 实测收到约束后能正确消歧。
5. （次要）判分归一化（`cm=centimetres`、数值容差）→ 清掉 380/1139 伪影。
6. （方案级）RL credit：给"verify 拒到 K 轮仍未换 query"明确负向，逼策略跳出重复搜索。

---

## 四、一句话总收（供报告/论文引用）

> 32B 全链路下 ESR 的 bad case 没有单一机械根因，而是 **「策略弱 + verifier 弱 + 方案规格软」的组合**：
> - **检索不收敛（53）** 是策略把检索锁死在错误假设上，靠 harness 的「信息停滞断环器失明（只数动作种类）」+「update_state 空转续命（无条件重置 UNVERIFIED）」无限重搜；
> - **拒绝式放行（~16）** 是 submit 门禁没有「必须实体/数值」类型守卫，把「证据不足」当合法最终答案放行；
> - **实体/数值错（~11–13）** 是 verify 指令没有「唯一目标 + 逐约束消歧 + 数值复算」约束，表面匹配与自算算术错被认可。
>
> 三重归因：**实验配置 ✗ / 代码-ESR 偏差 ✗ / ESR 方案规格软 ✓**。api12（强策略+强 verifier、同一 spec）下这 4 处缺口全部休眠，证明瓶颈在**策略–verifier 组合质量**而非 harness 机制 bug。治本不在换更大模型，而在把这 4 个缺失的**确定性约束写进 harness 与校验规格**——其中 submit 实体守卫一项即可确定性拦下第二类、错拦 0 条。