# Agent Search Harness 自主研究轨迹

- [Discovery-01：逐条件核对提示，34 次请求后因截断停止](discovery-01/README.md)。三个已运行槽位完整保留；其余五槽 NOT_RUN。未观察到可用于晋级的准确率提升。
- [Discovery-02：检索入口提示，82 次请求完成四题对照](discovery-02/README.md)。基线与候选均为 2/4，干预实际交付但未解决目标难题。
- [Discovery-03：中间历史散文省略，基线第六次请求被服务方拒绝](discovery-03/README.md)。其余七槽未运行，候选效果尚未测试；此次中断不构成准确率比较。

各阶段均保存实际模型输入、输出、工具、原文、终态、预算与脱敏映射。新增方案在阶段之间冻结，失败不会被新运行覆盖。研究代码、计划和报告位于 [autonomous_search](../../experiments/autonomous_search/)。
