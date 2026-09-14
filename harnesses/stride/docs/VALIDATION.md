# STRIDE a2 验证记录

版本 `0.1.0a2`，协议 `stride-search-2`。新包独立于旧 ESR，拟在基底 `a4926f3eeceda249817ef0cb93abb8e71d107e45` 上新增，不替换旧源码、实验或根 pyproject。环境和源码摘要见 [validation_manifest.json](validation_manifest.json)。

## 本轮实际执行

本机 Linux、Python 3.13.5。真实模型请求为 0，BC+ 与训练为 NOT_RUN；HTTP 测试仅访问 loopback fixture。历史私有自然轨迹未取得，本轮不是旧 BC+ 题目的复验。

| 项目 | 结果 |
|---|---|
| 原始 a1 基线测试 | 131 项通过；本轮最初运行 |
| 最新代码普通回归 | 178 passed in 9.74s |
| 同一套测试的最终覆盖验收 | 178 passed in 27.36s，0 失败、0 跳过 |
| 语句覆盖率 | 88.13%（1129/1281）；不是分支覆盖或语义正确率 |
| 三个核心反例在 a1/a2 上重放 | 原版 3 failed；新版 3 passed；见交付包 before_three/after_three 日志 |
| source compileall | PASS |
| 原生 HTTP 往返 | OpenAI-compatible 和 Anthropic，各覆盖便笺、纯文本修复、容量恢复，及原有 HTTP 测试 |
| CLI smoke | 三次脚本化决定、两次本地后端调用，submitted |
| 只读 replay | 与同局 smoke 报告相同，不发送请求 |
| Wheel 构建、独立目录安装与 smoke | PASS，确认导入来自 wheel_site |
| 冻结 cohort-fixture | 两局提交，无独立 judge，formal_accuracy=null |
| 六局恢复对照 | 完整运行；同代码每次只改变一个 flag；不计自然成绩 |
| 旧 ESR v2/v3/训练代码全集 | 未在本轮 source-only 工作区重跑，不称全仓通过 |
| Python 3.10 与远程 CI | 本地 3.10 未运行；CI 配置 3.10/3.13，远程结果另以实际 workflow 为准 |

多次 178 项运行是同一套测试，不相加。比原 131 项增加/展开 47 个实例，包括新机制、保留旧行为的消融与关键来源拒绝正向控制，不是 47 个 bug。

## 失败记录与环境边界

初始新增合同测试在旧代码上为 16 failed / 4 passed；实现后通过。第一次联合回归的一个旧容量断言与新恢复合同冲突，现改为预检 on/off 参数对照：关闭时保留旧 context_capacity 期待，开启时校验明确拒绝和未交付来源不可使用，而非弱化来源保护。

本轮运行环境发生重置后，从原交付包重建工作区，逐项 Git blob 哈希确认生产源码和测试与重置前一致，再运行上述最新回归。重置前原始临时日志没有冒充当前保留文件；交付包保存的是重建后实际日志，并额外重放三项原版失败/新版通过对照。

首次 shell 未安装包而直接运行模块曾得到 No module named stride_search；pytest 的 pythonpath 不会自动作用于 shell。后续显式 PYTHONPATH=src 检查源码 CLI，并独立安装 wheel 再检验。该环境错误不当作 harness bug。

## 六个单变量脚本场景

| 场景 | 关闭对应机制 | 开启 | 能说明什么 |
|---|---|---|---|
| FINAL 附带合法 notes | 3 决定后 model_budget | 同为 3 决定，submitted | 非关键错误不再连带阻塞合法独立终答 |
| 完整散文输出待修 | 4 决定，下一输入无原输出标记 | 4 决定，下一输入含标记 | 修复对象得到呈现；脚本固定答案，不能证明模型修复率提升 |
| 四个 6000 字符窗口 | 2 决定，context_capacity，零曝光 | 3 决定，明确撤下一个窗口，另三个交付后弃答 | 恢复路径存在，不代表更准或更省 |

三个开关默认开启，可独立关闭。六局不是完整 a1 对照。结果见 [a2_recovery_results.json](validation/a2_recovery_results.json)。

## 仍然严格的边界

关键错误不会被后续外围错误清除。未知 refs、未交付 anchors、超批量、畸形参数、关键读取与服务/身份/截断/完整性错误仍阻断；finish 必须最后，准确答案不自动改写，无免费补发。

修复预览有长度/hash、截断和容量省略标记，不是证据，不复制 provider thinking/signature，不注入为 system。被撤下结果完整存档但不交付，所有 native ID 都有回执；同范围重试复用快照。删除修复对象或撤下 payload 会被只读校验检测。最小合法请求仍放不下时明确失败。

## 可重复运行

从仓库根目录安装，再进入包目录；所有输出用新路径：

```bash
python -m pip install -e 'harnesses/stride[test]'
cd harnesses/stride
python -m pytest -q
python -m coverage run --source=stride_search -m pytest -q
python -m coverage report
python -m stride_search smoke --output /tmp/stride-a2-smoke-new
python -m stride_search replay --db /tmp/stride-a2-smoke-new/episode.sqlite
python -m stride_search cohort-fixture --output /tmp/stride-a2-cohort-new
python examples/recovery_comparison.py --output /tmp/stride-a2-recovery-new
```

后续还需供应商模板/计数校准、固定前缀模型续程、自然同预算配对与独立 judge。当前不声称 BC+ 准确率提高、工具轮数减少、语义蕴含正确、提示注入免疫或来源独立。
