# ESR v3 实际验证记录

## 2026-09-11 Windows 独立复验

基础分支远程核验为 `f67a902d3f08372cc4e1884e861b38e9638bc044`，独立工作分支 `research/esr-v3-auto-20260911T111515Z-f67a902`。[完整报告与覆盖表](iterations/20260911T111515Z_f67a902.md) 区分历史失败、代码修复和未执行实验。

| 本轮检查 | 实际结果 |
|---|---|
| 基础 v3 / 基础 v2+v3 | 128 / 228 通过，本轮实跑 |
| 最终 v2+v3 | **270 passed in 18.63s**；其中 v2 100、v3 170；0 失败、0 跳过 |
| 独立反例 | 25 个代码反例先失败后通过；另有 1 个测试输入违反既定 schema，记录后纠正 |
| `validate_v3.py --include-legacy` | PASS；源码在执行期间未变；6 个命令完成；SQLite 与导出文件保留且哈希复验通过 |
| 本地 HTTP 多工具及异常 | 成功、429、401、截断四种场景通过；日志无 fixture key；回放不发请求 |
| 冻结合成队列 | 8 局完整登记；4 提交、1 注入服务失败、3 NOT_RUN；15 次脚本化调用尝试、8 次内存检索调用 |
| 固定前缀与导出 | 实际 CLI 只读导出成功；缺失采样量的 `--require-rl` 按预期退出 1，未生成伪训练文件 |
| 真实模型 / BC+ / 训练 | **NOT_RUN**；本轮新增收费请求上限 0，实际请求 0 |

本轮环境为 Windows 10、Python 3.13.14、pytest 9.1.1、jsonschema 4.26.0。精确命令、原始失败、JUnit 和产物位于私有 `runs/v3_autonomous/20260911T111515Z_f67a902/`；公共报告只有合成与脱敏统计。

`this_on/off` 是机制接口的合成对照，正式准确率与正确完成耗时均为空；没有合格的无 ESR baseline 或 BC+ 独立判分结果。最终测试没有覆盖全仓其他训练代码，不能称为全仓通过。

以下保留基础实现时的 Linux 验证记录，数字与环境均属于历史轮次。

## 基础实现的历史记录

基底为用户指定的 `main@6ee9c4a264cd80a50d8a15511c8ed80b39c763b6`。新增独立包、六工具前向 CLI、SQLite 账本、HTTP 适配器、回放/导出、合成回归与三份主要文档。旧 v2/GRPO 源文件与历史结果没有修改。根 README 只加新入口说明；pyproject 增加 v3 入口、运行时 jsonschema 依赖和新测试发现路径。

| 检查 | 实际结果 |
|---|---|
| `pytest tests/harness_v3 -q` | **128 passed in 1.80s**，Python 3.13.5，Linux |
| compileall | 通过 |
| 六工具 schema 输出 | 通过 |
| 持久 SQLite smoke | 通过；3 次脚本化策略决定、2 次 fixture 检索，0 次真实模型请求 |
| 只读 replay | 事件链验证通过，终态可重现 |
| training export | 成功导出真实记录；缺少采样 token/logprob/span 时 `rl_ready=false` |
| 本地 HTTP 端到端 | 已包含在 128 项中；loopback 测试模型与检索协议，不连接外部服务 |
| wheel 构建 | `pip wheel . --no-deps --no-build-isolation` 通过，仅验证本地新包打包路径 |
| 真实 Qwen / 强 API / BC+ | **未执行** |
| 旧 `tests/harness_v2` 全集 | **本机未执行**，旧树未完整下载；新测试已命名空间隔离，后续应运行联合回归 |
| GRPO/SFT 优化器训练 | **未执行，当前也未实现完整训练桥接** |

完整命令、环境与源码 SHA256 位于 [validation/manifest.json](validation/manifest.json)，结果见 [pytest.log](validation/pytest.log)、[JUnit](validation/junit.xml)、[smoke.log](validation/smoke.log)、[replay.log](validation/replay.log)、[export.log](validation/export.log)。这些日志没有真实题目或付费 API 响应。

## 测试覆盖

参数层：add 不猜 ID，revise 目标类型，refs/旧字段互斥，读取入口互斥，空答案拒绝，重复 JSON key、NaN、布尔整数、独立 schema 对象。

来源层：实际响应后曝光、未交付新 o/c/d 不可同轮猜用、原文与段落、this 单页/多页/失败/关闭/修复延续/同响应冻结、重复选择保留 trace 而不增加独立来源。

状态层：requirement-only 清除旧解释、派生来源路径、依赖传播、独立事实保留、旧来源不被后补材料回填、原子多项修订、环路拒绝、A-B-A、退休 ID 不复用、失败写入不继续提交。

上下文层：容量失败不虚报交付、原生调用/结果成组保留、多页不因压缩获得 this、修订边界、未解决 requirement 保留而不展示旧 finding。

审核层：无草稿显式审核、空状态不远程空审、精确答案/来源匹配、审 A 交 B、字面引号、真实反馈边界、缓存、清草稿不洗否定、段落反证、自身意见不失效自身报告、格式修复有界、原包保留、跨 claim 来源拒绝、hard 与 diagnostic 分开。

执行层：末次直接提交、草稿不打捞、来源要求、缓存仍计 policy、SQLite 只读/并发 head/篡改/进程中断、拒绝在旧库新建 v3 表、URL 不接受嵌入凭证、日志不含 fixture API key、缺失采样信息拒绝 RL-ready。

## 开发过程中修复的具体问题

初次测试文件有一处参数化装饰器语法错误，修复后第一组为 82 项通过；第二组审核测试 103 项通过；随后持久性与 HTTP 组达到 124 项，再加入端点/旧库/反馈对象/未解条件回归，最终 128 项通过。

代码审查中修复：通过未修改旧节点形成的依赖环必须拒绝；覆盖检查键 `coverage` 不能因首字母 c 被当作 claim；局部审核不得借用另一 claim 的原文；审核自身新增的段落异议不得立刻破坏自身绑定；旧 v2 SQLite 不得被隐式加入 v3 表；反馈里的被审答案与当前草稿字符事实必须分开；没有 finding 的未解要求不能在新 header 消失。

这些是本轮新实现的研发记录，不是旧仓库自然轨迹中已经发生的全部 bug，不记为真实 benchmark 改善。

## 边界与下一步

当前代码是可运行的前向实现，不是仅有接口探针。它仍是 alpha：真实 provider 的 schema、chat template、token 用量与窗口策略尚需验收，历史检索为词面方法，SQLite 全状态快照存在存储放大，显式依赖不覆盖隐含推理。

真实模型实验必须另行授权请求预算，按 [ITERATION_PROMPT](ITERATION_PROMPT.md) 先固定前缀和正反对照，再自然配对。旧测试联合回归、跨 provider 接口、真实检索、性能与采样端接入不能用本轮 128 项测试替代。
