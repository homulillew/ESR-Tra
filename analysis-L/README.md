# 实验1 Bad Case 分析

本文件夹存放实验1（100条扩测）的 bad case 分析报告与诊断工具。

## 结构

```
analysis/
├── HARNESS_WORK_CHECKLIST.md     # Harness 工作总账（修复回溯 + 协议对齐 + 后续使力方向）
├── RL_PRECHECK_HARNESS_LEGALITY.md  # RL前合规梳理（修正版）：冻结Harness契约+分层定性+真风险四类
├── HARNESS_QUERY_GATE_PRINCIPLES.md # query门控三态(格式/语义/策略)合规与取舍原则
├── BADCASE_BASELINE_100.md       # Baseline 83条错误提交解剖（A/B/C三类）
├── BADCASE_ESR_100.md            # ESR 100条分析（提交复核/未提交成因/工具轮数/max_turns）
├── baseline_badcases_list.tsv    # baseline 100条逐条分类清单
├── esr_nosubmitted_list.tsv      # ESR 未提交81条逐条清单（gap状态/轮数）
├── esr_submitted_llm_judge.json  # (LLM judge结果,因4B不稳定弃用,留档)
├── tools/
│   └── inspect_tail.py           # 诊断工具:看单条run动作序列尾部
└── README.md
```

## 报告要点速览

### Baseline（83错）
| 类别 | 数量 | 说明 |
|------|------|------|
| A.过程语言当答案 | 53 | 计划文本/系统状态复述;A1早期放弃(search miss→计划塞finish)9条,A2晚期44条 |
| B.纯实体错 | 30 | 真实检索/推理失败,19条open=0瞎猜 |
| C.近似对 | 1 | 577 "DN AGRAR" 裁剪 |

核心洞察:search→open断裂是4B通病(baseline亦有49条open=0)。

### ESR（81未提交+19提交）
| 结局 | 数量 | acc |
|------|------|-----|
| 提交答对(语义复核) | 17 | 89.5%提交精度 |
| 提交答错 | 2(真错) | 311/776 |
| 未提交 | 81 | 78条=verify打回gap解不掉死循环 |

核心洞察:覆盖短板不是"不找",是"干到位了却收不了尾"(gap收敛闭环缺失+max_turns=30)。提交侧ESR更省(11.8轮 vs BL 19.4)。

## 工具轮数对比(用户重点)
- 已提交:ESR 11.8轮/4.7search vs BL 19.4/12.1
- 双方都对7条:ESR 11.1轮 vs BL 12.9轮(略省但有方差)
- 全量:ESR 20.9轮(含verify 2.3) vs BL 19.4

## 关键行动项
1. **重跑max_turns=100对照**(ECHO/AREX用100-200轮,30轮对ESR不公平)
2. **gap收敛闭环引导**(harness确定性改动,类_search_open_break)
3. gap→检索桥,非法read死循环断环,verify服务不可用标记
4. 行动项2/3的落地进展与已修项详见 [HARNESS_WORK_CHECKLIST.md](HARNESS_WORK_CHECKLIST.md)。

## 数据源
- 明细: exp1_results/exp100_report.json
- 仓库: exp1_results/exp100_merged_{baseline,esr}/
