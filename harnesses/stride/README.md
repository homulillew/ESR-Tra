# STRIDE 搜索 Harness

**0.1.0a3 / stride-search-3**：保留 a2 的非关键便笺失败隔离、短期待修输出视图和完整结果组容量预检，并新增只读 CPU FTS5 接入、检索器能力声明、编译查询诊断、有界已交付原文保留、历史搜索卡片恢复与命中位置摘录。详细见 [CPU_EVIDENCE_A3](docs/CPU_EVIDENCE_A3.md)。

STRIDE 是独立的读取优先单代理搜索框架，不继承 ESR 的 claim 图、pending、focus 许可、审核门禁或训练路由。程序负责原文、已读范围、工具回执、预算与恢复；模型负责查询、解释和明确提交。没有默认 auditor、额外总结模型、自动答案修正或训练。**当前仍没有真实 BC+ 性能提升证明。**

已完成 q26、q72、q661 的各一次自然运行及事后答案判分，三题均匹配基准答案，同时观察到引用支持不足。参见[三题脱敏分析](docs/THREE_CASE_REVIEW_A3.md)和[采集／判分工具](docs/TRACE_CAPTURE_A3.md)；这是开发案例记录，不是整体准确率评测。

完整 HTTP、SQLite 轨迹、原文证据、逐轮分析与 judge 结果已按用户授权整理至[三题完整资料](artifacts/20260914-three-case-a3/README.md)。让 GPT 分析过程问题并设计下一步实验时，可直接从[审阅任务](artifacts/20260914-three-case-a3/GPT_REVIEW.md)开始。

随后完成用户指定的 12 道难题，各一次自然运行，模型调用上限预先提高至 64。正式得分 6/12，本批共用 489 次 API 调用，累计剩余 449 次。参见[12 题分析](docs/HARD12_A3_REVIEW_20260914.md)、[全部轨迹与评估](artifacts/20260914-hard12-a3/README.md)及 [GPT 审阅任务](artifacts/20260914-hard12-a3/GPT_REVIEW.md)。其中 q778 是候选正确但提交类型错误，q788 是名称判对但解释存在证据矛盾；这些开发案例不代表总体性能。

## 安装与离线运行

```bash
python -m pip install -e 'harnesses/stride[test]'
cd harnesses/stride
python -m pytest -q
python -m stride_search smoke --output /tmp/stride-a3-smoke-new
python -m stride_search replay --db /tmp/stride-a3-smoke-new/episode.sqlite
python -m stride_search diagnose --db /tmp/stride-a3-smoke-new/episode.sqlite
python examples/cpu_evidence_comparison.py --output /tmp/stride-a3-cpu-new
```

`smoke` 和 CPU 对照均是脚本化协议验证，不是强模型或 BC+ 成绩。所有输出使用新路径，不覆盖旧实验。

## 工具与默认行为

| 工具 | 用途 | 关键边界 |
|---|---|---|
| `search` | 一次提出至多三个查询 | 返回导航；CPU 适配器明确暴露实际 OR/BM25 语义 |
| `read` | 从 dN 精确读范围，或恢复 eN 原窗口 | 只有实际交付的原文窗口可引用 |
| `find` | 文档内字面定位 | 默认大小写敏感；`ignore_case=true` 仍是字面匹配，不是语义检索 |
| `recall` | 检索已交付旧证据、已收到搜索卡片和便笺 | 词面导航，不自动成为证据 |
| `notes` | 可选研究便笺 | 不等于 verified fact，不是提交前置条件 |
| `finish` | 明确答案＋已交付 eN，或弃答 | 合法来源不等于语义蕴含；程序不补答案 |

默认 `evidence_shelf_size=3`：旧交互组退出后，可继续呈现最近三个不同且已确认交付的准确原文窗口；容量不足时整窗让步，不会把后台未交付材料提升为来源。该机制是可消融的上下文策略，不是“关键证据识别器”。

## CPU FTS5：保持现有 OR/BM25，不需要 GPU

真实运行可把 `--retrieval-url ...` 替换为：

```bash
--sqlite-index /private/bcplus/index.sqlite \
--index-id actual-frozen-index-label
```

索引必须已经包含 `metadata(identity/complete)`、`docs(docid/content/url)` 和 `search` FTS5 表。适配器只读，不重建、不修改语料。当前查询规则与 q26 的 LocalIndex 对齐：小写、正则提词、首次出现去重、各词 OR、SQLite `bm25(search)`、docid 同分排序。引号不形成短语过滤，`site:` 不形成域名过滤；这些限制会直接显示给 policy。

默认**不**启用编译后缓存；`--compiled-query-cache` 只复用同索引、同编译表达式、同 top_k 的结果，减少 CPU 后端工作，不减少生成重复 query 的 policy 决定。

## 有授权的真实单题运行

真实模型调用必须另有明确预算和凭证。示例：

```bash
stride-search run \
  --allow-network --accept-counter-estimate \
  --question-file /private/question.txt --db /private/runs/new-episode.sqlite \
  --model-api openai --base-url http://127.0.0.1:8000/v1 \
  --model served-model --model-revision frozen-deployment-label \
  --sqlite-index /private/index.sqlite --index-id actual-index-fingerprint \
  --counter utf8_bytes --context-limit 100000 --response-reserve 8192 \
  --max-model-calls 24 --max-backend-calls 60 --max-actions 80
```

`utf8_bytes` 不是 provider token 窗口，需要部署侧校准。认证值不写入账本；运行目录包含原题、原文与模型响应，必须保持私有。

### a2 恢复消融

```text
--strict-note-failure
--no-repair-context
--no-delivery-preflight
```

### a3 检索与上下文消融

```text
--hide-retriever-capabilities
--compiled-query-cache
--evidence-shelf-size 0
--no-recall-navigation
--prefix-recall-excerpts
```

一次实验应只改变一个主要机制；全部开启后的整系统变化不能归因于某一项。

## API

```python
from stride_search import Config, Harness
from stride_search.cpu_index import SQLiteFTS5

retriever = SQLiteFTS5('/private/index.sqlite', index_id='frozen-index')
h = Harness('question', retriever, path='/tmp/new-stride.sqlite',
            config=Config(max_model_calls=24))
try:
    terminal = h.run(model)
    report = h.archive.report()
finally:
    h.close()
    retriever.close()
```

## 文档

- [DESIGN](docs/DESIGN.md)：整体设计与安全边界。
- [RECOVERY_A2](docs/RECOVERY_A2.md)：a2 的恢复合同。
- [CPU_EVIDENCE_A3](docs/CPU_EVIDENCE_A3.md)：q26 bad case 驱动的 CPU/原文连续性迭代。
- [EXPERIMENTS](docs/EXPERIMENTS.md)：冻结对照与独立判分。
- [VALIDATION_A3](docs/VALIDATION_A3.md)：a3 实际验证与未执行项。

## 明确限制

当前支持固定文本语料，不支持浏览器点击、视觉页面、任意代码执行、流式响应、自动跨任务记忆、自动 resume 或模型训练。`recall` 仍是词面方法，便笺没有依赖撤销，合法 eN 也不保证支持答案。正确率只能由独立评测判定；本版本没有自动语义 verifier。
