# 服务器端编程模型提示：自动执行 ESR 2.1 前向验证

将下面“任务正文”完整交给**有服务器终端权限的编程 agent**。这是实验执行者指令，**不是被测 4B 的系统提示词**；不要把本文、历史分析、参考答案或预选证据注入 policy/auditor。

## 任务正文

你在已克隆的 `homulillew/ESR-Tra` 仓库中工作。目标是使用 `refactor/esr-state-2.1` 的新入口，完成可复现、有成本边界的真实 4B 前向验证，分析 gap 是否推进搜索。只做前向，不做 SFT/RL，不更换 state 架构，不通过增加题目专属提示词获得表面成功。

### 1. 先确认实现与资源，不要先猜环境

阅读 `docs/harness/{DESIGN,RUNBOOK,PROMPTS,VALIDATION}.md` 和 `src/esr_harness/{cli,prompts,protocol,runner,client,views}.py`。以当前代码和 `python -m esr_harness run --help` 为准。主入口必须是 `esr_harness`，不是 `esr_harness.v2`、`esr_grpo` 或 `analysis-L` 的旧驱动。

执行并记录 `git status --short`、`git branch --show-current`、`git rev-parse HEAD`、Python 与包版本、可用 GPU/显存/磁盘。不得覆盖未提交修改，不强推、不合并 main、不结束他人服务、不自动更改系统环境。需要修复时在新本地工作分支进行；没有额外授权不远程推送。精确修复先加测试，禁止减少断言掩盖问题。

优先使用用户已配置的非敏感变量：

| 变量 | 用途 |
|---|---|
| `ESR_MODEL_PATH` | 本地 Qwen3.5-4B 模型/tokenizer 目录 |
| `ESR_SERVED_MODEL` | 推理服务实际注册的 model 名称 |
| `ESR_POLICY_URL` | 兼容 chat/completions 的本地服务地址，含 `/v1` |
| `ESR_RETRIEVAL_URL` | 本地 BC+ 检索服务地址 |
| `ESR_DATASET` | BC+ JSONL；可包含标签，但随后必须生成无标签副本 |
| `ESR_MODEL_REVISION` | 实际模型快照/权重版本标识 |
| `ESR_INDEX_REVISION` | 实际语料、索引与检索配置标识 |
| `ESR_DEV_QIDS` | 可选：一行一个 qid 的已确定开发集清单 |
| `ESR_API_KEY` | 可选：只交给现有客户端，禁止打印、写日志或报告 |

变量缺失时，检查仓库配置、当前进程和用户指定目录；可有界检查常用挂载目录，不遍历全部磁盘、不输出进程命令中的秘密、不扫描密钥。确认模型/tokenizer/服务一致，不根据服务名字假装核实了权重 hash。先复用已有服务；没有服务时只用本机已安装框架及其实际 `--help` 配置启动，限制在可用且获准使用的 GPU，监听本地地址。不得自动下载大模型、整个语料或安装不明依赖；离线机器使用本地缓存。资源不足或关键路径无法确定，输出已执行步骤与缺失项并停止，不捏造路径或伪造结果。

### 2. 冻结运行条件与数据边界

在新目录 `runs/forward_validation/<UTC时间>_<git短SHA>/` 保存 `manifest.json`。记录 git SHA/dirty 状态、提示版本、四种实际 system hash、模型/索引/tokenizer 版本、服务/包配置、thinking、温度、预算、样本清单及数据 SHA256。版本填 `unspecified` 的实验不能宣称可复现。

只复制 `query_id/qid/id` 和 `query/question` 到 `questions_only.jsonl`，拒绝重复或缺失 ID。不要打印或读取 gold 内容来安排搜索。actor、auditor、检索 query 生成均只接收原题及合法观察；参考答案只允许在 rollout 结束后的独立评估流程使用。不要读取 q324 示范的答案、预选 docid 或历史成功查询来引导本次 rollout。

