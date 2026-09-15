# 第十轮完整封存轨迹

实际运行代码为 `72ec6f10d3449390de8c570e92407f7da8fed640`。本轮比较 baseline 与 search-raw-window-v1，四题八槽全部完成，项目 judge 判对数均为 2/4。候选未获得判分增益，未晋级；发布核验通过不代表机制改善答案质量。来源审阅及研究解释见[结果报告](../../../experiments/autonomous_search/records/discovery-10/RESULTS.md)。

本轮使用 69 次策略请求和 5 次 judge 请求，共 74 次 HTTP。2026-09-16 新授权 epoch 的 1000 次额度已用 74 次、剩余 926 次；此前总账历史保持不变。

本目录保留 8 个 SQLite、全部模型原始输入输出、原文、逐轮阅读视图、自动取文事件与来源，以及 148 个原始 HTTP 请求/响应 body。没有 NOT_RUN 槽或缺失响应。HTTP body 与原件逐字节一致；原始 seal 和封存文件保持不变；公开 SQLite 仅按既有发布器处理部署身份并重建事件链。自动取文不改记成模型 read 动作。

PUBLICATION_CHECKS.json 保存发布器核验，INDEPENDENT_PUBLICATION_CHECKS.json 保存独立核验，ARCHIVE_HEAD_MAP.json 保存原始与公开链头对应关系，MANIFEST.sha256.json 覆盖本目录除自身外的全部文件。完整私有原件、预算总账、标准答案和部署凭证未上传。发布过程没有发起模型、judge 或 CPU 文档请求。
