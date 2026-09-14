# STRIDE a3：12 题完整轨迹与评估

**6/12 正确（6 个正式提交全部 judge 判对，4 个预算耗尽，2 个弃答）。本批 489 次调用，累计剩余 449 次。**

先读 [完整批次分析](evaluation/BATCH_ANALYSIS.md) 与 [机器可读结果](evaluation/cases.json)。q788 名称判对，但条件解释存在证据矛盾；正式标签与证据审阅分别保留。

| 题号 | policy 调用 | 正式结果 | 交互分析 | 证据审阅 | 每轮原始请求与响应 |
| --- | ---: | --- | --- | --- | --- |
| 770 | 64 | model_budget | [分析](q770/INTERACTION_ANALYSIS.md) | [证据](q770/EVIDENCE_AUDIT.md) | [逐轮](q770/rounds/README.md) |
| 778 | 64 | model_budget | [分析](q778/INTERACTION_ANALYSIS.md) | [证据](q778/EVIDENCE_AUDIT.md) | [逐轮](q778/rounds/README.md) |
| 772 | 5 | judge 对 | [分析](q772/INTERACTION_ANALYSIS.md) | [证据](q772/EVIDENCE_AUDIT.md) | [逐轮](q772/rounds/README.md) |
| 774 | 64 | abstained | [分析](q774/INTERACTION_ANALYSIS.md) | [证据](q774/EVIDENCE_AUDIT.md) | [逐轮](q774/rounds/README.md) |
| 769 | 6 | judge 对 | [分析](q769/INTERACTION_ANALYSIS.md) | [证据](q769/EVIDENCE_AUDIT.md) | [逐轮](q769/rounds/README.md) |
| 775 | 64 | model_budget | [分析](q775/INTERACTION_ANALYSIS.md) | [证据](q775/EVIDENCE_AUDIT.md) | [逐轮](q775/rounds/README.md) |
| 786 | 64 | judge 对 | [分析](q786/INTERACTION_ANALYSIS.md) | [证据](q786/EVIDENCE_AUDIT.md) | [逐轮](q786/rounds/README.md) |
| 776 | 9 | judge 对 | [分析](q776/INTERACTION_ANALYSIS.md) | [证据](q776/EVIDENCE_AUDIT.md) | [逐轮](q776/rounds/README.md) |
| 771 | 3 | judge 对 | [分析](q771/INTERACTION_ANALYSIS.md) | [证据](q771/EVIDENCE_AUDIT.md) | [逐轮](q771/rounds/README.md) |
| 788 | 12 | judge 对 | [分析](q788/INTERACTION_ANALYSIS.md) | [证据](q788/EVIDENCE_AUDIT.md) | [逐轮](q788/rounds/README.md) |
| 793 | 64 | model_budget | [分析](q793/INTERACTION_ANALYSIS.md) | [证据](q793/EVIDENCE_AUDIT.md) | [逐轮](q793/rounds/README.md) |
| 794 | 64 | abstained | [分析](q794/INTERACTION_ANALYSIS.md) | [证据](q794/EVIDENCE_AUDIT.md) | [逐轮](q794/rounds/README.md) |

每题保留 episode.sqlite、完整 FULL_INTERACTION、逐轮 ROUND_ANALYSIS、原始 HTTP .body、查询实际编译与返回、可见性表、工具完整性表、文档与证据原文。逐题报告在 gold/judge 前封存，其 formal_correct=null 保持历史原貌；最终分数见 evaluation 与 judge。

[费用及额度](evaluation/summary.json) · [原始 judge](judge/judgments.json) · [运行前预算](cohort/budget-plan.json) · [gold 读取时间](cohort/judge-preparation/gold-access.json) · [源代码与 489 次请求核对](cohort/FINAL_SOURCE_TRACE_CHECKS.json)

公开 archive 只脱敏部署信息并重算事件哈希链；模型消息、工具结果、文档、证据和原始 HTTP 请求/响应正文保持相同。使用 [head 映射](ARCHIVE_HEAD_MAP.json) 对照私有封存与公开 archive；[文件变换记录](PUBLICATION_FILES.json) 说明脱敏范围。最终公开文件以根 MANIFEST.sha256.json 核验，SOURCE_FILE_HASHES 保存原始来源哈希。

全量生产索引、语料、未选 gold、凭据、虚拟环境与跨会话预算数据库不在发布包中。运行代码版本为 5d7752be94a9d40aa757383d8899504bc0f81e81；仓库本次提交保存实验材料，不改变该运行身份。

[GPT review task](GPT_REVIEW.md) | [Final notes and report errata](REPORT_ERRATA.md)
