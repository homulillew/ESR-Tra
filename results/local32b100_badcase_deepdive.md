# 32B 全链路 ESR bad case 深度分析

> 数据：`results/local32b100/`（本地 Qwen3-32B 策略+verifier，随机100条 × max_turns=100）
> 方法：从 `stores/<qid>_esr.sqlite` 重建每局 actions 时序，按工具分布 / verify 轮次 / 候选答案 / gold 召回 / 搜索 query 逐局归类
> 脚本：`analysis-L/badcase32b_analyze.py`（产出 `results/local32b100/badcase_analysis.json`）

## 总览

ESR 100 局里只有 **47 提交 / 11 正确**，其余 **53 全打满 100 轮不提交**。把 53+36 条 bad case 拆开后，主导失败**不在 verifier 门禁，而在策略侧的检索与实体选择**——与 4B 时代的"verifier 幻觉式假打回"是两类不同的问题。

```text
ESR 100 局
├─ 提交 47
│   ├─ 正确 11
│   └─ 错误 36
│       ├─ 拒绝式放行 18（verifier 把"找不到/证据不足"当 supported）
│       └─ 实体/数值错 18（verifier 把具体但错的答案当 supported）
└─ 打满100轮 53
    ├─ gold 从未召回进证据 43　← 主导
    └─ gold 已召回但未 supported 10
        ├─ 策略选错实体 verifier 正确拒 9
        └─ 策略持正确实体 verifier 冗余卡据 1
```

## 一、打满 100 轮的 53 例：真凶是"搜索循环"不是 verify 掰扯

按 actions 重建后，这 53 局的工具分布与全部局有明显分界：

| 工具均值 | max_turns(53) | submitted(47) |
|---------|--------------|---------------|
| search | **59.5** | 2.8 |
| open_page | 21.7 | 3.3 |
| update_state | 8.9 | 1.9 |
| verify_answer | 9.7 | 1.8 |

- max_turns 局平均 **59.5 次 search**，而提交局平均只有 2.8 次。submit 门禁本身干净：47 局拿到 `supported`，47 局全提交（`supported ⇒ submit` 一对一，门禁无漏放）。
- 关键：这 53 局里 **平均 distinct 查询词只有 3.9 个，而相邻重复搜索高达 52.1 次**。策略不是"换了很多查法"，而是**在同一个（或同一组）query 上来回重复搜**，每次都把同一个 top-hit 文档打开、verify 一次、被拒、再搜同一个词。
- verify 轮次：51/53 局 ≥3 次 verify，40/53 ≥5 次。**不是没去 verify，是 verify 永远不 supported**。

结论：53 局是**「同一组查询词反复重搜 + 永远 verify 不过」的组合循环**，一百万次轮次上限前跑不完。跟"上下文裁剪"无关——修掉上下文书虫后无 error，剩余的纯是行为不收敛。

## 二、分成两半：43 检索未召回 gold，10 召回却未 supported

逐局用归一化 gold 子串去查每局的证据原文与 search hit snippet：

- **43/53：gold 从来不在任何 search hit 的 snippet、也不在任何已开文档证据里** → 检索面根本没把 gold 捞上来。
- **10/53：gold 确实在某条已开证据里，但 32B verifier 始终不 supported。**

### 43 例检索未召回的根子：查询词锚在幻觉实体上

抽看这 43 局的 distinct query，不是 BM25 召回不够，而是**查询词本身就没对准 gold**：

- q1201(gold=`Govardhan Asrani`)：搜出来的词一路跳成 **"Dr. Tatiana Toro"**——
  题目一提某个候选人，策略就把题干浮出来的名字当锚，围着错的实体狂搜。
- q161(gold=`Kune Rima`)：query 直接变成 **"Neil Young born in 1940s..."**，锚错人。
- q199(gold=`Gae Lowe (Le Duel)`)：query 是 "album with word tunnel released between 1970 and 1985 runtime 30-40min"——**把整道题的一串限定词堆进去**当查询，BM25 对这种 10 词的流水账检索天然拉不响。
- q1026/q1209/q1236 同理，全是题干多分句直译。

所以 43 例是**策略侧 query 构造失败**：要么幻觉锚定错误实体，要么超长直译题干——gold 文档因此永远进不了 hit 列表，跟 verifier 无关。

### 10 例召回却未 supported：9 例是策略选错实体，verifier 拒得有理

逐条读 10 局的 held 答案（来自 task_states）vs gold：

