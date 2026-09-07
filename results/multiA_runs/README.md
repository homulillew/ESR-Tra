# multiA 少样本多轮实验（2026-09-03）

**问题**：强策略单轮 12/12 卡死后，用户质疑"是不是检索轮次不足？假打回/真打回判据是什么？"
本实验**加轮次补证据**，回答"harness 是否真有问题、强策略全轨迹能否完成任务"。

**脚本**：`/data1/ESR-GRPO-Code-L/analysis-L/multiA_drive.py`
- gap 驱动多轮：search → open(新doc) → update_state(answer=gold, supporting=已见全) → verify
- 用 `COMPLEMENT_QUERIES` 针对量化 MISS 的约束补检索词，最多 6 轮/条
- 真实 BM25(:8000) + 真实 4B verifier(:8005 Qwen3.5-4B)
- 跑 q324/186/364/636

**结果**：**4/4 全 needs_revision → 0 提交，但每条都 open 6 篇 doc、5 次 verify、约束链基本全覆盖。**

**金证据**（证明根因不是检索不足）：
- q324（Svetlana Gromenkova）约束 5/5 HIT：verify#5 rationale "问题描述的 X 是 Vanessa Hellebuyck"——
  verifier 认对 X=Vanessa(2010) 却把答案误判为应是 X 本身，而非"两年前的冠军"=Svetlana(2008,gold)。
  → **multi-hop 逻辑链"返回第几环"理解错，与检索无关**
- q364（Bada Lee）6 次 rationale 同一错："答案是原成员但题目问后者"，而 Bada Lee 就是后者。
- q186/636：补满后 verifier 转向强求不可满足的字面约束（"早期名称不同"/"forerunner 身份"/"更名年份"）。

**归因升级**：harness 门禁正常（无 fake→supported）；单轮卡死确有检索不足成分（约束 2-5/5 命中），
但**多轮补足证据后仍 4/4 卡死 → 根因是 4B verifier 对 multi-hop 复合链的理解缺陷**。
仅补检索救不了 multi-hop 误判。修复方向：确定性约束核验兜底 submit。

**文件**：`multiA_<qid>.sqlite` = 该条完整多轮轨迹账本；判定细则见 `analysis-L/ITERATION_LOG.md` 第八节。
