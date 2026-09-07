# Retry20 修复有效性验证结论

日期：2026-09-02
目的：验证 gap 闭环 5 项 harness 修复（`_illegal_read_break` / `_gap_worklist` / `_verify_service_glitch` / `_soft_deadline_note` / action_budget）对 20 条精选 bad case 是否有效。
跑法：双卡并行，max_turns=30（`esr_retry20_g0` GPU0/8005 9条，`esr_retry20_g1` GPU1/8006 10条）。

---

## 0. 一句话结论

**部分有效、但不达标。** 5 项修复把「search→不 open」的断裂彻底治愈（ESR 侧 open 不再缺位），也带来 1 条干净 win（266），但**核心的 gap 收尾死循环并没有普遍被救活**——19 条已出结果里只有 1 条从未提交变成提交。更关键的是：**暴露了一个第 3 种死循环——模型在 open_page 后攥着陈旧 evidence_id（如 e1）去 update_state/read_evidence 全部撞墙**，这是 5 项修复没有覆盖、且现在占主导的阻断机制。

## 1. 逐条对比（gp前=100批 / 后=retry20）

| qid | gap/res | 前 turns/sub | 后 turns/sub | 后动作 |
|-----|--------|-------------|-------------|--------|
| 120 | 2/1 | 24/未 | 17/未 | s7/o2/u1/v1 |
| 170 | 1/0 | 30/未 | 29/未 | s10/o3/u5/v2 |
| 186 | 2/1 | 20/未 | 30/未 | s19/o5/u2/v2 |
| 228 | 1/0 | 13/未 | 30/未 | s8/o6/u5/v1 |
| 239 | 1/0 | 17/未 | 30/未 | s11/o3/u4/v9 |
| **266** | 2/1 | 13/未 | **7/提交✓** | **s3/o1/u1/v1/submit** |
| 324 | 2/1 | 11/未 | 30/未 | s10/o9/u4/v4 |
| 384 | 1/0 | 10/未 | 30/未 | s21/o5/u2/v2 |
| 391 | 2/1 | 11/未 | 30/未 | s13/o6/u6/v3 |
| 416 | 2/1 | 24/未 | 30/未 | s14/o4/u3/v2 |
| 530 | 1/0 | 18/未 | 30/未 | s11/o3/u7/v4 |
| 533 | 1/0 | 17/未 | 30/未 | s10/o6/u8/v4 |
| 546 | 1/0 | 16/未 | 23/未 | s6/o2/u4/v1 |
| 625 | 1/0 | 18/未 | 30/未 | s13/o5/u6/v4 |
| 633 | 2/1 | 25/未 | 23/未 | s9/o7/u1/v1 |
| 661 | 2/1 | 22/未 | 30/未 | s12/o4/u7/v3 |
| 666 | 1/0 | 21/未 | 25/未 | s14/o2/u2/v2 |
| 1002 | 2/1 | 30/未 | 13/未 | s5/o1/u1/v1（接近，verify后复搜未收敛）|
| 1044 | 1/0 | 30/未 | 30/未 | s12/o3/u3/v9（尾部7连verify全被"服务不可用"打回）|

**转换率（全19条）：仅 266 一条从「未提交→提交」，5.3%。** 不足以支撑"修复有效→升级 100 轮重跑"的决策前提（用户原话：改完后先 30 轮验证，**若有效**再 100 轮重跑原始 100 条）。
| 661 | 2/1 | 22/未 | 30/未 | s12/o4/u7/v3 |
| 666 | 1/0 | 21/未 | 25/未 | s14/o2/u2/v2 |

**转换率：19 条里仅 1 条（266）从「未提交→提交」，5.3%。** 这不足以支撑"修复有效→升级 100 轮重跑"的决策前提（用户原话：改完后先 30 轮验证，**若有效**再 100 轮重跑原始 100 条）。

## 2. 干净的 win：266

- 原 100 批：gap 2/1，13 轮未提交。
- 修复后：**7 轮、42 秒提交（s3/o1/u1/v1/submit），答案=`In Asian Spaces` 与 gold 完全一致**。
- 这正是 gap-worklist + broken-loop 设计的预期形态：search→open 一手，update_state 一手，verify 通过即提交，不再退回购尾死循环。证明**这套机制方向正确，只是覆盖面不足**。

