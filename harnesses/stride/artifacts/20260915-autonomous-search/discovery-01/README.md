# Discovery-01 完整轨迹

本目录包含 2026-09-15 自主研究首轮实际运行的三个 episode：共 34 次真实策略请求，68 份原始 HTTP 请求/响应正文。队列第三槽因模型输出截断而停止；其余五槽为 NOT_RUN，没有 judge 调用或标准答案读取。[结果与用量报告](../../../experiments/autonomous_search/records/discovery-01/RESULTS.md)解释实验范围和失败原因。运行代码为 `4d48b95d49051e2fe81ec5b0a5f021929e4b331d`。

| 槽位 | 完整逐轮阅读入口 | 终态 |
|---|---|---|
| q775 baseline | [12 轮](q775-baseline-r1/rounds/README.md) | abstained |
| q775 constraint-review-v1 | [16 轮](q775-constraint-review-v1-r1/rounds/README.md) | model_budget |
| q774 constraint-review-v1 | [6 轮，含截断原响应](q774-constraint-review-v1-r1/rounds/README.md) | incomplete_response |

每个槽位的 `http/NNN/request.body`、`response.body` 保持私有原件的逐字节内容；`metadata.json` 记录身份、token/cache、状态与持久计量编号。`episode.sqlite` 可只读回放；`FULL_INTERACTION.md`、`trajectory.jsonl`、各项 CSV、`documents/`、`evidence/` 和 `all-objects.json` 提供完整阅读与分析入口。未实际取得原文的槽位不会生成虚构证据。

[cohort/RESULTS.json](cohort/RESULTS.json)保留全部八个计划槽位及原始计量，[STOPPED.json](cohort/STOPPED.json)记录停止位置。没有伪造 POLICY_SEALED.json：只有三个已运行 episode 的独立封存记录。

## 内容、身份与完整性

公开 SQLite 只替换部署身份中的私有地址，因此事件哈希链与私有原件不同。[ARCHIVE_HEAD_MAP.json](ARCHIVE_HEAD_MAP.json)逐档案提供原始和公开 head，原始模型请求、响应、工具参数和所有内容寻址对象不变。[PUBLICATION_FILES.json](PUBLICATION_FILES.json)记录逐文件转换，[PUBLICATION_CHECKS.json](PUBLICATION_CHECKS.json)记录实际核查：34 次请求与总账阶段计数一致、68 份正文逐字节一致、三个公开 SQLite 链验证通过、三个私有封存保持不变。

各槽 `SOURCE_FILE_HASHES.json` 是私有原件的来源定位；公开文件的哈希见本目录 `MANIFEST.sha256.json`。二者因明确记录的部署元数据脱敏可以不同。原始 seal 对应私有文件，不能误用为脱敏后文件的字节校验清单。

不包含凭证、真实部署地址、共享预算 SQLite、生产索引或私有部署 manifest。发布本身没有新增模型请求。旧实验档案和正式 6/12 标签未改动。
