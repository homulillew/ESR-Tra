# 第十二轮冻结执行说明

比较baseline与search-coverage-rank-v1，规则见[COVERAGE_RANK_PLAN.md](../../COVERAGE_RANK_PLAN.md)。同一原CPU OR/BM25查询取固定20候选，按不同query词在URL标题和完整snippet内的精确覆盖稳定重排，返回原top_k。原score不改，原池与最终顺序留档，只返回文档取得导航身份。唯一模型可见说明差异为retriever_capabilities，SYSTEM及工具schema不变。

实际全量回归593项通过，包含46项新排序检查；新增边界文件另有5项通过，不冒称重新运行过598项全量。边界覆盖两个原生call重复缓存、compiled等价batch、预算不足零执行、第二query失败与result扣留后的授权。独立review无阻塞。无新GLM和生产索引检索；准备器只读取原索引身份。测试日志、XML及源码哈希见OFFLINE_TESTS/PLAN。

队列q775基线→候选、q774候选→基线、q771基线→候选、q778候选→基线。原GLM服务/返回身份、temperature=0、full workflow、string-integer-v1，难题每槽16次、控制4次、每槽600秒，全部从空episode经正式CLI运行。原其他Config、问题、索引身份和源码均在PLAN.json冻结，实际运行SHA由manifest写入。

当前原总账autonomous-search-20260916剩844次，最多80策略＋8judge=88，另预留360次复验；发送前原子占额，失败/未知计入。全部策略封存后才判实际submitted；独立原文审阅核对核心关系。开发净正确数增加、控制不回退、增益有来源支持才进入新十二题配对。十二题均已暴露，不冒称holdout，旧6/12不变。

冻结时NOT_RUN，提交推送核验后直接启动，不再等待批准。在线阶段不调整规则、池大小或提示；异常封存停队列，不重试/换模型。负结果和完整脱敏轨迹照常发布。
