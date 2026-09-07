# 第一类 bad case 深挖：检索策略不收敛（53 例主因）

> 数据：`results/local32b100/`（本地 Qwen3-32B 策略+verifier，随机 100 条，max_turns=100）
> 方法：从 `stores/<qid>_esr.sqlite` 的 `actions` 账本逐轮重建轨迹，逐一对照驱动代码 `local32b_policy_drive.py`、harness 门禁 `environment.py`、api 驱动 `api_policy_drive.py`。
> 回答的问题：这些"检索不收敛"到底发生了什么？是实验配置 / ESR 方案本身 / 还是代码与 ESR 有偏差导致的？

---

## 一、完整轨迹：不收敛到底是什么（逐个代表性整局）

先看统计真相（101 局 ESR，含 53 条打满 100 轮）：

| 指标 | submitted(47) | max_turns(53) |
|------|--------------|---------------|
| 平均 search 次数 | **2.8** | **59.5** |
| 平均 distinct 查询词 | 1.8 | 3.9 |
| 平均相邻重复 search | ~0 | **52.1** |
| 平均 open](重复打开同 doc) | 0.7 | **19.0** |
| 平均「no-op update → re-verify」空转 | 0.4 | **3.7** |

max_turns 局不是"换了很多查法找不到"，而是**锁定在极少数（≤4 个）查询词上，把它们同一个词反复重搜几十次**，每次都打开同一个 top 命中（`dup=True`，零新证据）、再 verify 一次、被拒、再重搜同一个词。下面逐轮看三个完整代表局。

### 代表局 1：q1201（gold=`Govardhan Asrani`，答案被锁在错实体 `Dr. Tatiana Toro` 上）

```
[t1] SEARCH  'individual born in 1940s third of eight siblings disliked mathematics...'   → 命中 61372/88500/51757
[t2] OPEN    docid=88500 (新证据 e1)
[t3] UPDATE  answer_changed=True (策略把答案写成 Dr. Tatiana Toro —— 错实体)
[t4] VERIFY  needs_revision   created=[g1,g2,g3]
             rationale: 证据不支持 ...关于 Dr. Tatiana Toro 的出生年...
[t5] SEARCH  'Dr. Tatiana Toro born in the 1940s third of eight siblings family business'   ← 查询被错实体锚定
[t6] OPEN    docid=88500 dup=True（同一篇，零新证据）
[t7] UPDATE  answer_changed=False  → 状态 UNVERIFIED 重置
[t8] VERIFY  needs_revision   created=[] resolved=[]   ← 同一答案同一证据空转
... [t9~t20] 同上：同一个词重搜 + 开同 doc + answer_changed=False + needs_revision
[t13+] SEARCH 'Dr. Tatiana Toro born in the 1940s third of eight siblings'  (第 3 个词,从此一路重复)
   ↓ 该 query 被原样重发 60 次，每次命中 88500(46)/21241/8408，每次 open 88500 都 dup=True
[t21..t91] 60 次同词重搜 + 多次 dup open，只 t92 改一次、t93 重新 verify
[t92] UPDATE ver=11 answer_changed=False
[t93] VERIFY needs_revision  created=[g4,g5,g6,g7] resolved=[g1,g2,g3]
[t94..t100] 仍同词重搜；t95/t97 策略尝试 update 但被 harness 拒(陈旧 e1) → 继续重搜
```

**q1201 的全部检索分两类**：第 1 个词（合理改写题干）1 次，**第 2+3 词（同一个 `Dr. Tatiana Toro born in the 1940s...`）61 次**。整局 100 轮，gold 从未出现在任何 open 的证据里。

### 代表局 2：q161（gold=`Kune Rima`，答案被锁在 `Neil Young` 上）

```
[t1]  SEARCH  'artist born in 1940s, looked for biological father at 17...'   → 59490/4401/21712
[t2]  OPEN    docid=59490 (e1)
[t3]  UPDATE  answer_changed=True (策略答 Neil Young —— 错实体)
[t4]  VERIFY  needs_revision   created=[g1]
              rationale: 证据不含任何关于 Neil Young 的信息
[t5]  SEARCH  'Neil Young born in 1940s looked for biological father at 17...'   ← 错实体锚定，重搜
[t6]  OPEN    docid=18673 (e2)
... [t9~t12] 同词重搜、answer_changed=False、needs_revision(created g3..g7)
[t13+] SEARCH 'Neil Young born in 1940s'  ← 只留人名+年代的最小锚词，自此重复 ~84 次
   ↓ 每次都命中相同 22157/98487/71399，open 22157 全部 dup=True，零新证据
[t16..t100] 84 次同词重搜，中间夹 answer_changed=False 的 update 给 verify 续命
```

