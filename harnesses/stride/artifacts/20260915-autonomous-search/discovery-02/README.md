# Discovery-02 完整轨迹

本目录保留八个真实自然 episode 和四次项目 judge，共 82 次 HTTP、164 份原始请求/响应正文。真实运行 SHA 为 `3f214db0a6854b1820ed97b5f06d1b06f7e9e83d`。[结果报告](../../../experiments/autonomous_search/records/discovery-02/RESULTS.md)记录基线 2/4、候选 2/4，没有准确率增益。

| 槽位 | 逐轮入口 | 终态 |
|---|---|---|
| q775 search-pivot-v1 | [16 轮](q775-search-pivot-v1-r1/rounds/README.md) | model_budget |
| q775 baseline | [14 轮](q775-baseline-r1/rounds/README.md) | stalled_no_submission |
| q774 baseline | [16 轮](q774-baseline-r1/rounds/README.md) | abstained |
| q774 search-pivot-v1 | [16 轮](q774-search-pivot-v1-r1/rounds/README.md) | abstained |
| q771 search-pivot-v1 | [4 轮](q771-search-pivot-v1-r1/rounds/README.md) | submitted |
| q771 baseline | [4 轮](q771-baseline-r1/rounds/README.md) | submitted |
| q778 baseline | [4 轮](q778-baseline-r1/rounds/README.md) | submitted |
| q778 search-pivot-v1 | [4 轮](q778-search-pivot-v1-r1/rounds/README.md) | submitted |

每槽包含可只读回放的 episode.sqlite、完整 HTTP 正文与 metadata、FULL_INTERACTION.md、trajectory.jsonl、CSV、原文 documents/evidence 和内容寻址对象。`judge/http/` 保留四次实际判分；`cohort/RESULTS.json` 和 `POLICY_SEALED.json` 保留阶段结果与封存绑定。原始整数答案及其文本表示转换均在档案中。

HTTP 正文逐字节保持；公开 SQLite 仅对部署身份脱敏并重建事件哈希链。[ARCHIVE_HEAD_MAP.json](ARCHIVE_HEAD_MAP.json)提供原始/公开 head，[PUBLICATION_FILES.json](PUBLICATION_FILES.json)提供逐文件转换，[PUBLICATION_CHECKS.json](PUBLICATION_CHECKS.json)核验 82 次计量、164 份正文、八条公开档案链及私有原件不变。

各槽 SOURCE_FILE_HASHES.json 定位私有来源字节，公开目录 MANIFEST.sha256.json 校验公开字节；原始 seal 不能直接作为脱敏后字节清单。这里不包含共享预算数据库、凭证、真实部署地址、私有部署 manifest 或生产索引。发布没有新增模型调用，原正式 6/12 未变。
