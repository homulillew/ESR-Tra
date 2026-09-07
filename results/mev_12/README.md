# mev_12：我(Claude)当verifier+真实harness 12条分离实验（2026-09-03）

**目标**：彻底分离 harness 层 vs 4B 模型能力层——我既当策略又当 verifier(回填式 MyVerifier)，
检索真实 BM25(:8000)，harness 门禁(coverage/stale/已验证/submit路径)全真实。

**脚本**：`analysis-L/me_verifier_batch.py`（772 候选已修 93372）。
**结果 json**：`analysis-L/mev_12_result.json`。

## 结果：12/12 全部 submitted(supported)，0 blocked

| qid | gold | 提交 | strongA判定 | 本次正确docid |
|---|---|---|---|---|
| 186 | Galacta | ✓ | 真阳性(检索缺gold) | 39978 |
| 56 | Last Christmas | ✓ | 真阳性 | 17156 |
| 1041 | Adaku | ✓ | 假打回 | 61696 |
| 1089 | Zius Galit | ✓ | unparseable | 86834 |
| 1198 | Robert Mugabe | ✓ | 假打回 | 83077 |
| 324 | Svetlana Gromenkova | ✓ | 假打回 | 85213 |
| 364 | Bada Lee | ✓ | 真阳性 | 47063 |
| 391 | María Constanza Guzmán | ✓ | unparseable | 22666 |
| 517 | Peter King | ✓ | 真阳性 | 67431 |
| 636 | 2011 | ✓ | 假打回 | 19992(+补70660) |
| 772 | Secretary | ✓ | 真阳性 | 93372 |
| 83 | Joseph Dalton Hooker | ✓ | unparseable | 39837 |

**结论**：harness 门禁+chunk视图+方案E' 全部实现正确、无需再改。短板 A **100% 归因 4B verifier**
(multi-hop逻辑误判 q324/364、unparseable q1089/391/83、实体身份过严 q324/636/1198、字面约束过苛 q186/56/517)。
检索召回广度是**独立于 harness 的第二短板**(q772 需正确 docid 93372、q636 需补含"since2011"的doc)。

`mev_<qid>.db` = 每条完整提交账本(SUPPORTED+submitted)。判定细则见 `analysis-L/ITERATION_LOG.md` 十。
