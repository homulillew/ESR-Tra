# finish 字符串与整数答案合同

`string-integer-v1` 是公开的 answer 输入合同。它接受非空白字符串和 JSON 整数，将下游 `terminal.answer` 保持为字符串。它修复整数答案被字符串专用接口阻塞的问题，不代表模型自主改变了参数类型。

## 产品入口和迁移

正式 `stride-search run` 与 `stride-search schema` 默认启用新合同；`--answer-contract legacy` 保留旧字符串合同。Python API 的 `Harness(..., answer_contract="string-integer-v1")` 显式启用新合同；API 默认仍为 legacy，避免静默改变已有集成和历史重放。冻结的 cohort 入口继续遵守原计划，本轮不迁移旧 cohort。`SCHEMAS`、`validate` 和 `tools` 的默认模式也保留旧合同，新的模型 schema 和本地校验统一由 `answer_contract` 选择。

基础归档协议继续为 `stride-search-3`。新 episode 的 header 记录 `answer_contract`；历史边界切换调用 `set_answer_contract`，写入含边界轮次的事件。`Archive.report()` 返回当前有效合同，仍能读取此前 a3、a2、a1 档案。无需修改已有终态的 answer 类型或文本判分器。

为验收时通过正式 CLI 保持原部署设置，新增 `--temperature` 和 `--max-seconds` 参数，默认值分别保持原来的 0.2 和 900；本轮传入原运行的 0 和 1800。这两个参数不改变检索或预算策略。

## 输入与表示规则

模型看到的 answer schema 为 `type: ["string", "integer"]`，保留字符串的非空白、1–8000 字符约束，以及原回答/弃答 oneOf 分支。JSON Schema 会把某些浮点数视为数学整数，因此本地补充精确 Python 类型检查：只有 `type(value) is int` 才进入整数路径。`true`、`21.0`、`2.1e1`、null、对象和数组拒绝；这一语法区别同时写在工具说明中。

统一函数 `answer_text` 生成下游文本。字符串逐字符保留，不 strip、不补单位、不加引号；整数按标准十进制表示，数值不变。`-0` 经 JSON 解析为整数零，文本为 `0`，原始参数字节仍保存。转换结果仍受 8000 字符上限约束；过大的整数在转换前按位数界限拒绝，Python 自身的十进制解析/转换限制也转换为受控合同错误，不关闭运行时限制。当前 Python 默认整数十进制限制可低于 8000 字符；长编号应使用字符串。

例如，整数 `47` 对应终态文本 `"47"`；字符串 `"0012"`、`"29/02"`、`"21 years"` 和包含引号或空白的合法文本均原样保留。类型合法的错误整数仍按原值提交，系统不推断事实或修改答案。

新合同的成功终态增加最少的 `answer_representation` 元数据：规则版本、输入类型、`decimal` 或 `identity` 操作；整数另外记录原始 `input_value`。原生响应、工具 arguments 字符串、来源和 refs 不覆盖。转换后的文本继续检查 `answer_prefix`/`answer_suffix`；要求引号时，整数不会被自动补引号。来源交付、require_sources、finish 顺序、前序关键错误阻断和弃答规则保持不变。普通 assistant 文本不进入此路径。

## 本轮验收方案

基底为 `8238a19a98db143212ac22e85f4b5a6c529a202f`；建立后继分支前已核对远程无后续变化。旧资料基底为 `749c505110741d828c7f54fdfb865c37b19627b3`，原运行核心为 `5d7752be94a9d40aa757383d8899504bc0f81e81`。此前十六次字段反馈实验不重跑，旧报告、轨迹和正式 6/12 保持原样。

离线测试覆盖整数、字符串原样保留、拒绝边界、来源、显式格式、动作顺序、普通文本、SQLite/report/CLI replay/JSON 导出和原文本 judge 的本地入口。内容错误但类型合法的整数不会被纠正。另在私有副本中按旧合同恢复原 R3，再将原 R4 响应交给新执行路径；这是 recorded-action 验收，不算新模型成功。

在线阶段一从同一 R3 边界开始，新合同只改变 SYSTEM 中的答案表示说明、finish 工具说明和 answer 类型声明；原题、已读原文、句柄、缓存及离散计数不变。最多四次新请求，成功即停。阶段二仅在合法提交且离线来源核对通过后启动一次，从空 episode 通过正式 `cli.execute(run)` 路径执行最多十二次新请求。观察器只接入占账留档和外层停止循环，模型、CPU、参数解析、Config、新合同、执行和 report 使用产品代码。

两阶段总上限十六次，使用原持久总账，每次发送前原子占额；不重试，不探针，不调用付费 judge。每阶段按新的真实单调时钟观察 300 秒，HTTP 超时至多 180 秒且不超过局部剩余时间；原有有界 CPU 步骤可能跨过窗口，但不再启动下一步。不伪称恢复原历史耗时，不把局部上限写入模型提示或伪造原 harness 的 model_budget。

阶段一的自动进入条件保守地核对终态和已交付原文中的年龄表述，核对结果不进入策略提示，也不改变答案。最终报告再逐项审阅原始响应、规范化文本和引用。该核对不是官方判分。

```text
python -m stride_search schema --final
python -m stride_search run ... --temperature 0 --max-seconds 1800
python harnesses/stride/experiments/integer_answer/validate_live.py prepare --private-manifest <original-private-manifest> --output <new-private-preparation> --report <new-report>
python harnesses/stride/experiments/integer_answer/validate_live.py run --private-manifest <original-private-manifest> --output <new-private-run> --plan <frozen-plan>
```

凭证仅由本地进程环境 `ESR_API_KEY` 提供。计划、离线证据和最终脱敏结果位于 [report](report/)；完整 HTTP、SQLite 和逐轮记录保留在本地新运行目录，不重复公开原题或原文。