默认最多 **8 道开发题 × 4 个配置 = 32 个真实 episode**，并发 1，不自动扩到 100/830 题。优先使用 `ESR_DEV_QIDS`；没有独立开发集时，用 `SHA256("esr-forward-dev-v1:" + qid)` 排序选择前 8 个 ID，并明确这只是开发性诊断，不能声称这些题从未用于历史调参。选择过程仅依赖 ID，不依赖答案、成功率或 gold doc。保存顺序与清单。少于 8 题就使用全部可用题并说明。

默认四个配置：`baseline/off`、`esr/off`、`esr/hard`、`esr/soft`。同题同源、同 4B、同索引、同 top-k、同窗口和总生成预算；auditor 默认与 policy 使用同一 4B 服务但独立新上下文。不要用强模型代替在线 auditor。策略 thinking 开、temperature=0.6；auditor thinking 关、temperature=0.0，均按 CLI 显式记录。当前 CLI 没有模型采样 seed 参数，不添加不存在的 `--seed`；ID 选择的确定性不等于 GPU 采样可完全复现。每臂一次即可，暂不做三种子统计。

预算起点：max_actions=64、context=32768、policy output=2048、audit output=2048、combined completion=24000、top-k=5、view_chars=8000、max_pending=4。全部 32 局名义上限是 768000 个 completion token，包含审核；实际输入 token、保守收费与超限服务另记。若服务器不支持该窗口，**在首个 episode 前**统一调低所有臂并记录，不能只给失败臂加预算。给每个真实 episode 加 15 分钟墙钟上限；超时保留账本和未结算请求，标记 `external_timeout`，不通过杀进程后的草稿打捞答案。该上限是资源限制，不是任务时长估计。

### 3. 先跑协议测试与最小服务联通

使用隔离环境。依赖已满足时不重复安装；需要安装则用可信且本地可用的安装来源，不升级整个训练栈。

```bash
python -m pip install -e '.[test,model]'
python -m pytest -q tests/harness_v21/test_prompt_profiles.py
python -m pytest -q
python -m esr_harness run --help
```

给 synthetic smoke 使用唯一新路径，执行 `python -m esr_harness smoke --store <新路径>`，随后只读 replay。smoke/HTTP fixture 的结果只标为协议通过，不是 4B/BC+ 分数。

确认本地模型返回文本 content、finish_reason 和真实 usage；tokenizer/chat template 与 thinking 参数匹配。检索 `/retrieve`、`/get_doc`、`/get_doc_chunks` 的请求以 `views.py` 为准，不照旧驱动猜 API。审核要保持 fresh context。固定且确定性索引才声明缓存；不确定时传 `--no-deterministic-retrieval`，禁止伪造固定版本让缓存生效。

检查真实构造的四种请求：baseline 无 update/verify/submit 指令与 focus 参数，ESR/off 无 verify 指令，hard/soft 结束规则不同；工具描述、schema 与实际参数校验一致。

### 4. 真实运行：先一题四臂，再完成剩余开发题

首个开发题四臂的真实运行就是首轮服务验收，不另外增加样本。运行每局后检查 summary、退出码和 ledger，完成所有臂再进入下一题。正常 abstain、unknown、预算耗尽是有效结果，不因不成功而丢样本或扩大预算。

以下命令是单题模板，变量必须来自前面的实际发现；不要把占位字符串直接发给服务。`ARM_ARGS` 对 baseline 取 `--mode baseline --audit-mode off`；其余为 `--mode esr --audit-mode off|hard|soft`。

```bash
# Bash；设置好 QID、RUN_DIR、ARM 和对应 ARM_ARGS 数组后运行。
mkdir -p "$RUN_DIR/$ARM"
timeout --signal=TERM --kill-after=30s 900s \
  python -m esr_harness run \
  --dataset "$RUN_DIR/questions_only.jsonl" --qid "$QID" \
  "${ARM_ARGS[@]}" \
  --policy-url "$ESR_POLICY_URL" --model "$ESR_SERVED_MODEL" \
  --model-revision "$ESR_MODEL_REVISION" --tokenizer "$ESR_MODEL_PATH" \
  --thinking --temperature 0.6 --no-audit-thinking \
  --retrieval-url "$ESR_RETRIEVAL_URL" --retrieval-revision "$ESR_INDEX_REVISION" \
  --max-actions 64 --max-context-tokens 32768 \
  --max-output-tokens 2048 --audit-max-output-tokens 2048 \
  --max-total-completion-tokens 24000 --search-top-k 5 --view-chars 8000 \
  --max-pending-views 4 --recent-actions 4 \
  --store "$RUN_DIR/$ARM/$QID.sqlite" \
  --output "$RUN_DIR/$ARM/$QID.summary.json"
```

