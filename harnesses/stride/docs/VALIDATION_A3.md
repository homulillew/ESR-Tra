# STRIDE a3 验证记录

## 范围

版本 `0.1.0a3`，协议 `stride-search-3`，基于已发布 a2 `badc82df9bfabc374ded7e8cf1b281815c46be88`。本轮保持 CPU SQLite FTS5；没有 GPU、embedding、reranker、额外 Agent、训练或默认语义 verifier。

本地验收只使用合成小索引、fixture 模型和 loopback HTTP。没有生产 BC+ 索引、真实 q26 重放或付费模型调用。因此下面的通过结果证明协议/实现路径，不证明自然任务准确率提升或工具轮数下降。

## 本地验收结果

| 检查 | 结果 |
|---|---|
| a2 基线回归 | 178 项通过 |
| a3 最终回归 | **228 passed，0 failed，0 skipped** |
| 语句覆盖 | **90.54%（1340/1480 statements）**；不是分支覆盖或语义正确率 |
| 新合同反例 | a2 上 3 个期望的 a3 行为失败，a3 上通过：关键已交付原文跨裁剪保留、未打开历史搜索卡片 recall、命中位置摘录 |
| CPU SQL 等价 | 8 组自造查询与 q26 LocalIndex 的 SQL 查询/排序/snippet/score 规则一致 |
| CPU 文件只读 | 缺失库不创建、写入被 query_only 拒绝、查询前后索引文件字节不变 |
| 本地原生 HTTP＋CPU | OpenAI-compatible 与 Anthropic 各跑通 search → read → finish；实际 wire 可由 Archive 重建 |
| CLI | compileall、smoke、replay、diagnose、cohort-fixture 通过 |
| Wheel | 构建、独立目录安装和 smoke 通过；打包 Python 源与验收源码逐字节一致 |
| 真实模型 / BC+ / q26 | **NOT_RUN**；付费模型请求 0 |

本地环境中 SQLite 版本与历史 q26 运行环境可能不同；合成等价测试不能替代生产索引的实际排名核验。

## 四局单变量合成对照

`examples/cpu_evidence_comparison.py` 创建新的合成 SQLite，不读取生产 BC+。

| 机制 | 关闭 | 开启 | 正确解释 |
|---|---|---|---|
| 编译后精确缓存 | 2 次模型决定、2 次后端 | 2 次模型决定、1 次后端 | 只省相同编译表达式的 CPU 执行；没有省 policy 决定 |
| 有界原文保留 | 强制裁剪后最后输入没有 marker | 最后输入重新呈现已交付 marker | 原文连续性路径可用；会增加输入，不代表自然准确率提高 |

正式实验必须分别做单变量消融；不能把整包开启后的差值归给其中一个机制。

## 保留的严格边界

- 只有已经确认交付的 eN 才能进入原文保留区；后台快照或被容量预检撤下的结果不能被提升为来源。
- 历史 search 卡片仍是 navigation，不能直接进入 `finish.refs`；必须 `read` 得到 raw evidence。
- `find(ignore_case=true)` 是字面大小写不敏感匹配，不是别名、实体解析或语义搜索。
- 合法 eN 不代表其支持答案。错误答案仍可能引用合法窗口后 submitted；`semantic_status` 保持 `not_automatically_verified`，`formal_correct` 保持 null。
- 编译等价只说明适配器执行表达式相同，不证明两次搜索在研究上必然冗余。
- evidence shelf 按明确的最近首次交付顺序保留，不是重要性评分；超过数量或容量时仍会退出。

## 发布后的验收要求

GitHub Actions 应在 Python 3.10、3.13 上运行完整 pytest、smoke、replay、cohort-fixture，以及 a3 的 CPU 合成对照和 diagnose。远程 CI 状态必须以发布 commit 的实际 workflow 结果为准，不能复用 a2 的旧绿灯。

后续 q26 自然运行必须：固定远程 release SHA、确认包版本与协议、保留同一 CPU 生产索引和 query/ranking 规则、先审查持久预算授权，只运行一次自然 episode；不能将已知旧答案/查询/候选注入 policy。具体执行合同见 [CODEX_Q26_RETEST_PROMPT](CODEX_Q26_RETEST_PROMPT.md)。
