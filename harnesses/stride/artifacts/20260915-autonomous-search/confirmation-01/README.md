# 独立 12 题复验完整封存轨迹

本轮比较 baseline 与 read-only-explicit-v1，12 题共 24 个槽全部完成。项目 judge 判对数分别为 8/12 与 6/12；处理臂相对 baseline 为 0 胜、2 负，退步题为 q786、q793，配对检验 p=0.5。控制题未回退，其余 8 题净减少 2 道判对题。本轮未达到研究提升标准，不能认定方案成功；独立来源审阅已完成，机械完整性通过但部分条件支持存在缺口，judge 判对不等于来源证据已经核实。

本轮使用 251 次策略请求和 15 次 judge 请求，共 266 次 HTTP，均返回 200，模型身份一致。新授权 1000 次额度累计使用 770 次、剩余 230 次；总账上限 1643 次、累计使用 1413 次。

本目录保留 24 个 SQLite、全部原文与工具轨迹、逐轮阅读视图及 532 个原始请求/响应 body。没有 NOT_RUN 槽或缺失响应。所有 body 与私有原件逐字节一致，原私有 seal 保持不变；公开 SQLite 仅按既有发布器处理部署身份并重建事件链。未加入标准答案数据库、私有预算库、凭证或部署配置。

PUBLICATION_CHECKS.json 保存发布器核验，INDEPENDENT_PUBLICATION_CHECKS.json 保存独立核验，ARCHIVE_HEAD_MAP.json 保存私有与公开链头对应关系，MANIFEST.sha256.json 覆盖本目录除自身外的文件。发布和核验过程没有调用模型或重发请求。

完整独立来源审阅已完成，详见 [结果与审阅](../../../experiments/autonomous_search/records/confirmation-01/RESULTS.md)。原始判分标签不因来源审阅而改写。
