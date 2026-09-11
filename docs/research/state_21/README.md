# State 2.1 研究材料与实现索引

本目录归档会话中前面生成的分析文档。**originals文件按原字节保存**，其“未实现”“未推送”是当时状态，不是当前分支状态。当前可执行规范以[DESIGN.md](../../harness/DESIGN.md)、[RUNBOOK.md](../../harness/RUNBOOK.md)及测试为准。

## 原始文档

- [架构、上下文与训练理论复审](originals/ESR_v2_架构与训练理论复审_20260908.md)
- [架构与理论审计补充](originals/ESR_方案再审视_架构与理论审计_20260908.md)
- [State & Action 2.1 RFC](originals/ESR_4B_State_Action_RFC_2_1_20260908.md)
- [q324完整推演与State快照](originals/BCplus_q324_State_Action_Walkthrough.md)
- [q324结构化轨迹](originals/q324_state_action_walkthrough.json)
- [原RFC语法Schema](originals/ESR_state_action_2_1_RFC.schema.json)、[原示例](originals/ESR_state_action_2_1_examples.json)、[原语法检查](originals/schema_validation.json)

前期的4B研究综述与实验规划仍保留于本仓库`docs/research/ESR_GRPO_4B_RESEARCH_REVIEW.md`和`ESR_GRPO_4B_EXPERIMENT_PLAN.md`。这次不改变训练算法。

## 如何阅读

q324是基于真实材料的**事后协议推演**。拟定query没有实际在新harness中执行；指定命中关系和审核表是设计示例，不是4B实验、也不是无oracle自然rollout。仍有未证条件，不能为了演示成功而改成全supported。

早期研究文档中的论文/性能数字是历史研究记录，证据层级和受控条件需按原文复核。它们不成为本轮代码正确性或4B收益的证明。此次实现没有新增或重新验证论文性能主张；有界provenance加权/positive-only均未实现到新前向。

本轮收口内容：局部finding delta、单focus、按缺口组织检索尝试、精确已暴露证据、按内容审核缓存、候选作用域/冲突来源、可恢复工作卡。没有知识图谱、新planner、过程reward或强模型在线依赖。
