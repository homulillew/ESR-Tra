# 持续省略历史分析：两篇原论文复核

核查日期：2026-09-16。只读公开论文，无实验题、gold、judge 或候选设计。直接结论：两篇都测到 token 与准确率变化，但没有证明持续删除全部 assistant 分析可以普遍提升准确率。保持工具观察也不能保证无损。

## Agent-Omit：主要是训练后的自适应省略

[Agent-Omit: Adaptive Context Omission for Efficient LLM Agents，v2，2026-05-11](https://arxiv.org/html/2602.04284v2)；[版本记录](https://arxiv.org/abs/2602.04284)；[作者代码](https://github.com/usail-hkust/Agent-Omit)。首次提交为 2026-02-04。

模型学习输出空 thought，并用特殊命令选择删除历史 observation；因此不等同于保留全部工具观察、仅持续投影 assistant.content。Qwen3-4B/8B 经监督微调和强化学习，在 DeepSearch、WebShop、TextCraft、BabyAI、SciWorld 测试。表3中 Qwen3-8B WebShop 的 Pass@1 从6.93到23.57，平均token从16,741到8,764；这是训练后联合机制效果。

更直接的负结果：Thinking-Retention 在 DeepSearch 将token从8,281减至5,234，但Pass@1从17.75降至10.25。图3的逐轮干预发现，中间轮省略可提高准确率，初始或最终轮省略有害；这是选择位置的证据，不是持续全删实验。正文表2/表3的8B-RL DeepSearch数值26.56/24.56不一致，不能择一当稳定结果。其训练和rollout筛选成本不能忽略。

## Buried in Textual Debt：有与本问题直接对应的全删对照

[Buried in Textual Debt: Context Pruning with Visual Evidence Preservation for MLLM Agents，2026-08-24](https://arxiv.org/html/2608.22963v1)，§5.1、表1/3及附录C。

Delete All Reasoning 持续移除每个已完成分析段，保留原动作、工具观察和图像。在 GTA、V*、B-Jigsaw、VisualToolBench、MNMS 上，表1报告：

| 模型 | Full Trace平均准确率 | 全删分析 | SPARE选择性重建 |
|---|---:|---:|---:|
| Qwen3-VL-30B-A3B | 44.30 | 35.22 | 49.19 |
| Qwen3-VL-8B | 54.27 | 50.12 | 53.47 |
| Nemotron-Nano-VL-8B | 30.10 | 28.07 | 29.97 |

全删移除约99–100%分析token，却在三个模型平均分上均下降；30B的GTA单项50.85高于基线45.76，说明并非每任务都受损。SPARE通过同模型摘要与两种条件下的概率回放选择片段，再重建视觉证据；需要额外推理计算和token分布访问，不能等同于零调用删除。其37.89–64.58%删除率只计分析侧历史，不含观察、图像或总API成本。表3每轮摘要触发32.20低于模型自行触发42.37；附录的受控过时推测实验改善强制选择，但自由回答准确率未变。

## 解释边界

“不再生成分析”“删除已生成分析”“选择性删除并重建证据”是三个不同干预。Agent-Omit支持训练后选择性省略；第二篇直接显示固定全删的平均准确率风险，选择性方法也并非对全部模型优于原轨迹。多模态证据竞争与纯文本检索不同，不能将其准确率幅度直接迁移。此次无需扩展第三篇即可回答核心问题。
