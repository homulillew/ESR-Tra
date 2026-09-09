# 决策与失败登记

## 共同工程修复

长问题初始 focus 超长、重读绕过 pending 上限均有离线复现；已添加回归测试。研究更新继续保持引用、ID、focus 等语义约束的原子性。有效语义更新附带不存在的 attempt_id 时，返回明确 warning，完整未关联 note 保留在动作参数，不制造尝试归属。

基线恢复完整的动作和工具返回历史。ESR 仍使用工作卡。两臂同样保留失败提案、遵守相同 provider 和预算。不使用会丢失旧证据正文的工作卡冒充普通多轮基线。

首次测试因系统默认临时目录权限失败：119 passed / 61 setup errors。改用新的仓库内临时目录后，进一步发现 Windows 系统代理将 localhost 请求送到上游；测试 fixture 单独设置 loopback no_proxy，未更改系统代理或冻结 v2 代码。修复后测试 193 passed，记录位于 runs/strong_api_esr/tests-03.txt。

## 真实合成验收，非 BC+ 成绩

20260909T090825717112Z_fixture_E-soft_synthetic-orin_0：12 动作，9 个非法，输出 246 token，正式提交失败。首个断点 a2：模型返回 action 与 docid 同级，缺少 arguments。a6 有合法候选与证据，之后重复格式错，审核没有发生。原始文本模式失败完整保留。

根因假设：provider 支持的结构化工具接口可以降低外层 JSON 维护负担。改动只将唯一契约映射成 Anthropic 原生 tools；不从散文抽动作，不补字段，不改变证据门禁。探针验证同一路由支持 tool_choice 和 tool_use。

20260909T091440949219Z_fixture_E-soft_synthetic-orin_0：8 动作，1 个非法，正式提交，policy 8 次 + fresh auditor 1 次，输入 19,022、输出 612 token。a4 同时引用和 dismiss o1，严格拒绝；a5 根据保留提案去掉冲突 dismiss，完成局部修复。a6 重读已引用视图，a7 fresh audit，a8 提交。这只支持接口可靠性的初步机制判断，不能从两次随机合成运行推导 BC+ 效果。

## 样本冻结

ID 哈希选择 24 个候选，排除 8 个历史题并检查四词 shingle 近重复；未根据答案、gold docid 或 ESR 结果排序。确认集已锁定为 9 题，prior 分层实际 1 易 / 5 中 / 3 难。其余 15 题为 pilot 池，prior 5 中 / 10 难。结构规则识别不到多桥接的题不保证真正简单；后续开发集用 baseline pilot 校准。确认集内容未向开发上下文展示，不为追求 3/3/3 换题。

## 实际执行边界

默认使用 CPU 上新建的 SQLite FTS5 BM25 完整语料索引。索引完成标记和 corpus SHA256 已核对。不得把它写成下载的 Lucene 索引或稠密检索器。模型返回标识 glm-5.2，网关路由无法独立固定权重版本。thinking 参数未宣称已控制；真实请求省略该参数，各臂一致，保存实际响应字段。

第二组旧题运行显示：原 65,536 保守容量单位会在 baseline 真实输入仅 13,688 token 后阻止继续。计数探针 HTTP 200 只返回 `success`，不是计数服务。随后唯一一次长上下文合成探针成功，实测输入 130,069、输出 2 token。正式 pilot 之前，将各臂共同容量上限固定为 128,000，仍以 UTF-8 字节加 1,024 开销保守估计，且保留输出空间。该设置低于已观察的单次输入接受规模，但不宣称取得官方 tokenizer 或最大窗口认证。旧容量运行保留且不可与新容量直接归因比较。

第二组 E-off 在 a9/a10 同时引用和 dismiss 相同 ID。此前错误文字只陈述规则，未指出具体冲突集合；现在错误路径固定到 arguments.dismiss_observation_ids，并列出需要由模型移除的冲突 ID。状态在错误时仍完全不提交，不自动更正参数。
