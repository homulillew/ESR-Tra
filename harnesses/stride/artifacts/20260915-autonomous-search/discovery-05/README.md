# 第五轮开发实验完整封存轨迹

本轮比较 baseline 与 once-prose-reset-v1，运行身份为冻结提交 `652f21d`。计划四题八槽，实际只运行 q775、q774 两题四槽；q771、q778 四个控制槽均为 NOT_RUN。这不是完整开发集或十二题独立复验。

q775 处理臂使用 16 次请求，提交 Akure；baseline 使用 15 次，提交 Akure (Nigeria)。q774 baseline 使用 16 次请求后弃答；处理臂在第 4 次模型响应后的第 17 次 CPU 检索发生 backend_failure，队列随即停止。该后端请求记录耗时约 104.151 秒，但原始错误没有保留 SQLite 底层原因，不能据此确定超时。离线复现不属于本目录原始实测轨迹。

本轮没有 judge，已提交答案不等于正确答案，不能报告完整配对准确率。合计 51 次 policy HTTP、0 次 judge；本次授权的 1000 次额度累计使用 224 次，剩余 776 次。cohort 保留 STOPPED 和四个 NOT_RUN，没有生成全阶段 POLICY_SEALED 或虚构判分。

本目录保留四槽原始请求、响应、工具调用、已交付原文和逐轮阅读视图。102 个 HTTP body 文件与私有原件逐字节一致；SQLite 仅脱敏部署身份并重建事件链，原始私有 seal 不变。PUBLICATION_CHECKS.json 保存发布核验结果，ARCHIVE_HEAD_MAP.json 保存事件链对应关系，MANIFEST.sha256.json 覆盖本目录除清单自身外的文件。

本目录不包含凭证、私有部署配置、预算数据库或标准答案数据库。发布过程未调用模型，也没有补跑中断查询。
