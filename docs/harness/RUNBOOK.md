# Harness 2.1 运行与迁移

## 本地协议验收（不需要GPU）

```bash
python -m pip install -e '.[test]'
python -m pytest -q
python -m esr_harness smoke --store /tmp/esr21-smoke.sqlite
python -m esr_harness replay /tmp/esr21-smoke.sqlite
python -m esr_harness.schema /tmp/esr21-schemas
```

smoke为11动作的确定性脚本：两个来源、部分审核、一次重复query缓存、精确重读、答案提交。它不是模型能力成绩。

## 真实4B服务入口（本轮未执行）

```bash
python -m pip install -e '.[model]'
python -m esr_harness run \
  --dataset /path/to/bcplus.jsonl --qid 324 \
  --mode esr --audit-mode hard \
  --policy-url http://127.0.0.1:8005/v1 \
  --model Qwen3.5-4B --model-revision PINNED_REVISION \
  --tokenizer /path/to/Qwen3.5-4B \
  --retrieval-url http://127.0.0.1:8000 --retrieval-revision FIXED_INDEX \
  --max-actions 64 --max-context-tokens 32768 --max-output-tokens 2048 \
  --max-total-completion-tokens 24000 --max-pending-views 4 \
  --store runs/state21/q324-hard.sqlite
```

精确tokenizer/chat template必须匹配服务；模型/index revision是操作方声明，不是远程hash证明。policy默认thinking，auditor默认non-thinking（可显式修改）；二者新会话、共享总生成预算，默认同一4B endpoint。审计模式和模型/索引配置是实验条件，不混报。

`--no-deterministic-retrieval`关闭确定性假设；未声明固定retrieval revision也不缓存搜索。服务端实际更换索引/模型应开启新episode，不能复用旧记录。工具文本只能进入数据位置，不能执行页面指令。

## 兼容性

- 主入口使用2.1 delta/nullable answer/focus/finding/submit decision。旧全量claims和answer_kind参数被显式拒绝。
- `esr_harness.v2`为冻结实现；旧100项测试仅调整import，测试内容不弱化。
- root `replay`可以只读查看v2和2.1。`--resume`只接受匹配配置的2.1账本；没有自动迁移。
- 旧`analysis-L`/scripts/esr_grpo不会自动变成2.1。不要混用旧driver或reward router。
- JSONL loader只读取question/query，不把gold、gold_docids给模型。正式答案judge仍需单独固定。
- 账本可能含完整原文与模型响应，不要未经检查公开发布真实私有轨迹。API密钥只从环境变量读取。

## 对结果的解释

`submitted`不等于`correct`；`supported`是语义auditor在当前输入上的判断，不等于形式证明。soft保留unknown/contradicted；abstain和预算耗尽保留draft供诊断，不能计作答。

总生成用量同时报告observed completion和charged completion；unknown usage按最大请求上限占用。protocol/HTTP/容量失败不生成semantic gap。

## 开发准则

先加可复现的机制测试，再修代码；不添加qid专属规则、失败N次放行、关键词黑名单或凭命中答案名判supported。前向未通过真实校准前不开始信用算法扩展。

## 服务器自动验证入口

克隆 `refactor/esr-state-2.1` 分支后，将 [FORWARD_VALIDATION_PROMPT.md](FORWARD_VALIDATION_PROMPT.md) 交给服务器上的编程 agent。默认最多8道开发题、4个配置、并发1；它不是被测4B的系统提示词。

提示层现为 `research-2.1.1` / `atomic-2.1.1`，参见 [PROMPTS.md](PROMPTS.md)。提示变更后使用新账本，不对旧episode静默resume；State 2.1与ledger schema 3不变。
