# Workflow v1 完整真实轨迹

本目录应用户追加要求公开完整记录，覆盖 6 个自然运行槽位、68 次策略请求与 3 次后处理 judge 请求。发布过程没有新增模型调用。分析结论、运行实现 SHA、387 项离线验收和额度见[完整分析报告](../../experiments/workflow_v1/report/RESULTS.md)。

实际运行实现：`2d62ac9dbe3bd6f59eb62c3f9980fbfb4c7364a7`；原分析报告提交：`86f9ac3dca4f8f5c6288975a2c41758dec385bf5`。

## 按槽位阅读

| 槽位 | 请求数 / 结果 | 逐轮索引 | 全部交互 | SQLite |
|---|---|---|---|---|
| q775 legacy | 16 / model_budget | [每轮记录](q775-legacy/rounds/README.md) | [完整交互](q775-legacy/FULL_INTERACTION.md) | [档案](q775-legacy/episode.sqlite) |
| q775 full | 16 / submitted，judge=false | [每轮记录](q775-full/rounds/README.md) | [完整交互](q775-full/FULL_INTERACTION.md) | [档案](q775-full/episode.sqlite) |
| q774 full | 12 / abstained | [每轮记录](q774-full/rounds/README.md) | [完整交互](q774-full/FULL_INTERACTION.md) | [档案](q774-full/episode.sqlite) |
| q774 legacy | 16 / model_budget | [每轮记录](q774-legacy/rounds/README.md) | [完整交互](q774-legacy/FULL_INTERACTION.md) | [档案](q774-legacy/episode.sqlite) |
| q771 full | 4 / submitted，judge=true | [每轮记录](q771-full/rounds/README.md) | [完整交互](q771-full/FULL_INTERACTION.md) | [档案](q771-full/episode.sqlite) |
| q778 full | 4 / submitted，judge=true | [每轮记录](q778-full/rounds/README.md) | [完整交互](q778-full/FULL_INTERACTION.md) | [档案](q778-full/episode.sqlite) |

建议先阅读逐轮索引，再打开该轮链接的 `request.body` 与 `response.body`。较大的完整交互文件可以下载阅读。每槽同时提供：

- `http/NNN/`：实际 HTTP 请求正文、响应正文、发送前占额记录和用量/延迟元数据；不包含 Authorization 请求头。
- `trajectory.jsonl`、`events-timed.jsonl`：完整事件与记录时间。
- `all-objects.json`、`episode.sqlite`：所有请求、响应、动作和引用对象，包括完整 workflow 视图；gap 本轮没有被自然使用。
- `documents/`：实际冻结的原始文档；`evidence/`：已生成的精确证据窗口。
- `ROUND_TABLE.csv`、`QUERY_EXECUTION.csv`、`TOOL_INTEGRITY.csv`、`EVIDENCE_TABLE.csv`、`VISIBILITY_TABLE.csv`：逐轮、查询、工具、证据和交付记录。

## Judge 与完整性

[Judge 输入绑定](cohort/judge-cases.json)保留全部实际提交文本及对应标准答案；[judge/http](judge/http)保存 3 次真实请求/响应，编号依次对应 q775 full、q771 full、q778 full。其余槽位没有提交，不补造判分。标准答案只在策略封存后被读取；实际时间见 [gold-access.json](cohort/gold-access.json) 与 [POLICY_SEALED.json](cohort/POLICY_SEALED.json)。这次公开标准答案不表示它曾进入策略输入。

本次新增授权公开此前仅留本地的完整轨迹。原私有封存记录保持原样，正式 6/12 和旧实验不变。共享预算库、账户凭证与生产索引不在此目录。

部署地址替换为 `model-service.invalid`，本地用户路径匿名化；该地址仅为占位符，不能用于实际请求。SQLite 仅修改 `model_identity` 事件中的部署元数据并重新计算后续事件哈希链；**所有内容寻址对象以及 142 个 HTTP 请求/响应正文保持逐字节一致**，没有更改模型原始回答、原生工具 ID、arguments、工具结果或原文。

- [ARCHIVE_HEAD_MAP.json](ARCHIVE_HEAD_MAP.json)：6 个原始/公开档案 head 对照和修改事件位置。
- [PUBLICATION_FILES.json](PUBLICATION_FILES.json)：每个复制文件的原始与公开哈希、转换类别。
- 各槽 `SOURCE_FILE_HASHES.json` 指向发布前的原文件哈希，`PUBLICATION_IDENTITY.json` 说明公开档案身份。
- [PUBLICATION_CHECKS.json](PUBLICATION_CHECKS.json)：6 个公开档案验证、71 次请求、142 个正文逐字节对照及私有封存未改验证。
- [MANIFEST.sha256.json](MANIFEST.sha256.json)：本次完整公开包的文件哈希。

`cohort` 中的历史 `seal_sha256` 等文件级绑定仍指原私有封存文件；公开副本应使用本目录的新 manifest 校验。事件 head 的公开对应关系以映射表为准，不能把匿名化档案当成原私有字节档案。

发布器相关既有本地测试本轮实际通过 3 项；公开副本还进行了全量档案、正文对应和敏感信息检查。全部工作为离线发布，不消耗模型额度。
