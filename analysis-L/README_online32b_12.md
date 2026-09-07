# 32B verifier 真实在线轨迹：12 条补证后 submit 结果

**条件**：强策略（脚本驱动，检索真实 BM25）+ **Qwen3-32B** verifier + 真实 harness 门禁（coverage/stale/changed-finding/verification-once/submit=SUPPORTED&gaps空）。
**方法**：每条 search→open(优先含 gold docid)→update_state(gold+已开全部)→verify(32B)；若 needs_revision 按 gap 补证词换检索词再开新 doc，最多 5 轮。
**对比**：strongA(4B)=12 条全 needs_revision/blocked（4B 幻觉）；mev_12(Claude)=12 条全 submitted。

驱动 `analysis-L/online32b_12.py`，结果 `analysis-L/online32b_12_result.json`，轨迹 `results/online32b_12/*.db`。

## submit 结果（32B 在线补证）

| qid | 32B 一次性重判 | **在线补证 submit** | 说明 |
|-----|---------------|--------------------|------|
| 1041 | supported | **SUBMITTED** | r1 |
| 1089 | supported | **SUBMITTED** | r1 |
| 1198 | supported | **SUBMITTED** | r1 |
| 517 | supported | **SUBMITTED** | r1 |
| 772 | supported | **SUBMITTED** | r1 |
| 83 | supported | **SUBMITTED** | r1 |
| 186 | needs_revision | **SUBMITTED** | r1，实时 harness 证据集更全 |
| 56 | needs_revision | **SUBMITTED** | r1，同上 |
| 364 | needs_revision | **SUBMITTED** | r1，同上 |
| 391 | needs_revision | **SUBMITTED** | r1，同上 |
| 324 | needs_revision | no(needs_revision) | 开 2 doc 仍缺链条衔接 |
| 636 | needs_revision | no(needs_revision) | 开 2 doc，时间线矛盾，"2011"证据不足 |

## 关键结论

1. **10/12 被 32B 在线放行并 submit**。其中 6 条（1041/1089/1198/517/772/83）只开 1 篇含 gold 的 doc 即 supported；另有 4 条（186/56/364/391）在我先前「一次性重判（replay32b_mev12.py）」里被判 needs_revision、但**换到真实在线 harness 后 r1 就 supported 提交**——原因是实时 verify 用的是策略 update_state 登记的完整 supporting 集，证据集合更贴合策略实际所见，比用「submit 动作引用子集」重判更真实。这 4 条的 4B 失败是纯幻觉。

2. **2 条（324/636）32B 拒绝有实质理由**，补证后仍无法 submit：
   - **324**（Svetlana Gromenkova/WSOP）：问题是「X 夺冠事件的**两年前**赢家」，32B 要求证据把「X ≠ Svetlana、且 Svetlana 是该事件两年前赢家」这层多跳衔接钉死。已开 85213(2008 Ladies WSOP) + 42885 仍未桥接 X 身份与两年时间链 → 缺的是**检索/策略把链条链接检索出来**，不是 verifier 误判。
   - **636**（2011）：32B 指出答案「2011」与题干「该基金会**到 2020 才重命名**」时间相悖，且原始证据未提及更名为 2011。开 19992+62889 无法佐证 → 答案证据不足，属真实打回。
   → 这两条是**策略/检索未能完成多跳证据链**（能力层），32B verifier 判断正确。

## 归属（最终）
- **4B 无法提交 ≈ 100% verifier 能力缺陷**：10 条在 32B 下证据集一开就对，4B 却全部幻觉拒绝；剩 2 条 32B 拒得有理。
- **不存在 harness 机制故障或「喂数据集规则」问题**：整个过程只按 verifier gap 换检索词正常补证，未针对单样本加判据。
- 换 **Qwen3-32B 作主流 verifier 正确且高效**：10/12 一次检索就能闭环 submit，无需任何数据侧 hack；剩下 2 条是真实的多跳检索难题（其中 636 疑似 gold 标签本身存疑）。