### 代表局 3：q199（gold=`Gae Lowe (Le Duel)`，答案锁在错专辑 `Tunnel of Love` 上）

```
[t1]  SEARCH  'album with word tunnel released between 1970 and 1985 runtime 30-40 minutes band compared...'   ← 整段题干堆进 query（BM25 拉不响）
[t2]  OPEN    docid=14810 (e1)
...（策略先答 Eurythmics，verify 拒）
[t12] SEARCH  'Tunnel of Love album runtime'   ← 收敛到错候选专辑 Tunnel of Love，锁死
[t16+] 'Tunnel of Love album tracklist and runtime' (13次) + 'Tunnel of Love album runtime' (46次)
   ↓ 命中反复是 40426/78378，open 全 dup=True；verify 永远 needs_revision，answer_changed=False 空转
```

### 三个代表局的共同结构

```
锁错候选（策略把某个实体当作答案）
   → verify 的 rationale 把这个【错的】实体/名字写回给策略
   → 下一轮 query 被错实体锚定（1201:"Dr. Tatiana Toro"、161:"Neil Young"、199:"Tunnel of Love"）
   → 同一 query 反复重搜，每次 open 同一 top-doc（dup=True，零新证据）
   → 在 answer_changed=False 的空转 update 后重 verify，永远 needs_revision
   → 直到 100 轮耗尽。
```

核心机制：**策略无法在它锁定的错误假设上收敛**（因为假设本身错，verify 永远拒），而环境让它**可以无限"再来一轮"而不必改变方向**。所以看起来是"检索不收敛"，实则是**"检索方向已被错误假设彻底锁死"**，重搜只是囚徒式的空转。

---

## 二、归因：实验配置 / ESR 方案 / 代码-ESR 偏差？

### 结论先行

| 层 | 判定 | 依据 |
|----|------|------|
| **A. 实验配置** | **不是主因；只有一项放大** | max_turns=100、窗口 40960 只放大耗时，没制造新机制 |
| **B. ESR 方案本身** | **方案里有一个结构性漏洞被 32B 放大** | update_state 可空转重置、_search_open_break 对"dup-open 掩护"结构性失明 |
| **C. 代码与 ESR 有偏差** | **无——代码忠实实现了方案** | 机制完全来自 environment.py 的既有门禁/引导，非 32B 驱动改写引入 |

逐条拆。

### 2.A 实验配置：只放大耗时，不制造机制

- **max_turns=100** 与 40960 窗口只决定"能烧多久"：让 53 条能打满 100 轮，把钝刀子磨到流血。submitted 局平均只在 2.8 次 search 后结束，配置没把它们逼进死循环，说明**不是预算不足把策略逼坏**，而是**差策略用不完预算照样不收敛**。
- 窗口 40960 + 上下文裁剪（EVIDENCE_CHAR_CAP≈6000 字符、MAX_RENDERED_EVIDENCE=8、MAX_ACTION_HISTORY=30）会丢早期/长证据，对需要长历史多跳的样本有影响——但 q1201/q161/q199 的问题不是"证据被裁掉"，而是**策略从未检索到一个含 gold 的正确候选**（gold 不在任何 hit）。裁剪不是主因。
- **一处真实但次要的 config 属性**：`search_top_k=20`。Top-20 的 hit 列表里 gold 文档是否出现取决于 query 质量；当 query 被错实体锁死，top-20 里永恒是同一批错文档。这不是 top_k 大小问题，是 query 发散问题——换 query 才解，而策略不换。

**配置的定位**：它是"放大器/催化剂"，不是"根因"。同样的门禁在 api12（api 强策略）下停顿在 0.4 空转、0.7 dup-open、2.8 search 就收敛提交。

### 2.B ESR 方案本身：两个结构性漏洞（32B 恰好踩中）

`environment.py` 的门禁里有两处"想防死循环却防不住"的设计，正是本次 53 例空转的机械根子：

**漏洞一：`update_state` 无条件把状态重置为 `UNVERIFIED`，且对"什么都没改"不设防。**

- `update_state`（environment.py:443）**总是** `verification_status=UNVERIFIED`，并把 `gaps` 原样带过来（line 442）。
- `_verification_error`（line 1059）只查 `UNVERIFIED` 才放行 verify。
- 于是策略可以：`answer_changed=False` 的 update（什么都没改）→ 状态被重置成未验证 → **同一答案同一证据无限次 re-verify 全部合法**。
- 实测：max_turns 局平均 **3.7 次**这样的空转 update→verify；`answer_changed` / `support_changed` / `changed_finding_ids` 都被记录了（metadata）却**从不用于阻止空转重验**。