| qid | held | gold | verifier 拒绝理由 | 判定 |
|-----|------|------|------|------|
| 1027 | 10 | 17 | Greg Moore 是加拿大车手，题干要美国人 | 策略错（数值也错），verifier 对 |
| 1226 | Natalie Cole | Yumi Arai | 多条前提证不到 | 策略错实体，verifier 对 |
| 546 | Ronnie O'Sullivan | Ding Junhui | century/147/spec 前提证不到 | 策略错实体，verifier 对 |
| 63 | Montreal | St. Louis | 无首个赞助商城市 | 策略错，verifier 对 |
| 653 | 2001 | 2005 | 无基金会成立年 | 策略错年份，verifier 对 |
| 726 | 2019 | 2010 | 队长年份对不上 | 策略错年份，verifier 对 |
| 853 | 一段主体不明的措辞 | Richard C. Larson | 答案不是具体实体 | 策略没吐出实体，verifier 对 |
| 904 | 1982 | 1980 | 导演出生地前提证不到 | 策略错年份，verifier 对 |
| 239 | Anna | Jun | 证据超预算(harn旁支) | 策略错 + harn预算截断 |
| 907 | Vasco da Gama Pillar | Vasco da Gama Pillar | 结构在某 UNESCO 76 英里内证不到 | 策略持正确实体，verifier 冗余卡一条旁据 |

**9/10 是策略产出错误答案却被 verifier 正确地拒绝**；只有 907 一条是策略已经持到 gold 实体、verifier 拿一条题干旁证（"76 英里内 UNESCO"）卡住不放，可算 verifier 过严。

这直接推翻"32B verifier 像 4B 一样幻觉式假打回"的猜测：**换 32B 后 verifier 是诚实的，它拒的都是策略真正选错的答案**。瓶颈从 verifier 能力，移到策略的检索-选实体。

## 三、提交但答错的 36 例：verifier 的"拒绝式放行"稀释精度

已提交 47 里 11 正确、36 错误。36 错误再分成两类：

- **18 例拒绝式放行**：提交的是「证据不足 / 未提供 / 无法确定 / insufficient」这类**措辞性拒绝**（q1076/1119/297/301/555/591/753/838/864/885/98……）。32B verifier 把它们判成 **supported（gaps 空）放行提交**。这 18 例对精度是纯损耗。
- **18 例实体/数值错**：提交的是具体但错的答案（日期 1012、数值 380/624/778、人名 1203/1230/416、作品 1139/580/664……）。verifier 在证据似乎对上部分时就支持了。

正向佐证：正确提交的 11 条里 **9 条 gold 都在证据里**——gold 进了证据 + 策略选对实体时，32B verifier 是能放行的。问题不在 verifier 不认对答案，而在于**它对"对答案"和"拒绝式 / 错实体"放行得一样宽**。

## 四、根因收束

把 100 局的坏结果归到三类，按贡献排序：

1. **策略检索不收敛（53 例，主因）**：32B 策略在 100 轮里靠 3.9 个 query 反复重搜（52 次相邻重复），既不换面、也不扩 cover。其中 43 例 gold 从未进证据（query 锚幻觉实体或超长直译），10 例 gold 进了证据但策略选错实体。verify 循环只是这个不收敛的表现，不是独立故障。
2. **verifier 类型判据松（18 例）**：32B verifier 把"找不到/证据不足"的措辞判为 supported。这类提交把精度从"应接近 100%"稀释到 23%。
3. **verifier 冗余卡据（约 1 例，907）+ harn 预算截断（239）**：边缘，量小。

**一句话**：在 32B 全链路下，ESR 的提交门槛（`SUPPORTED 且 gaps空`）机制是干净的（supported⇒submit 1:1），真正卡死的是**策略侧的检索面铺不开 + 实体选错**；而提交的精度又被 **verifier 对"拒绝式答案"过宽**稀释。两者都指向「策略/verifier 的组合判据」，与 4B 时代的 verifier 幻觉是不同病症。

## 五、指向的改进方向（供实验2参考）

- **策略检索纪律**：限制同一 query 的重复搜索次数、强制在 reject 后换查询面（引入 query 去重 / 扩展），切断"3.9 词 × 52 次重复"的循环。
- **verifier 类型约束**：给 verify 判据加"答案必须是具体实体/数值，拒绝式措辞算不通过"的自约束，或对这类答案单独不给 supported——直接掐掉 18 例拒绝式放行。
- **RL credit assignment 更明确**：对"verify 拒到 100 轮"给明确负向，逼策略跳出重复搜索；对"gold 在证据却选错实体"给检索/选实体正误关联。