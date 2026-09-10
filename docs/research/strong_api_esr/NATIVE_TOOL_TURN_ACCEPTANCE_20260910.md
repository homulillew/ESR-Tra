# 原生多工具执行的真实验收

2026-09-10，在线源码提交 `4a889fe467574f63464bcda6f1be93e7056566ea`。本阶段按照预登记执行一次合成流程和原开发集首题三臂对照，无追加采样，确认集未打开。四局的在线源码哈希一致，使用 Lanz-Medium 路由、相同 CPU 全语料检索配置；21 份在线响应均标识 `DeepSeek-V4-Flash-0731`。这仍是网关返回别名，不证明权重固定。

**本阶段验证了原生多工具可以完整执行并交付结果，未证明 ESR 的准确率、成本和速度三项目标。** 新协议与旧单调用版本不同；本阶段共同每局模型请求上限从 32 降为 16，旧结果仅供诊断，不能拼接成正式消融。

## 真实联通

现有合成 Orin Observatory 流程正式提交，审核 supported。5 次策略请求完成 search、open_page、update_state、verify_answer、submit_answer；5 项动作全部成功。

审核实际用了 2 次请求：第一次返回空报告对象，原有有界格式修复指出缺少 claims、coverage、target，第二次报告有效。保留两份原始响应，额外审核计入成本，没有把“动作错误数为 0”解释为所有模型输出首次均合法。该合成结果不是 BC+ 能力成绩。

合成流程合计 7 次模型请求、输入 16,719、输出 933 token，耗时 42.49 秒。未调用 BC+ 检索后端。

## 同题三臂对照

| 实验臂 | 正式独立判分 | policy / audit 请求 | 实际工具动作 | 实际检索后端请求 | 输入 / 输出 token | 正确完成耗时 |
|---|---|---:|---:|---:|---:|---:|
| B | 正确 | 3 / 0 | 4 | 3 | 8,643 / 503 | 40.27 秒 |
| E-off | 正确 | 5 / 0 | 5 | 2 | 24,455 / 1,222 | 30.15 秒 |
| E-soft | 正确 | 5 / 1 | 6 | 3 | 25,976 / 2,100 | 50.54 秒 |

三局均无工具执行错误、无未知用量、无传输重试。B 与 E-soft 各出现一次双检索响应，全部调用均执行，没有再整包拒绝或只执行第一项。E-off 本次只产生单调用。E-soft 完成了一次有效 fresh-context 审核并正式提交。

三局在线共 14 次模型请求，其中 policy 13、audit 1；输入 59,074、输出 3,825 token。离线 judge 另用 3 次请求，输入 1,200、输出 197 token；三次均按固定 BC+ 模板判正确。judge 只读取已经结束的提交，未看到实验臂和内部研究状态。

E-off 本题比 B 少一次后端请求、完成时间更短，但需要更多模型请求和 token。E-soft 比 B 使用更多模型请求和 token，耗时也更长。因此，当前结论是**接口可用性改善，ESR 总成本优势未成立**。单题全对有明显天花板，不能估计总体准确率提升；E-off 的耗时优势也不能外推到整套开发集。

## 交付与记账核对

对四局实际 provider body 和原始账本进行独立只读检查：共 18 份策略决策、20 项调用回执，两个多调用组。检查历史中出现的 18 项调用/结果配对，以及 4 次正文交付记录，未发现缺失或错配。终止动作保留回执，不为交付终止结果再请求模型。重读两份已引用正文的场景由两臂合成回归测试覆盖，本批真实策略未专门触发该场景。

本阶段总计 **24 次 API 请求**：合成 7、三臂在线 14、独立 judge 3。合计输入 76,993、输出 4,955 token，与全局账本增量一致。全历史请求从 1,065 增至 1,089；总上限仍为 1,403，当前检查点仍为 1,137，剩余 48。4 笔历史未知用量继续占预算，本阶段没有新增未知用量。

最新全局记账核对验证 1,085 份已结算响应、250 份导出，无结算差异或缺失导出。历史单独计数探针仍有一项全局请求不在 episode ledger 中，属于已保留的旧记录，不伪装成零。schema 扫描仍是此前 442 个受影响请求、49 个目录，没有给本阶段增加历史 ID 别名污染警告。