可写一个很薄的本地 Python/subprocess 批跑器：参数化这些真实 CLI 命令，捕获 stdout/stderr、退出码和超时。它不能绕开 `esr_harness` 直接组装另一个 agent，也不能在请求里追加人工答案线索。运行状态追加到 `runs.jsonl`，每个 qid/arm 路径唯一；已有终态只读，不用 resume 重跑直到成功。

出现 tokenizer、账本一致性、模式指令串扰、证据未交付或 endpoint 系统性错误，立即暂停扩展。保留失败目录，先定位并补机制测试；修复后用新 SHA/新目录对受影响配置重跑，旧失败不得删除。语义错误不能用题号分支、关键词拒答守卫、删 requirement、改审核放行标准修复。

### 5. 分析与判分必须分离

每局检查：真实 `terminal.outcome`、提交答案、audit 标签、动作序列、各步 focus/need、finding delta、重复查询缓存、未读 hits、实际 exposure、反证作用域、生成/审核次数、测得 token、保守 charged token、unknown usage、时延。只读 replay 不得调用外部服务或改变原账本。

针对重复搜索，分别统计：完全相同请求、同文档新窗口、重复读取、相同命中池、focus 是否仍相同、是否出现新关系 finding。字符数/新文档数不是语义信息增益。人工审阅至少覆盖一次无进展搜索、一次候选修订或反证、一次正确读取后状态更新；若这些情形未自然出现，写“本批未观察到”，不编造。

最终答案 judge 在 rollout 后独立运行，先固定版本、输入与评分口径。不要使用旧 smoke substring judge 当正式准确率；不要以 supported/submitted 当 correct；不要把 abstain/超时/预算终态的 final_draft 算成提交。数值单位、别名和争议标签分别列明。没有可信 judge 就报告“未判分”，仍交付完整工程与成本分析，不临时把 gold 暴露给研究策略。审核误放/误拒需要独立人工或离线审核，不拿 gold 一致性代替证据充分性。

所有计划题目保留在分母；另分层报告基础设施失败和正常终态，给出端到端视角与正常完成子集。四臂同时比较实际 token/检索调用成本，不仅比较相同动作上限。8题诊断不作显著性或泛化结论，不因为新配置赢几题就宣布效果成立。

### 6. 交付文件与停止条件

交付到 RUN_DIR：

```text
manifest.json                 版本、硬件、提示hash、预算、数据清单
questions_only.jsonl          仅ID与原题
runs.jsonl                    每局计划/状态/退出码/超时
<arm>/<qid>.sqlite            原始账本
<arm>/<qid>.summary.json      正常产生的运行摘要
<arm>/<qid>.stdout.log        若批跑器保存
<arm>/<qid>.stderr.log
metrics.json                  含口径、分母、cost与缺失值
bad_cases.md                  观察→状态→gap→动作的断点和具体action ID
REPORT.md                     实测结论、限制、下一步最小修复
```

报告明确分开：协议测试通过、真实服务运行完成、语义审核结果、最终答题判分。只引用实际运行文件和 action/decision ID。不要公开完整私有证据、API密钥或服务令牌。可以记录精确环境，但报告中脱敏非必要个人路径。

完成最多32局与报告后停止，不自动训练、不扩大评测、不把开发题当全新测试。若资源/服务/可信判分缺失，就交付已完成的部分、具体缺失项与可复现错误；不得用模拟 trajectory 代替真实输出。
