# ESR v2 运行、迁移与前向验收

## 1. 安装及入口

Python >=3.10；核心代码只依赖标准库。模型 tokenizer 通过可选 transformers 加载。

```bash
python -m pip install -e '.[test,model]'
python -m pytest -q tests/harness_v2
python -m esr_harness --help
```

无需安装时，CPU 核心可以用 `PYTHONPATH=src python -m esr_harness smoke`。
正式在线运行需提供**与服务端相同的 tokenizer/chat template**，不以固定 token/char 比例替代。
Qwen 的 thinking/parser 配置需与服务端匹配；客户端不静默删除不受支持的参数。
日志保存服务端原始响应；解析允许完整 JSON、单一代码围栏或完整前导 `<think>...</think>`，
不会通过正则从任意文本中捞出“最后一个看起来像答案的 JSON”。

## 2. CPU 机械验收

```bash
python -m esr_harness smoke --store /tmp/esr-v2-smoke.sqlite
python -m esr_harness replay /tmp/esr-v2-smoke.sqlite --export /tmp/esr-v2-smoke.json
```

该 fixture 为虚构赛事：先误把中间实体 Alex 当目标，审核给出反证，改成 Taylor，重新审核并提交。
预期 7 个动作、2 次 audit、1 个真正的 claim repair。没有 LLM，不代表模型已学会修复。

## 3. 真实 4B 单题

假设服务已启动；此仓库不改动原服务器进程。下列端口／模型名／路径应使用实际部署值。
服务鉴权需要时，通过 `ESR_API_KEY` 环境变量提供；不要写入仓库。

```bash
export POLICY_URL=http://127.0.0.1:8005/v1
export MODEL=Qwen3.5-4B
export TOKENIZER=/path/to/Qwen3.5-4B
export QA=/path/to/bcplus.jsonl

python -m esr_harness run \
  --dataset "$QA" --qid 324 \
  --mode esr --audit-mode hard \
  --policy-url "$POLICY_URL" --model "$MODEL" \
  --model-revision PINNED_MODEL_REVISION --tokenizer "$TOKENIZER" \
  --retrieval-url http://127.0.0.1:8000 --retrieval-revision PINNED_INDEX_REVISION \
  --thinking --no-audit-thinking \
  --max-actions 64 --max-context-tokens 32768 \
  --max-output-tokens 2048 --audit-max-output-tokens 2048 \
  --max-total-completion-tokens 24000 \
  --store runs/harness-v2/324-hard.sqlite
```

只有 question/query 从数据行进入任务；answer、gold_docids、evidence_docids 不进入请求。
同 qid 重复出现会报错，而不是最后一行静默覆盖。

每题一个新 SQLite 文件；summary 默认写在同目录 `.summary.json`。使用相同参数加 `--resume`
可以恢复未结束 episode。question、配置和 manifest 不一致时拒绝恢复，不修改旧账本。
正常 budget_exhausted 不伪装成 API error，也不自动打捞候选当最终答案。

同一 4B 默认兼作 auditor；两个角色不共享会话。异模型审核需要同时提供
`--audit-model` 与匹配的 `--audit-tokenizer`，单独记录成本，仅用于诊断／校准。

## 4. 前向实验三臂

先只比较同一个 4B、同一索引、同样 view/上下文/生成预算：

| 臂 | CLI 关键参数 |
|---|---|
| Baseline | `--mode baseline --audit-mode off` |
| ESR hard | `--mode esr --audit-mode hard` |
| ESR soft | `--mode esr --audit-mode soft` |

每臂使用不同 store，不复用 state。之后才增加 ESR off 以隔离状态本身收益。
这里的 `off` 是实际不调用审核；**未实现隐藏 shadow audit 实验臂**。
检索器比较另开实验，不能同时换 retriever、窗口、模型、thinking 和门禁后只归因到 verifier。

先在旧 bad-case 开发集 smoke；再用新的固定开发子集跑 100 题。
冻结检索/index、tokenizer、模型声明和数据 split；不要把已反复分析的题当未见测试。
本轮不运行训练、不承诺新的 BC+ 成绩。

## 5. 指标与终态

summary 记录 terminal、动作尝试、工具计数、非法动作、文档/视图数、new_observed_chars、audit cache hit、
research_version、总 policy+audit prompt/completion tokens 和 unknown_usage_requests。

主要终态：submitted、abstained、budget_exhausted、generation_budget_exhausted、context_overflow、service_error。
Submitted 的 evidence_status 独立记录 supported/unknown/contradicted/unverified，不能混成一个“通过率”。

语义质量须用**独立、固定、经校准的最终 judge**评估。新版不调用旧子串 `ExactMatchJudge`，
但也不声称已替你完成正式判分。不要把名字出现率、提交率或 supported 率当正确率。
成本比较必须同时看输入/输出 tokens 和工具调用，不能只比相同 action 上限。
unknown usage 表示成本不完整；不得纳入精确 token 成本结论而不披露。

## 6. 迁移约束

历史 branch：`archive/pre-harness-v2-20260907`。
旧 `src/esr_grpo/`、`analysis-L/`、`results/` 不删除、不移动；历史 driver import 路径不改。
它们继续复现原实验，不代表新版生效。新实验统一从 `python -m esr_harness` 进入。

新旧协议在 ObservationView、claim state 和 audit 输出上是破坏性变化，因此不提供假兼容 wrapper。
旧 SQLite 必须只读查看，不能喂给 v2 resume；需要重跑一次真实检索生成 v2 views。
未来若需离线对照，只能按旧日志当时确实保存的实际观察重建，不能用重检索内容冒充原观察。

v2 没有采样时精确 token IDs、old logprobs 与训练 action spans；不能直接接旧 credit router。
先验收前向，再专门实现训练适配和 token 对齐测试。不要把 CPU stub 数据当训练质量证明。

## 7. 日志处理

SQLite/JSON 可能含完整检索原文及模型请求；它们可能涉及版权或私密语料。
默认只写本地，不自动上传运行轨迹到 GitHub；分享前按数据许可检查。
只读 replay 可导出完整记录，且禁止覆盖原 SQLite。
一个 episode 只跑一个进程；并发实验用独立 store。