## 可复现命令与记录

以下是本阶段实际调用方式。每次运行都会新建实验目录并占原有预算；不覆盖旧局。

```powershell
$study = 'runs/strong_api_esr/20260909T085343Z'
$config = "$study/native_tool_validation_20260910.yaml"
python scripts/strong_api.py fixture --config $config
python scripts/strong_api.py run --config $config --questions "$study/dataset_splits/development.questions.jsonl" --qid 149 --category development --arms B E-off E-soft
python scripts/evaluate_strong_api.py --max-requests-per-answer 1 --run-dirs 20260910T042419572616Z_development_B_149_0 20260910T042500461490Z_development_E-off_149_0 20260910T042531583674Z_development_E-soft_149_0
python scripts/audit_strong_api_receipts.py
```

凭证通过原有私密输入读取，不写入命令、报告或 git。私有配置是当时公共配置的副本，只把每局请求上限收紧为 16。新增 judge 请求上限同时约束格式修复和传输重试；超限保留原响应并停止，不改变判分标准。

私有研究目录保存：

- `NATIVE_TOOL_VALIDATION_START_20260910.json`：运行前源码、预算、样本范围和停止条件。
- `native_tool_validation_20260910.yaml`：实际预算与模型配置。
- `native_tool_validation_checkpoint_20260910.json`、`native_tool_validation_per_run_20260910.csv`：逐局指标与成本。
- `native_tool_delivery_audit_20260910.json`：逐项结果和实际正文交付核对。
- `receipt_audit_20260910T043010669133Z.json`、`schema_audit_20260910T043007817244Z.json`。
- `20260910T042224343727Z_fixture_E-soft_synthetic-orin_0`。
- `20260910T042419572616Z_development_B_149_0`。
- `20260910T042500461490Z_development_E-off_149_0`。
- `20260910T042531583674Z_development_E-soft_149_0`。

各实验目录保留不可变 ledger、真实 provider 请求/响应、完整轨迹、用量、manifest、stdout/stderr、结束状态和独立判分。原暂停状态归档为 `PAUSE_NEW_EPISODES.archived-before-native-turn-validation-20260910.json`。

离线代码验收见[实现说明](NATIVE_TOOL_TURN_IMPLEMENTATION_20260910.md)。新增只读工具 `scripts/audit_native_tool_turns.py --run-dirs <实验目录...> --output <新文件>` 可重新核对实际原生消息；缺少匹配结果的合成负例能够被检测。

实际 rollout 完成后，补充了畸形原生消息防护：工具名称非字符串、input 非对象或内容块结构异常时，保留全部调用和未执行说明，不把非法原始块再次塞入 provider 请求。该防护通过合成反例验证，本批真实响应没有触发它；不为此重复消耗 API。真实结果仍明确归属上述 `4a889fe`，后续提交中的诊断工具、judge 请求上限和畸形消息防护不能冒充已在这四局全部触发验收。

最终完整回归 **264 项通过**，记录为 `tests_native_envelope_20260910T123446370.txt`。此前各次测试输出及临时测试数据均保留；没有通过删除失败或改写历史日志得到这个结果。

## 剩余问题

1. 未完成新协议下完整九题开发集和一次性确认集，未选择最终 ESR 候选，不能宣称研究目标完成。
2. 审核合成流程仍需要一次格式修复，应继续保留和统计这种成本；不能把 protocol 成功视为语义正确的充分证明。
3. 状态维护与工作卡输入仍增加强模型成本，需要在共同工具层固定后单独定位；本阶段没有同时修改 ESR 研究策略。
4. 不同 focus 的组合、状态修改与检索混合、审核与提交混合仍按明确规则拒绝。这些是当前执行范围，不是模型能力结论。
5. 未知返回的上下文预留是保守估计，不能保证任意后端输出一定可容纳。真实请求仍执行完整累计容量检查，超出时保留记录并停止扩展。

本阶段运行已结束，没有后台继续刷题。新协议保留为完成最小验收的工程版本；后续效果检验仍须遵守剩余预算和预登记阶段条件。
