# ESR-GRPO 实现分析（文档第二十一节 Step 1 产出）

日期：2026-08-31
基于：`/data1/ESR-GRPO-Code/`（解压出的运行仓库）

> 重要前提：本仓库的 ESR 实现**已经基本完成**，并非从零开始。文档要求"阅读仓库→输出实现分析→然后实现"，而实际实现（状态机/上下文/credit/advantage）已存在于代码中，且我已通过无 GPU 的独立 bootstrap 验证了核心逻辑（8/8 单元测试通过 + 模拟 rollout 正确）。

---

## 1. 当前 Agent rollout 流程在哪里

- 主滚动循环：`verl/experimental/agent_loop/tool_agent_loop.py`
  - `ToolAgentLoop.run()`（:306）状态机：`PENDING → GENERATING → PROCESSING_TOOLS → INTERACTING → VERIFYING → TERMINATED`
  - ESR 模式由 `multi_turn.esr_enable=true / context_compression_method=esr_state` 触发，自动进入 ESR 路由（:205-229）
  - 配置：`verl/trainer/config/bcp_esr_grpo_1gpu.yaml`
- Convention rollout 管理：`verl/workers/rollout/sglang_rollout/sglang_rollout.py` + `async_sglang_server.py`（含 sglang 0.5.18 兼容补丁）

## 2. Search / Visit / Context 分别在哪里实现

- 工具：`verl/tools/esr_internal_tool.py`（search/open_page/read_evidence/verify_claims/submit_answer），通过 `esr_search_tool_config.yaml` 加载
- 检索服务：`examples/sglang_multiturn/browsecomp_retrieval_server.py`（BM25，端口 8000）
- Context 管理：`verl/experimental/agent_loop/esr_context.py`
  - `build_research_messages` / `render_research_view`（Research 视图，只暴露 Claim+Evidence 目录）
  - `build_verify_messages` / `render_verify_view`（Verify 视图，只含 Question+Claims+Referenced Raw Evidence）
  - `select_reconstruction_turns`（保留最近尾 + 含未处理 Evidence 的 turn，Context 压缩不丢 Evidence）

## 3. GRPO advantage 和 loss 在哪里计算

- advantage：`verl/trainer/ppo/core_algos.py:594-743` `@register_adv_est("esr_grpo") compute_esr_grpo_advantage`
  - 实现 `Ã = M_{i,t} · Z_i · max(A_i, 0)`
  - 组内 GRPO 归一化 → Z 门控（success∧legal∧passed）→ M 信用掩码广播到 action token
- 配置：`algorithm.adv_estimator=esr_grpo`，`esr_success_reward_threshold`，`esr_credit_granularity=action`
- metadata 传递：`verl/trainer/ppo/ray_trainer.py:253-268`（esr_response_action_ids / esr_credited_action_ids / esr_legal_submit / esr_final_verify_passed）
- reward：`verl/utils/reward_score/bc-p.py` `compute_score`（0/1.0 outcome，提取 submit_answer XML 与 ground_truth 比对）

## 4. 当前日志和 evaluation 在哪里

- ESR 结构化日志：`esr_state.py` ProvenanceLog（action/relation/answer provenance）+ `final_state_snapshot` + `debug_dict()`
- rollout 多 segment metadata 已通过 AgentLoopOutput.extra_fields 传出（tool_agent_loop.py:435-478）
- 评测数据/脚本：
  - 训练/验证 parquet：`data/browsecomp-plus-processed/esr_bcp_smoke.parquet` / `esr_bcp_test.parquet`（query/answer/prompt/reward_model）
  - BrowseComp-Plus 评测工具：`/data1/ESR-GRPO/ESR-GRPO/src/esr_grpo/browsecomp.py`（qrels/run/Accuracy/Evidence Recall）

## 5. ESR 需要修改的文件

**核心（已实现，无需重写）**：
- `verl/experimental/agent_loop/esr_state.py` — Evidence/TaskState/Claim/Gap/ESRStateManager/ProvenanceLog
- `verl/experimental/agent_loop/esr_context.py` — Research/Verify 视图与上下文重建
- `verl/experimental/agent_loop/esr_credit.py` — Final Support Chain + Gap Repair Chain trace
- `verl/experimental/agent_loop/tool_agent_loop.py` — ESR 路由、VERIFYING 状态、action ID 对齐
- `verl/trainer/ppo/core_algos.py` — esr_grpo advantage
- `verl/trainer/ppo/ray_trainer.py` — esr metadata 传递
- `verl/experimental/agent_loop/agent_loop.py` — esr_task_success、multi-segment metadata plumbing

**按要求新增/补充的模块化拆分（文档十七节建议 esr/ 结构，已对应实现）**：
| 文档建议 | 实际落点 |
|---|---|
| evidence_store | esr_state.py (RawEvidenceStore) |
| task_state | esr_state.py (TaskState/Claim/Gap) |
| state_manager | esr_state.py (ESRStateManager) |
| verifier | esr_context.py (verify view + apply_verification) |
| context_view | esr_context.py |
| provenance | esr_state.py (ProvenanceLog) |
| credit_trace | esr_credit.py |

## 6. 实验1和实验2分别准备怎么接入

**三种模式（文档十七/十八节）已由配置开关支持**：
- `baseline`（普通 Agent/AREX）：esr_enable=false，走 ECHO/普通 context
- `esr_grpo_baseline`（ESR 前向 + Vanilla GRPO）：esr_enable=true + adv_estimator 用 vanilla grpo（credit 默认关闭）
- `esr_grpo`（ESR 前向 + ESR-GRPO）：esr_enable=true + adv_estimator=esr_grpo

**实验1（验证 ESR Research State 有效性）**：基线只 rollout，无 ESR-credit 训练。用 `esr_simulated_rollout.py` + 小样本 rollout 对比 metrics（Accuracy/Evidence Recall/回合数/Gap 解决率等，见文档 5.3）。
**实验2（验证 ESR-GRPO credit）**：固定 ESR 前向，仅切换 `algorithm.adv_estimator`（vanilla grpo vs esr_grpo），对比 credit mask 质量 + 训练曲线（文档 13）。

---

## 当前阻塞点（必须解决才能推进真实训练）

1. **GPU 显存被占满**：2 块 H100 各被 `VLLM::Worker_TP0/TP1`（PID 638218/638219，各占 78482/81559 MiB）占满，仅剩 ~2.6GB。无法启动任何 verl/sglang 训练或 rollout。
2. **README 所述运行环境缺失**：README_ESR.md 指定 `/data/WSH/ESR-GRPO-Code/ESR-GRPO/.conda`（torch 2.13 / sglang 0.5.18 / conda），该路径在本机不存在。系统 Python 3.12 无 verl/sglang，且 omegaconf/antlr4 损坏。
3. **此仓库（verl 集成版）缺少数据/模型软链接**：`data/` 为空（README 期望 `data/Qwen3.5-4B`、`data/browsecomp-plus-processed/*.parquet`）。运行时资源实际在 `/data1/ESR-GRPO/`（models/Qwen--Qwen3.5-4B、caches/browsecomp_bm25_cache.pkl、BrowseComp-Plus/）。

**已通过无 GPU 验证的部分**：ESR 状态机 + credit trace 核心逻辑（8/8 单测通过，模拟 rollout 正确排除了无关 search 的 credit）。这属于文档实验流程图 Step 3 的核心验证，已达成。