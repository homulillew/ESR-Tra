# STRIDE 搜索 Harness

**0.1.0a2 / stride-search-2**：新增非关键便笺失败隔离、短期待修输出视图和完整结果组容量预检，见 [恢复合同](docs/RECOVERY_A2.md)。

STRIDE 是一版独立的、读取优先的单代理搜索框架。它不继承 ESR 的 claim 图、pending、focus 许可、审核门禁或训练路由。目标是通过减少不必要的状态维护、缩短研究到提交的路径，改善固定强模型的准确率—成本表现；**这一任务效果尚未获得真实 BC+ 实验验证**。

程序负责保存原文、记录已读范围、恢复旧材料、维护明确预算与工具配对；模型负责选择查询、解释证据和明确提交。没有默认 auditor、额外摘要模型、自动答案修正或训练。

## 安装与离线运行

从仓库根目录：

```bash
python -m pip install -e 'harnesses/stride[test]'
cd harnesses/stride
python -m pytest -q
python -m stride_search smoke --output /tmp/stride-smoke-new
python -m stride_search replay --db /tmp/stride-smoke-new/episode.sqlite
python -m stride_search cohort-fixture --output /tmp/stride-cohort-new
```

所有输出必须使用新路径。`smoke` 的三次脚本化决定演示 search → read → finish 的可达性，不是强模型成功率；`cohort-fixture` 验证冻结队列和两臂统计，正式准确率在没有独立判分时保持空值。

## 工具与默认行为

| 工具 | 用途 | 关键边界 |
|---|---|---|
| `search` | 一次提出至多三个查询 | 返回导航，不自动抓取全文，不自动当作证据 |
| `read` | 从 dN 精确读范围，或恢复 eN 原窗口 | 引用句柄必须先交付；原文与字符偏移不可重写 |
| `find` | 文档内精确定位 | 位置与摘录只是导航，不自动变成可引用原文 |
| `recall` | 检索本局旧证据和便笺 | 词面重叠检索，不是语义召回保证 |
| `notes` | 按需保存／替换／删除小型研究便笺 | 不等于 verified facts，不是提交前置条件 |
| `finish` | 明确答案＋已交付来源，或弃答 | 不继承草稿、不补字符；不要求先写便笺或审核 |

同一次模型响应可声明多项基于已有信息的动作，默认最多四项。当前后端按顺序执行，不宣称实现多线程并行加速。`max_batch=1` 本身不是完全串行对照：还应把 `max_queries_per_search=1`，避免一个工具内部隐藏三个查询。

默认在原始预算内为最后一次决定预留 `finish`。如果 action slots 或输出预算先接近耗尽，也切入终答阶段。原始问题与已交付原文仍在；模型自行给出准确字符串或弃答，程序不捞答案。该规则可单独关闭做消融。

## 有授权的真实单题运行

真实模型调用必须另有明确预算和凭证。本示例不会自动启动服务、下载模型或发现密钥：

```bash
# 在本机已有的安全环境中设置 STRIDE_API_KEY；不要把密钥写入命令、仓库或报告。
stride-search run \
  --allow-network --accept-counter-estimate \
  --question-file /private/question.txt --db /private/runs/new-episode.sqlite \
  --model-api openai --base-url http://127.0.0.1:8000/v1 \
  --model served-model --model-revision frozen-deployment-label \
  --retrieval-url http://127.0.0.1:8001 --index-id actual-index-fingerprint \
  --counter utf8_bytes --context-limit 100000 --response-reserve 8192 \
  --max-model-calls 24 --max-backend-calls 60 --max-actions 80
```

**100000 在此示例中是 UTF-8 字节，不是 100K token。** 字节数与输出预留只是显式估计，不能证明服务端不会超窗。部署侧必须校准；`--accept-counter-estimate` 让这一局限显式化。OpenAI-compatible 可改用本地 HF chat template 估计，仍不能代替实际服务模板核验：

```bash
# 上述 run 参数改为：
# --counter hf_tokens --tokenizer /models/local-tokenizer \
# --context-limit 32768 --response-reserve 2048
```

原生 Anthropic Messages 使用 `--model-api anthropic`，基地址应是部署的 `/v1` 根，适配器追加 `/messages`，认证为标准 `x-api-key`。当前 HF 计数器不支持声称准确计算 Anthropic 消息模板。OpenAI 输出参数可显式选 `--output-parameter max_completion_tokens`；不进行失败后的自动接口降级。

所有模型、审核、代理的“隐藏调用”在本实现中为零，因为没有附加模型。实际 policy 尝试、后端尝试、usage 及未知值分别记录。没有价格配置时不生成货币成本。

三项恢复机制默认开启。对照开关：`--strict-note-failure`、`--no-repair-context`、`--no-delivery-preflight`。在相同总预算内分别测试，不调用额外模型。

安装后从包目录执行合成恢复对照：

```bash
python examples/recovery_comparison.py --output /tmp/stride-recovery-new
```

生成六局单变量脚本运行的实际请求与账本，没有自然任务判分。

## API

```python
from stride_search import Config, Harness
from stride_search.fixtures import smoke_corpus, smoke_model

h = Harness("Who was the first director of Lumen Observatory?", smoke_corpus(),
            path="/tmp/new-stride.sqlite", config=Config(max_model_calls=3))
try:
    terminal = h.run(smoke_model())
    report = h.archive.report()
finally:
    h.close()
```

正式部署把 fixture model/retriever 替换为 `OpenAIModel` / `AnthropicModel` 与 `EchoRetriever`。`LocalCorpus` 是小规模确定性词面检索器，**不是官方 BC+ BM25**，不用于替代正式全库检索对照。

## 文档

[设计与取舍](docs/DESIGN.md)解释为什么减少状态职责，而不是继续扩展 ESR；[实验合同](docs/EXPERIMENTS.md)定义同模型、同索引、同预算、完整分母和独立判分；[验证记录](docs/VALIDATION.md)区分本轮实跑、合成正反例和未测量项。

## 明确限制

当前支持固定语料的文本搜索，不支持浏览器点击、视觉页面、任意代码执行、流式响应、自动跨任务记忆、自动续跑或模型训练。只读 replay 不恢复执行；进程中断后不重发未知是否完成的调用。

来源合法不代表语义支持，正确率只能由独立评测判定。`notes` 仍可能写错或产生偏见，历史退出也可能丢失有价值的桥接线索。默认没有机制保证“更新后的信息一定被模型服从”。严格安全属性与待测行为收益分开。

运行目录含问题、原文和原始模型响应，应留在私有目录；不要推送到公开仓库。认证头不进入账本，但原始任务数据不会自动脱敏。
