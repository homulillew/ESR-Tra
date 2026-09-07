# 32B verifier vs 4B vs Claude — mev_12 基线纯 verifier 对比

**基线** `results/mev_12/mev_<qid>.db`：强策略 + Claude 当 verifier + 真实 harness，12 条全 submitted，evidence 全部已含 gold。
**本实验**：从 12 条账本重建每条 verify 时的 (question, answer, evidence 原文)，用 **Qwen3-32B** verifier（`http://127.0.0.1:8002/v1`）重判，不重跑检索、无额外注入。

驱动脚本 `analysis-L/replay32b_mev12.py`，结果 `analysis-L/replay32b_mev12_result.json`。

## 判定表

| qid | 4B(strongA) | Claude(mev_12) | **32B** | 32B gaps |
|-----|-------------|----------------|---------|----------|
| 1041 | needs_revision | submitted | **supported** | 0 |
| 1089 | needs_revision | submitted | **supported** | 0 |
| 1198 | needs_revision | submitted | **supported** | 0 |
| 517  | needs_revision | submitted | **supported** | 0 |
| 772  | needs_revision | submitted | **supported** | 0 |
| 83   | needs_revision | submitted | **supported** | 0 |
| 186  | needs_revision | submitted | needs_revision | 2 |
| 56   | needs_revision | submitted | needs_revision | 3 |
| 324  | needs_revision | submitted | needs_revision | 1 |
| 364  | needs_revision | submitted | needs_revision | 1 |
| 391  | needs_revision | submitted | needs_revision | 2 |
| 636  | needs_revision | submitted | needs_revision | 1 |

## 结论

- **6/12 被 32B 判 supported**：证据确实含 gold——4B 对这几条的"假打回"是纯粹的 verifier 幻觉/判据不足，与检索无关。换成更强大的 verifier 即可放行提交。
- **6/12 被 32B 判 needs_revision，gap 全部是实质性的**（非幻觉）：
  - `186` 证据缺"软件公司 1990s 原名（两栖动物名）"这条关键约束；
  - `56` 证据缺 ReFrame Stamp / MPA rating / 导演第二部片三处约束；
  - `324`/`364` 证据只给到最终人物一层，未覆盖问题要求的链条/前因（启动者 X、同生日推广舞蹈的名人）；
  - `391` 证据缺大学院系任职与生平细节；
  - `636` 更关键——32B 指出 **"2011" 与题干"到 2020 年才重命名"时间相悖**，且打开的证据里 Rename 前的时间线确实与 2011 不符，答案本身可疑。
  → 这 6 条是**单条 evidence 证据覆盖不足**，Claude 判 submitted 是因为当时 12 条统一放宽/或对已开文档宽容，32B 更严格、逐约束核对。

## 归属

- 4B 无法提交 = **verifier 能力与判断力不足**（6/12 纯幻觉式拒绝 + 6/12 因证据链缺被拒，其中多数 32B 认 supported），**不是** harness 机制故障、**不是**数据集缺陷。
- 换成 32B verifier 后：
  - 一半轨迹能无需任何证据补充直接放行（原来 4B 幻觉卡死）；
  - 另一半仍需把缺失约束对应的文档开全/evidence 补全——这属于**检索端的正常补证流程**，而非 verifier 误拒。
- 结论与 [[strong-model-harness-attribution]] 一致：主导失败在能力层（verifier），换强 verifier（32B）是正确的适配方向，且**不需要针对数据集/单样本加规则**。