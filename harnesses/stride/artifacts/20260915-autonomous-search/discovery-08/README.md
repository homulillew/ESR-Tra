# 第八轮中断阶段完整轨迹

冻结运行代码 `2d3d195`，比较 baseline 与 read-only-once-v1。实际运行四槽；q775两臂均空答案，只有这一组完成两臂任务运行。q774处理臂16请求后model_budget，baseline第4次HTTP400触发服务方data_inspection_failed，队列停止。四个控制槽NOT_RUN，无judge、无全局POLICY_SEALED，不报告完整四题准确率。

两题处理臂各有一次read-only请求，但模型均输出search，被原样拒绝执行，没有自动替换为read。q775后续正常阶段另有读取；不能将其视为限制轮成功执行。q774的400是输入内容检查拒绝，原始记录不能确定具体触发内容，不是401鉴权错误或429限流。

合计49次policy HTTP、0次judge；新授权1000次额度累计427次，剩573次。cohort保留STOPPED、RESULTS和所有NOT_RUN状态，没有补跑。

本目录包含4个SQLite、完整原文与工具轨迹、逐轮阅读视图以及98个原始HTTP body，包含400原始响应。所有body与私有原件逐字节一致，私有seal不变；公开SQLite仅脱敏部署身份并重建事件链。

PUBLICATION_CHECKS.json保存校验结果，ARCHIVE_HEAD_MAP.json保存链对应关系，MANIFEST.sha256.json覆盖本目录除自身外的文件。没有凭证、私有配置、预算或标准答案数据库；发布未调用模型、过滤或重发请求。
