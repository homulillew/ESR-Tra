# 第三轮完整轨迹：输入检查拒绝后停止

冻结代码 `004930d648d947f375239e6df2d9c60d385eaf60`。q775 基线发送六次，第六次收到 HTTP 400 `data_inspection_failed`；其余七槽未启动，候选方案没有在线结果。没有 judge 请求或准确率配对。

目录保存完整请求、响应、SQLite、逐轮工具回执和来源原文，包括被拒绝请求及原始错误响应。公开发布检查见 [PUBLICATION_CHECKS.json](PUBLICATION_CHECKS.json)，文件哈希见 [MANIFEST.sha256.json](MANIFEST.sha256.json)。十二个 HTTP body 与私有原件逐字节一致；仅部署和本地身份元数据脱敏，并提供归档哈希映射。未上传凭证、生产索引或共享预算库。

详见[结果报告](../../../experiments/autonomous_search/records/discovery-03/RESULTS.md)。失败与未知尝试全部占额：本阶段 6 次，刷新窗口累计 122/1000，剩余 878。