**漏洞二：`_search_open_break`（the 防纯-search 死循环的断环器）对"dup-open 掩护"结构性失明。**

- `_search_open_break`（environment.py:697）从最新动作向前数**连续合法 search-only**片段，≥3 个才强制 open top-1。
- 但坏局的循环是 `search → open_page(dup=True, 零新证据)`——dup-open 是**合法非 search 动作**，把"连续 search"的计数器直接打断。
- 结果：策略一边在重复搜索、一边用没产生任何新证据的 dup-open"自我掩护"，让断环器**死不触发**。实测只有 8/53 条在末端真的以 ≥3 连续 search 收尾（那 8 条断环器才在最后露出头），其余 45 条全被 dup-open 掩护到 100 轮。
- 断环器检测的是**动作种类**的重复，不是**信息增益**的停滞——而 32B 的死循环恰恰是"信息零增益"而非"动作种类重复"。

这两个漏洞在 api12（强策略）下**存在但不起作用**，因为强策略根本不会"答不出就原地重试"；32B 弱策略一遇到找不到的题，就拿这两条逃生通道把自己埋进去。

### 2.C 代码与 ESR 有偏差？——没有

`step:NOT A DEVIATION`：

- 把 q1201/q161/q199 的机制逐条回追到代码：锁错实体→verify rationale 回读→query 锚定→dup-open 掩护→空转 re-verify，**每一条都能落到 `environment.py` 的既有实现行**，不是 32B 驱动改写（`local32b_policy_drive.py`）私有加戏。
- api 与本地两个驱动在检索/引导上的处理**完全一致**（都只 delegate 给 `env._next_step_guidance`，都无任何 query 去重/重复预警/覆盖收敛约束；见 ACTION_INSTRUCTION——search 只有一句 `{"query":"<检索词>"}`，从没告之"重复词就换向"）。本地驱动**唯一**的改动是模型 I/O 层（上下文护栏、session 管理），不影响检索策略。
- 也就是说：本次不收敛是 **ESR 方案（含 harness 门禁与引导）在 32B 弱策略下的固有表现**，不是这个实验配置特有的代码 bug，也不是"代码没遵循 ESR 设计"的偏差。

---

## 三、真正的治本点（按杠杆排序）

1. **给 harness 装"信息停滞"断环器**（替代只数动作种类的 `_search_open_break`）：
   - 连续 N 次 `search → dup-open`（零新 `created_evidence_ids`）→ 强制换方向；连续 ≥2 次 dup-open 直接算"零进展轮"，打断"连续合法动作"掩护。
   - 重复查询词去重/预警：query 与最近 M 次相同 → guidance 直接点名"这个词已重搜 N 次、命中不变，改换关键词提取法，或直接从已打开的 evidence 归纳"。
2. **`update_state` 空转设防**：当 `answer_changed==False and changed_finding_ids==[] and support_changed==False` 时，**不**无条件重置为 UNVERIFIED（或至少由 gate 判定"无实质改动则不允许再 verify"），掐掉空转 re-verify 的无限续命。
3. **verify 结果消化**：`_gap_worklist` 把 gap 描述（常含错实体）直接当检索词，等于帮策略锁死错假设。改成"**从 gap 提取可核实的命名实体/日期/标题**，而不是回灌错实体全文"，并优先用已打开证据反推。
4. **RL/方案级**：给"verify 拒到 K 轮仍未换 query"明确的负向 credit，把"该换向却不换"变成一个可学习罚项（呼应实验2 的 credit assignment）。

---

## 四、一句话总结（供报告引用）

> 32B 下"检索策略不收敛"的真面目，不是检索发散，而是**策略把检索方向锁死在某个错误假设（`Dr. Tatiana Toro` / `Neil Young` / `Tunnel of Love`）上，然后靠 harness 的两个漏洞——`update_state` 空转重置 + `_search_open_break` 对 dup-open 掩护失明——把这一个错误方向无限重搜直到 100 轮**。它不是实验配置（配置只放大耗时）、不是代码-ESR 偏差（机制全在既有 environment.py 内），而是 **ESR 方案里"信息停滞断环器缺失"的结构漏洞，被 32B 弱策略大规模踩中**；强策略（api12）下同一机制完全休眠。