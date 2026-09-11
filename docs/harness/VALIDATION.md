# State 2.1 验证记录

日期：2026-09-08。审查基线：`6ee9c4a264cd80a50d8a15511c8ed80b39c763b6`。本次只实现与验证前向协议，不执行BC+、SFT或RL。

## 实际本地执行

在Python 3.13.5下：`python -m pytest -q`：**168 passed**。

- 冻结v2：100项原测试。仅改为versioned import和测试包相对导入，未删掉原断言。
- 2.1：68项测试，覆盖局部delta、不变字段、ID分配/退役、成对finding引用、未暴露引用拒绝、nullable answer、partial audit、focus不失效审核、finding变化失效、同候选修复与候选替换区分、已知反证、hard/soft/off/abstain。
- 搜索/上下文：固定请求缓存、top-k/query差异、索引声明冻结、focus失败阶段、推断父ID、独立purpose、精确重读、零近期历史时latest正文、正文去重、目录分页、容量准入、rank-before-position、ambiguous offset、尝试摘要作用域、预算最后一步、只读恢复。
- 客户端：未知成本保守预留、进程未结算请求恢复、audit结束预算、截断/无content、凭据不入账、非法quote、完整原输入保留重试、无效policy JSON仍有delivery receipt。
- 实际localhost HTTP集成：CLI → 检索/文档/chunk适配 → scripted policy/auditor → ledger/replay；11次policy、2次audit，65个fixture completion tokens。完全重复search只执行一次外部调用，整体两次retrieve。gold/文档标签canary未进入请求或账本。
- 当前导出JSON Schema经过Draft 2020-12语法检查和初始state/动作正反例检查；运行时仍有引用、作用域、quote和状态转移校验，不能只靠Schema证明正确。

CPU smoke完成11动作、2份证据、部分审核、一次缓存重复query、精确重读、最终提交。**这是脚本，不是小模型生成的轨迹。**

## 远程验证

分支CI配置在Python 3.10/3.13执行同一完整suite、smoke和replay，并保留源快照artifact。实际CI结论以对应commit的GitHub Actions状态为准，不把“已配置”写成“已通过”。

## 尚未证明

- 没有连接真实Qwen3.5-4B、BM25/index或运行新BC+样本。
- 没有声称重复搜索减少、通过率提高、语义审核正确率提高或性能达到论文数字。
- q324为历史原文支撑的事后设计推演，query命中和人工审核不冒充自然rollout；部分条件unknown不能全标supported。
- 暴露日志证明客户端请求/响应关联，不证明模型理解；语法、引用存在和蕴含是三个层级。
- 来源hash/单writer/hash-chain防意外改写，不是对任意恶意数据库所有者的安全证明。
- 实际RL sampler token/logprob/mask尚未实现，训练入口不迁移。

## 变更边界

main保持不动；新实现位于开发分支。`src/esr_grpo`与历史分析/结果未被改写。v2使用冻结包和只读schema分发，不覆盖旧SQLite。后续更改必须先给可复现机制测试，不增加qid例外和强制放行规则。