## 3. 关键新发现：第 3 种死循环「陈旧 evidence_id 撞墙」

对 4 条 g0 未转换案例的轨迹尾部实证：

```
170: open_page(71571)→合法，返回 evidence_id=e45
     update_state{e1} → "changed finding requires visible original Evidence: e1"  ← 陈旧ID
     update_state{e1} → 同上
     read_evidence{e1} → "requires an Evidence ID in the current evidence_directory"
     186: 尾部非法 read_evidence（ID 不在 directory）
     324: 尾部非法 read_evidence（同上）
     391: update_state → "changed finding requires visible original Evidence: e1"
```

机制：gap-worklist **解决了「去开对文档」**（open_page 正常触发，search→open 断裂治愈），但文档打开后模型**攥着旧/未登记的 evidence_id（如 e1）去 update_state / read_evidence，全部 legal=False 撞墙**。它不认 open_page 返回的新 ID（e45）。`_illegal_read_break` 只在「连续非法 read ≥3」才触发，且文案建议「先 update_state 登记」——但对 update_state 自身的「changed finding requires visible original Evidence」则**没有任何针对性 nudge**，模型没有从撞墙里被捞出来。

## 3.5 另外两条：1044 是「verifier 服务故障受害者」，1002 是「接近未收敛」

`_verify_service_glitch` 修复在**模型层**正确生效（模型按引导原地重试，不再误跑搜新证据），但暴露了**底层 verifier 服务不稳定**：

```
1044: 动作根=27；最后 7 个动作(20-26)全部 verify_answer legal=False
      错误全为「【系统服务瞬时故障，非答案问题】verify 服务暂时不可用（HTTPError）」 ← GPU1/8006 verifier
      模型按 glitch 引导连续重试 7 次，把剩余轮次烧完，没能等来一次成功 verify
```

- **1044 不是 gap 死循环，是 verifier 基础服务在 GPU1 反复 HTTPError**。`_verify_service_glitch` 让模型别乱搜、原地重试——对，但重试 7 次仍全部失败，说明 verifier 服务本身需要修复/重启，而非 guidance 问题。
- **1002 明显改善**：30→13 轮，delete 掉冗余乱搜（s19→s5），open/update/verify 各 1 一手推进接近，但 verify 后复搜未收敛——仍属「陈旧/缺一项证据没闭环」。

这改变了对 retry20 的归因：19 条失败里，**至少 1 条（1044）是 verifier 服务问题**、**多数（170/186/324/391…）是「陈旧 evidence_id 撞墙」harness 缺口**、只有少数接近能力天花板。这其实比"全是能力问题"更乐观——**很多条差一个确定性断环就能救**。

## 4. 下一步建议（核心：给「陈旧 evidence_id 撞墙」加断环）

**为什么 5 项修复没救起 gap 收尾**：它们治的是「search→open 断裂」（已好）和「verify 打回后换词重搜」（已好），但**没治「open_page 后拿错 evidence_id」这一新主导环**。update_state 被拒（changed finding requires visible original Evidence）与 read_evidence 被拒（不在 directory）共享同一根：**模型引用了它没在本次窗口读过/登记过的证据 ID**。

一个确定性 harness 新增（`_search_open_break` / `_illegal_read_break` 同款即可覆盖）：
1. 检测「连续 update_state 被 `changed finding requires visible original Evidence: eX` 拒绝」≥2。
2. guidance 点名：`open_page` 上一次返回的 evidence_id 是 **e45**（要读其原文构建 finding），**不要把旧 ID eX 塞进 evidence_findings**；evidence_findings 必须取自本次窗口 open_page / read_evidence 返回过、且亲眼见过原文的证据。
3. 把 update_state 的 `changed finding requires visible original Evidence` 错误文案补上合法做法：若要用新打开的证据，open_page 返回里有 evidence_id，就把该 evidence_id 对应的 finding 填进 evidence_findings。
4. （可选）`_illegal_read_break` 触发阈值 ≥3 降到 ≥2，并把扫描扩展到非法 update_state 串，扩大断环覆盖。

这条与 gap-worklist 正交、确定性、不影响验证通过侧的精度。**加上它后 30 轮验证转换率若能显著抬升（不止 266 一条），再考虑升级 100 轮重跑**；否则说明覆盖短板更接近能力层而非 harness 层，应转向 RL（实验2）。