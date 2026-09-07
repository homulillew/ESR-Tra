# mev_pilot：我(Claude)当 verifier + 真实 harness 分离实验（2026-09-03）

**目标**：彻底分离 harness 层 vs 4B 模型能力层——我既当策略又当 verifier，检索真实 BM25(:8000)，harness 门禁全真实。

**方法**：`analysis-L/me_verifier_harness.py` 回填式 MyVerifier，verify 时导出 prompt 由我判，回填 verdict 进 env；
所有门禁(coverage/stale/已验证/submit路径)全真实。

**Pilot q324**：1 verify 即 SUPPORTED → submit 成功，outcome=SUBMITTED，6 turns，answer=Svetlana Gromenkova 正确提交。

**对照**：同 q324 在 multiA(4B verifier) 里约束 5/5 补满仍 needs_revision。→ **harness 门禁完美，卡死 100% 在 4B 裁判 multi-hop 逻辑缺陷。**

`mev_324.db` = 完整账本(SUPPORTED + 提交)。判定细则见 `analysis-L/ITERATION_LOG.md` 九。
