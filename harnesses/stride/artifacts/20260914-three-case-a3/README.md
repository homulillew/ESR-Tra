# STRIDE a3：三题完整轨迹与判分

本目录公开 q26、q72、q661 各一次自然运行的完整轨迹、原文证据、逐轮分析和事后答案 judge。三题最终答案均命中基准，但轨迹中存在引用解释错误、条件未核实、重复阅读和提前结束验证等可研究问题。

**给 GPT 的入口：[GPT_REVIEW.md](GPT_REVIEW.md)。** 它给出阅读顺序、证据定位和下一步实验约束。先看分析，再回查对应轮次与原始 body，避免把 3/3 答案正确当作全部过程已通过。

## 三题导航

| 题目 | 完整分析 | 引用审计 | 全部交互 | 按轮阅读 | 原始 SQLite |
|---|---|---|---|---|---|
| q26 | [分析](q26/INTERACTION_ANALYSIS.md) | [审计](q26/CLAIM_EVIDENCE_AUDIT.md) | [完整交互](q26/FULL_INTERACTION.md) | [12 轮](q26/rounds/README.md) | [数据库](q26/episode.sqlite) |
| q72，预标简单 | [分析](q72/INTERACTION_ANALYSIS.md) | [审计](q72/CLAIM_EVIDENCE_AUDIT.md) | [完整交互](q72/FULL_INTERACTION.md) | [14 轮](q72/rounds/README.md) | [数据库](q72/episode.sqlite) |
| q661，预标困难 | [分析](q661/INTERACTION_ANALYSIS.md) | [审计](q661/CLAIM_EVIDENCE_AUDIT.md) | [完整交互](q661/FULL_INTERACTION.md) | [4 轮](q661/rounds/README.md) | [数据库](q661/episode.sqlite) |

原题在各题 question.txt / question.json，原始提交在 result.json。每题 http/NNN/request.body 和 response.body 保留实际模型请求／响应正文；trajectory.jsonl 保存全部事件，SQLite 的 objects 表包含归档对象和本局取得的文档全文，不仅是摘要。

工具、查询、原文和可见性分别在 TOOL_INTEGRITY.csv、TOOL_EXECUTION_LINKS.csv、QUERY_EXECUTION.csv、EVIDENCE_TABLE.csv、EVIDENCE_LIFECYCLE.json、VISIBILITY_TABLE.csv。q72/q661 另有 READ_SELECTION_AUDIT.json 和 ROUND_REVIEW_INPUT.json。按轮文件是新生成的阅读视图，完整请求 body 与原始对象仍保留。

事后判分见 [JUDGE_REPORT.md](judge/JUDGE_REPORT.md)、[judgments.json](judge/judgments.json) 和 [external-labels.json](judge/external-labels.json)。三个 slot 仅在本包对应 roster 内有效，分别是 q26、q72、q661。judge 只判原始 finish.answer 与基准是否一致，不审查模型提交前的解释或 refs 充分性。

## 公开副本与原始封存的关系

用户在完成实验后明确授权将完整轨迹与分析发布至远程。原始本地封存目录未修改。此前报告里“仅本地／不公开”的文字描述当时状态；本目录为后来授权生成的公开副本。

公开处理只替换内部模型服务主机名和本机用户路径。三个 SQLite 中只改 model_identity 事件的部署地址，其后事件链按同一发布版算法重算；所有 content-addressed objects、模型实际请求／响应、工具参数／结果、文档、证据窗口及其哈希保持不变。衍生 JSON/Markdown 中的事件哈希引用映射到公开链。

**公开数据库的 head 不等于原始 head。** [ARCHIVE_HEAD_MAP.json](ARCHIVE_HEAD_MAP.json) 同时保留二者，judge 的公开标签指向公开链。原始 body 全部按字节不变，元数据经过替换的文件不宣称与原文件按字节相同。

[PUBLICATION_FILES.json](PUBLICATION_FILES.json) 逐文件列出原始 SHA-256、公开副本 SHA-256 和处理方式；各题 SOURCE_FILE_HASHES.json 保留源封存文件清单，供与本地原件对照，不应拿它验证公开派生文件。当前公开文件应以本目录 [MANIFEST.sha256.json](MANIFEST.sha256.json) 为准。

没有上传 API 密钥、秘密请求头、真实预算 SQLite、生产搜索索引、虚拟环境或运行时 WAL/SHM。保留了复核成本所需的预算计数及脱敏身份元数据。公开计划中的 USER 路径和 model-service.invalid 是占位符，不是可执行生产配置。

## 复核

在安装发布版 STRIDE 的环境中，可以对公开数据库运行只读 replay/diagnose，或用 Archive.verify() 检查对象及事件链。代码和冻结 Config 位于各题 capture_source、manifest.json 以及仓库 examples。实验实际基于 release `5d7752be94a9d40aa757383d8899504bc0f81e81`，发布这些材料的新提交不代表另一次自然运行。

发布验收见 [VALIDATION.json](VALIDATION.json)。它核对三份公开 Archive、30 次 policy 和 3 次 judge 的原始 HTTP body、全部内容对象、公开 judge head 映射与文件哈希。Git 对本目录禁用换行转换，以保持传输前后的正文哈希。
