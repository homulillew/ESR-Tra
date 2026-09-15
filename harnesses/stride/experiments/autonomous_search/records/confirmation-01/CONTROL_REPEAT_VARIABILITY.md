# 同一首请求下的控制题输出变化

2026-09-15；仅使用 discovery-01 至 09 已完成的 q771/q778 控制槽、封存归档和现有判分。未新增 judge，未访问 confirmation-01 活动轨迹或保留的八题。本分析不改变当前 12 题复验的冻结规则。逐槽完整 SHA256、请求数、现有判分和机制事件见 `CONTROL_REPEAT_VARIABILITY.json`。

## 观察

36 个计划控制槽中，20 个实际运行，共 79 次策略请求；16 个因整轮提前停止而 NOT_RUN。未运行控制集中在 01/03/05/08，每轮四槽；不能把这些槽归为控制题本身的基础设施失败。实际运行的 20 槽中，18 槽提交且已有 judge 标为正确，2 槽未提交，没有实际控制槽基础设施失败，也没有未判分提交被推断为正确。

q771 的十个首请求 body SHA256 均为 `a61deeac7f2debefea800747f21cf59eb495c83b3fe63081feaef2c7a704fe3b`；q778 均为 `7c3b4de711393e1eb56749a873d6860c113e222b59f4a83f8c44136a147268b7`。实际请求均 temperature=0。每题十个首响应 body 哈希互不相同。为排除时间戳、响应 ID 和 tool call ID 自然变化，另对 content、reasoning_content 和按原顺序解析的函数名/arguments 作规范化哈希；每题仍为十种。

这说明在本次 API、模型标签与记录条件下，相同首请求字节和 temperature=0 没有得到逐内容一致的输出。它不定位服务内部原因，不证明特定随机采样实现，也不保证今后每次都不同。同一首请求哈希不表示后续整条请求轨迹相同。

每题十槽均为九次已有 judge 正确、一次未提交。第四轮 middle-history 两槽在 R4 确实删除了中间组散文，不能混入“所有实验机制均未执行”的描述；其余十八槽没有实际机制改动输入。只看未激活子集，每题仍是八次已有 judge 正确、一次未提交。所有实际运行封存文件哈希及 SQLite 链已复核；本次没有重做全部来源审阅，judge 正确不代替来源完整支持。

## 第九轮的归因限制

第九轮两个候选控制提交并已有 judge 标为正确，两个 baseline 均 model_budget 空答。四槽都未触发 read-only-explicit；首请求完全一致，而首响应已有不同散文与查询。q771 baseline 在 R2 读首段、R3 继续搜索、R4 FINAL 请求 read 被拒；q778 baseline R2 queries 类型错误未执行搜索，R3 改正后搜索，R4 FINAL 请求 read 被拒。候选来源支持已在独立控制审阅中确认，但这不能把未激活条件下的输出差异转化为机制贡献。

这些是跨轮开发记录的描述统计，不是预先随机抽样、同一程序版本的稳定成功率估计。除第九轮局部对照外，跨轮协议和代码版本有所变化；即便首请求相同，后续实现也不能一概视作相同。因此既不能用 18/20 估计可靠性置信界限，也不能据第九轮控制净增益宣称提点。冻结中的独立复验仍按原规则完成。

## 范围失误附注

记录 UTC：2026-09-15T14:06:22.953741+00:00。发生在 confirmation-01 冻结启动后：检查旧 RESULTS 的 judgments 数据类型时，脚本的 list 输出分支未先筛控制槽，意外输出旧开发题 q774/q775 的 judge rationale，其中包含标准答案信息。准确工具执行时刻未单独保留，此处给出发现后附注记录时间。未打开 gold 文件、保留八题或活动轨迹；该意外内容不进入本控制统计。该 agent 此后不承担 q774/q775 的机制或提示设计，不能宣称其后续设计仍完全未见标准答案。当前冻结代码与模型输入未因此改变。本文件不复述答案或 rationale。

## 实际运行槽

下表 success_existing_judge 仅指现有判分为正确；unsubmitted 指未提交。完整首请求和首响应哈希逐槽保存在 JSON，避免正文重复长哈希。

| Stage | Slot | Requests | Existing outcome | Actual input intervention |
|---|---|---:|---|---|
| 02 | q771-search-pivot-v1-r1 | 4 | success_existing_judge | False |
| 02 | q771-baseline-r1 | 4 | success_existing_judge | False |
| 02 | q778-baseline-r1 | 4 | success_existing_judge | False |
| 02 | q778-search-pivot-v1-r1 | 4 | success_existing_judge | False |
| 04 | q771-baseline-r1 | 4 | success_existing_judge | False |
| 04 | q771-middle-history-v1-r1 | 4 | success_existing_judge | True |
| 04 | q778-middle-history-v1-r1 | 4 | success_existing_judge | True |
| 04 | q778-baseline-r1 | 3 | success_existing_judge | False |
| 06 | q771-baseline-r1 | 4 | success_existing_judge | False |
| 06 | q771-relation-review-once-v1-r1 | 4 | success_existing_judge | False |
| 06 | q778-relation-review-once-v1-r1 | 4 | success_existing_judge | False |
| 06 | q778-baseline-r1 | 4 | success_existing_judge | False |
| 07 | q771-relation-review-memory-v1-r1 | 4 | success_existing_judge | False |
| 07 | q771-baseline-r1 | 4 | success_existing_judge | False |
| 07 | q778-baseline-r1 | 4 | success_existing_judge | False |
| 07 | q778-relation-review-memory-v1-r1 | 4 | success_existing_judge | False |
| 09 | q771-read-only-explicit-v1-r1 | 4 | success_existing_judge | False |
| 09 | q771-baseline-r1 | 4 | unsubmitted | False |
| 09 | q778-baseline-r1 | 4 | unsubmitted | False |
| 09 | q778-read-only-explicit-v1-r1 | 4 | success_existing_judge | False |
