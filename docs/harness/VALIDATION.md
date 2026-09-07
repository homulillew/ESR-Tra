# v2 验证记录与剩余验收

日期：2026-09-07；历史基线 commit：`040710279e591162d793883cd64f8b1ae424a759`。

## 已执行

在当前隔离环境 Python 3.13.5 中：

```text
python -m pytest -q tests/harness_v2
100 passed

python -m esr_harness smoke --store <fresh sqlite>
submitted / Taylor / supported / 7 actions / 2 audits
```

测试包含真实 localhost HTTP 请求的 CLI→retrieval→policy→audit→SQLite→replay 集成。
HTTP 服务端的策略、检索和审核响应是确定性 fixture，不是实际 vLLM/BC+ 服务。
该集成验证了同一 runner、独立审核上下文、7 policy+2 audit 的成本累计，
以及数据 answer/gold_docids 的 canary 没有进入请求或轨迹。

CI 配置覆盖 Python 3.10 与 3.13；**本地已执行的是 3.13.5，不能把配置等同于远程 CI 已通过**。
旧 esr_grpo 的测试未在本轮隔离环境重跑，旧源代码和训练实现也未修改。

## Bad-case 到回归的映射

以下是从旧案例提炼的**机制回归**，不是声称重新运行了对应 BC+ 题。

| 旧现象／参考案例 | v2 修复与测试 |
|---|---|
| q120 尾部证据超出旧 16k 前缀 | offset 全文窗口；本地 chunk fallback 可命中尾部；实际 span/hash 保存 |
| q170 未登记 ID 无法 read | read 任意本 episode 已返回 observation，不要求写 finding |
| q324/q364 等目标关系位置混淆 | target+必要条件显式表示；fresh atomic audit；合成目标关系修复 smoke；真实语义仍待 4B 校准 |
| q161/q1201 等 duplicate-open 掩护停滞 | 同文档可见区间并集诊断；重复 open 不重置停滞计数 |
| 无变化 update 导致无限重新 verify | research payload 幂等；输入 fingerprint 缓存；有限动作／生成预算 |
| gap 仅改措辞就“解决” | claim ID 稳定；改 reason 不解决；删除/替换 requirement 不记修复 |
| q1089/q391/q83 一类审核 JSON 失败 | 原始 Q/A/证据保留的 bounded retry；失败不创建语义 gap |
| q18/q591 等拒答被当 supported | typed abstain；target audit 区分作答与元陈述；soft 保留不支持标签而非伪造 supported |
| supported+gaps 被客户端抹掉 | 新 schema 无可覆盖的整体 supported；逐字段聚合、quote 检查 |
| 同 doc 新 query 的策略/审核视图不一致 | 每次实际 view 独立持久化；read/audit 不重建检索视图 |
| baseline 死 read、ESR finish 绕过 | 单 schema，按模式白名单分发；baseline read 可用；ESR finish 不可用 |
| 长上下文静默裁掉新证据 | pending 视图保护；真实 tokenizer 检查；无法容纳则 typed overflow |
| 轨迹污染、错误标签泄漏、重复 qid 覆盖 | 独立 store，header 固定；loader 不返回标签；重复 qid 拒绝；完整 HTTP canary 测试 |

参考历史材料：
[32B 统一分析](../../results/local32b100_badcase_unified.md)、
[早期 ESR 100 题分析](../../analysis-L/BADCASE_ESR_100.md)、
[旧 verifier](../../src/esr_grpo/verification.py)、
[旧 environment](../../src/esr_grpo/environment.py)、
[旧 runtime](../../src/esr_grpo/rollout.py)。

## 机械不变量测试范围

实际视图一致性、文档身份检查、偏移边界、重叠片段合并、原文 quotation 验证、
no-op/cached audit、stale audit、pending consume/dismiss、无有效 state 的提交拦截、
hard/soft/off 标签、abstain、模式隔离、schema 多余参数和类型、
所有动作尝试受预算约束、JSON 最外层完整性与重复键拒绝、
审核错误不污染 state、HTTP 400/503 的 bounded 行为、缺 usage 显式标记、
secret 不写日志、SQLite 不可更新、hash-chain 校验、竞争 writer 检测、
写盘失败不修改内存、只读 replay、不修改 legacy schema、export 不覆盖 SQLite、
真实 HTTP 的端到端调用路径与标签隔离。

## 尚未验证，不能宣称完成的部分

* 没有连接原训练机实际 Qwen3.5-4B、Qwen3-32B 或 Echo/BM25 endpoint；没有新 BC+ 准确率。
* 没有使用真实 Qwen tokenizer 文件做服务端一致性实测；生产 CLI 强制提供 tokenizer，不能以 stub 替代验收。
* 没有重放每一个历史 SQLite；机制 fixture 不等于真实历史语义复现。
* 没有证明 auditor 引用正确句子就一定推理正确；没有实现确定性算术/日期求值器。
* 没有实施 SFT/RL，没有迁移训练 token span 或 credit estimator。

## 下一道门：真实 4B 前向校准

先冻结 model/tokenizer/index 声明，跑旧 bad-case 机制开发集；检查实际请求、view hashes 和错误分类。
然后做固定 (Q,A,observations) 的审核标注校准，分别统计误拒、误放、unsupported quotation 与 protocol error。
最后同预算比较 baseline / ESR-hard / ESR-soft，按题目配对统计准确率、完成率、预算耗尽和真实成本。

若系统层不变量仍失效，先加可复现测试后修代码；若只是语义错，应修改校准/数据/模型，
不要重新添加 qid 特判、gold 关键词或“失败 N 次即通过”的分支。
**前向验收达标以后，才进入训练适配。**
