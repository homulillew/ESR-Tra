# 本地 Qwen3-32B 标准评测（随机 100 条，ESR vs baseline，max_turns=100）

> 日期：2026-09-07 ｜ 脚本：`analysis-L/local32b_policy_drive.py` / `run_local32b_100.py` / `evaluate_local32b100.py`
> 数据落点：`results/local32b100/raw_results.jsonl`（200 行）、`stores/*.sqlite`、`eval_summary.json`、`eval_report.md`

## 做法

同一套 ESR/baseline 两臂流程，**策略与 verifier 都换成本地 Qwen3-32B**（端口 8002，TP=2，限长位变体窗口 40960）。`max_turns=100`。从 830 条池按 `seed=20260904` **随机抽 100 条（不排除原 12 条）**，每 `(qid, mode)` 独立全新 session + 独立子进程，离线 `ExactMatchJudge` 判分，运行期不给 gold。

## 结果

| 指标 | ESR | baseline |
|------|-----|----------|
| 提交率 | **47%**（47/100）| **100%**（100/100）|
| Accuracy（仅已提交）| **23%**（11/47）| 15%（15/100）|
| Accuracy（含未提交）| 11%（11/100）| **15%**（15/100）|
| 平均工具轮数 | 58.1 | 4.3（**≈13.5×**）|

**正确集合重叠**：双对 9，ESR-only 2（1007/266），baseline-only 6（1108/1226/1230/380/853/907）。

## 关键结论

1. **32B 策略下 ESR 相对 baseline 无净增益，反而含未提交准确率低于 baseline（11% vs 15%）**。这与 api12（强 api 策略，ESR ≥ baseline）形成**方向相反的对照**。
2. **提交精度的稳定器角色仍在**：ESR 已提交者中 23% 答对，高于 baseline 的 15%——「提交少但提交的更准」的语义成立。但**代价是 53% 的 ESR 局打满 100 轮不提交**（verify 门禁循环解不掉），这 53 条的努力全部归零，拖垮含未提交准确率。
3. **提交精度 23% 本身也被 32B verifier 的“拒绝式放行”稀释**：47 条已提交里 11 条是「证据不足/未提供/无法确认」类**拒绝措辞**答案，32B verifier 判定其为 supported（gaps 空）因而放行提交。32B 当 verifier 会认可“找不出答案”作为合规答案，这压低精度。
4. **轮数悬殊 13.5×**（58.1 vs 4.3）。32B 长轮次上限放大了 ESR 门禁循环的耗时：53 条打满 100 轮。
5. **max_turns 53 条 = “知道或努力过但交不出”**。baseline-only 6 条正确里，3 条（1226/853/907）ESR 打满 100 轮未提交——正确答案被 verify 门禁吞掉。

## 根因定性（32B 策略 + 32B verifier 下的现象）

- **不能归为 harness 缺陷**：本实验修掉了一个真 harness 问题（上下文裁剪在密集 escape-HTML 证据下把当前消息裁空导致"空对话 400"，4 条误报为 error，已在原始记录里归为 max_turns）。修复后 200 条无崩溃、无 error，只有能力/门禁行为。
- **主导现象是 32B 策略+verifier 的组合行为**：verifier 既过度严格（对置信答案纠缠不可解 gap 打满 100 轮），又在拒绝式答案上放行——两个方向的判据都偏离“提交正确实体”。这是**策略/verifier 能力与判据绑定**的问题，不是门禁或裁剪的机械缺陷。

## Caveat

- 32B 是**限长位变体**（窗口仅 40960，非官方 128K）。为防超窗，驱动器做了 token 估算裁剪（`EVIDENCE_CHAR_CAP`/`ACTION_EVIDENCE_CHARS`≈6000 字符、`MAX_CTX_TOKENS`≈30k）。裁剪会丢弃早期/长证据，对需要长历史多跳的样本（如碍于 dense HTML 的文档）收敛有影响。这属于 32B 本地窗口的现实约束，如实记录。
- 随机 100 与 api12 的 12 条有重叠（如 1007/130/211/266/393/538/932/963/963 等），但 api12 用 api 策略、本实验用 32B，不可直接比绝对值，仅能看方向。
- 判分敏感性与 api12 一致：宽松 ExactMatch 子串命中，对「拒绝式措辞 vs 实体」不同判会对「拒绝被放行」的条数敏感。

## bad case 深挖

逐局轨迹重建的失败分类见 **[local32b100_badcase_deepdive.md](local32b100_badcase_deepdive.md)**：53 打满轮的主因是**策略检索不收敛**（avg 仅 3.9 个 distinct query、52 次相邻重复搜索，43/53 gold 从未进证据，query 锚幻觉实体或超长直译）；提交错 36 里 **18 例是 verifier"拒绝式放行"**（把"证据不足/找不到"判 supported）。`supported ⇒ submit` 门禁 1:1 干净，瓶颈在策略检索与 verifier 类型判据。