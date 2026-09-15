# 第十一轮冻结执行说明

比较 baseline 与 continuous-prose-omission-v1，完整方案见 [CONTINUOUS_PROSE_PLAN.md](../../CONTINUOUS_PROSE_PLAN.md)。仅在后续请求中持续省略完整工具组里的可见助手正文；包括首组、最近组及FINAL。SYSTEM、工具定义、原问题、工具调用与回执不变，原始归档保留。provider reasoning若有仍原样送出。第一次请求必须与本次基线逐字节一致。

实际离线完整回归547项通过，包含12项新增区别性检查；定向新旧历史测试32项通过。详细记录和哈希见 OFFLINE_TESTS.json。没有新GLM调用。当前授权窗口剩926次，足够本阶段88次和后续预留360次；原总账不清零，使用 autonomous-search-20260916。

顺序为 q775基线→候选、q774候选→基线、q771基线→候选、q778候选→基线。原GLM和只读CPU、temperature=0、full workflow、string-integer-v1，难题16请求、短控制4请求、每槽600秒，从空episode经正式CLI自然运行。PLAN.json冻结源码、全部Config、问题和身份哈希；实际SHA由运行manifest记录。冻结时在线状态NOT_RUN，推送核验后自动开始，无需人工批准。

全部八槽封存后才判实际提交；来源审阅独立判断支持。只有开发净正确数增加、控制不回退且增益有来源支持时才进入新十二题配对复验。未达到标准完整保留负结果。队列异常封存停止，不重试、不在结果出现后修改实现或提示。
