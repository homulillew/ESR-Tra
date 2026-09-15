# Agent Search Harness 自主研究轨迹

- [Discovery-01：逐条件核对提示，34 次请求后因截断停止](discovery-01/README.md)。三个已运行槽位完整保留；其余五槽 NOT_RUN。未观察到可用于晋级的准确率提升。

各阶段均保存实际模型输入、输出、工具、原文、终态、预算与脱敏映射。新增方案在阶段之间冻结，失败不会被新运行覆盖。研究代码、计划和报告位于 [autonomous_search](../../experiments/autonomous_search/)。
