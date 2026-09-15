# q778 固定前缀后的真实续程实验

本实验比较原通用错误反馈（A，`legacy`）与字段级错误反馈（B，`field`）对模型自主修正参数类型的影响。四槽顺序为 A1、B1、B2、A2，每槽独立重放 q778 的真实 R1–R4，从 R5 起发送新请求。每槽最多四次新模型尝试，总计最多十六次；成功或弃答后立即停止该槽，不补齐调用。

代码基于已审阅提交 `80c0868c0987bb83f07f6290a4ae33219c274e9a`，资料基底为 `749c505110741d828c7f54fdfb865c37b19627b3`，原运行核心为 `5d7752be94a9d40aa757383d8899504bc0f81e81`。远程原工作分支在建立后继分支前仍指向已审阅提交。产品核心和格式化器均不再改动，只新增真实续程入口及必要测试。

## 时间与预算

这是固定前缀条件下的新续程。历史 R4 边界的精确单调耗时不可得，本次不恢复该值，也不以 UTC 差值代替。每槽离线重放完成、真实适配器校验通过后，使用新的 `time.monotonic` 起点，采用相同的 300 秒局部观察窗口。

每个完整步骤前检查局部时间；HTTP 超时不超过 180 秒及局部剩余时间的较小者。步骤中原有 CPU 操作仍按原后端超时执行，因而已开始的完整步骤可能越过 300 秒，之后不再启动下一步。传输超时属于异常，停止整个队列。局部次数或时间上限只写实验状态，不调用 `_end`，不产生虚假的原模型预算终止事件。

原 Config 保持不变，包括 64 次模型调用、200 次动作、120 次后端调用、48000 输出额度和 1800 秒 harness 上限。R4 后模型可见余额仍为 60、196、113、47648，仍处于 RESEARCH 阶段；局部四次/300 秒上限不进入模型输入。原有持久总账在每次真正发送前原子占账，失败和未知请求也占额。离线读取时总账为 551/1000，实际在线余额另见运行报告。

## 输入控制与失败处理

A 首请求复现公开存档中的原 R5 字节。B 首请求只改变 R4 错误的工具回执 `message` 和 `control.feedback.message`。实际适配器生成的请求再次比较；实际首个 HTTP body 在占账发送前核对冻结哈希。后续各槽自然运行，持续采用本槽反馈模式。

原私有 manifest 必须匹配已发布的原文件哈希；真实 CPU 索引身份与前缀身份完全一致，因此原查询缓存键得以保留。新的查询交给真实只读 CPU 后端。模型服务地址来自原私有 manifest，凭证来自进程环境；首次及每次新响应都按原 `expected_response_model` 检查身份。无探针、重试、auditor 或 judge。HTTP、身份、截断、预算、完整性或后端异常停止队列，未启动槽保留 NOT_RUN。

离线 fixture 的预写回答仅验证工程行为。312 项历史测试、1134 组历史比较和旧 R5 复现记录是前一提交的证据；本轮实际验收见 [OFFLINE_ACCEPTANCE.json](OFFLINE_ACCEPTANCE.json)。在线效果必须以本轮新响应为准。

## 执行入口与记录

在仓库根目录设置 `PYTHONPATH=harnesses/stride/src`，使用原运行的 Python/SQLite 环境。以下参数均由本地实际路径提供；凭证通过 `ESR_API_KEY` 传入，不写入文件。

```text
python harnesses/stride/experiments/field_feedback/live_pilot.py prepare --private-manifest <original-private-manifest> --private-output <new-private-preparation-dir> --report <new-report-dir>
python -m pytest harnesses/stride/tests/test_field_feedback.py harnesses/stride/tests/test_field_feedback_prefix.py harnesses/stride/tests/test_field_feedback_live.py -q --basetemp=<new-private-test-dir>
python harnesses/stride/experiments/field_feedback/live_pilot.py run --plan harnesses/stride/experiments/field_feedback/live_report/PLAN.json --private-manifest <original-private-manifest> --output <new-private-run-dir>
```

本次执行前先提交冻结代码与计划；执行后只增加报告，不边看结果边调整实现。`PLAN.json` 及其哈希保存本次注册条件，旧 `report/` 中的 OFFLINE_ONLY/BLOCKED 文件保持原样。

每槽本地保存完整 `episode.sqlite`、`trajectory.jsonl`、真实 `http/*/request.body`、`response.body`、占账元数据、结束状态及完整内存状态。总账保留在原位置。公开报告只提供必要的新动作、结果与哈希，不重复上传原题、已交付原文或新完整 HTTP。

结构修正、答案信息保持和来源有效分别判断。弃答、只有普通文本或仍被拒绝的 finish 都不算成功恢复。本轮不产生新官方评测标签，原 12 题 6/12 和 q778 空答案保持不变。温度 0 不保证确定性；两次一臂的小样本仅支持局部判断。
