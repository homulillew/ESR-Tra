# Discovery 10：q775 / q774 独立来源审阅

范围仅本轮两个问题的 baseline 与 search-raw-window-v1 四个封存策略槽，运行冻结 SHA 72ec6f1。未读取 judge、RESULTS 判分、gold 或判分理由，未补模型请求，未修改产品。结构化核验与计量见 HARD_CHECKS.json；文件不保存部署身份、本机路径或题目完整正文。

## 核验结论与成本

四槽 seal 文件哈希、SQLite 链、54 对实际 HTTP 请求/归档及正常响应对象核验通过。自动 search 的父 call、原 query 首项、首文档、六文档去重上限、snapshot 缓存状态、实际 get_document、词面选择器重算、原文 range/hash 均通过。实际输入按工具回执、raw_windows 和 shelf 结构解析，窗口对象与 visible_evidence/delivery_ack 对应；成功原生 read/find/finish 的固定 binding 核验通过。没有将字符串出现在任意散文中当作交付。

本协议从首请求起改变 SYSTEM 与 search 描述，故两臂 R1 **不逐字节相同**。两题 R1 除 SYSTEM、tools 外相同；不能套用旧只读协议“触发前首输入相同”的解释。没有分支或独立规划调用。

| 槽 | 模型请求 | search/read/finish 声明 | 后端 | 自动尝试/成功/skip | 输入/输出 token | 缓存读 token | terminal 秒 |
|---|---:|---|---:|---|---|---:|---:|
| q775 baseline | 16 | 25/1/0 | 18 | 0/0/0 | 204385/1352 | 142720 | 84.580 |
| q775 candidate | 10 | 10/0/1 | 20 | 3/3/5 | 162720/2711 | 54912 | 81.739 |
| q774 baseline | 12 | 11/0/1 | 21 | 0/0/0 | 206962/1955 | 92288 | 约见 checks terminal |
| q774 candidate | 16 | 15/2/1 | 43 | 6/6/9 | 283458/2592 | 103296 | 192.363 |

search 声明包括本地拒绝；自动获取不是模型原生 read。q775 候选八个成功 search 进入 attach，另两条因重复查询被原工作流拦截；三次自动尝试均取窗，五次跳过。q774 候选六次自动取窗达到上限，九次 skip，另有两次原生 read。两槽自动原文均无 no-match 或 error，结构化检查未发现容量 withholding。计量是实际策略请求与后端工作，不等于答案质量，也不含 judge。

## q775：部分年份关系正确，核心城市答案没有来源支持

**baseline**：R2 将 queries 错写为字符串，两条 search 参数无效；R3 改为数组。R4 关注 2005 年成立的国际 Booker，但混入 The White Tiger 普通 Booker 路线。R5 唯一 read 得普通 Booker 百科 e1=[0,3000)，R6 才实际交付；它明确普通奖成立于 1969，并介绍另有国际姊妹奖。随后 R6–R15 反复搜索国际 Booker、Flights、Luminaries，未再读对应原文。R16 已是 FINAL 仍生成 search，被 final_only 拒绝，终态 model_budget 空答案。该槽不是主动弃答。

**candidate 的自动来源顺序**：

- R1 自动 e1：Barnard 的 Jhumpa Lahiri 介绍 [788,3788)，R2 输入首次交付。包含翻译、博士论文、任职与奖项列表，但不支持所问两本书及城市链。这里先取得原文，尚未取得有效解题依据。
- R2 自动 e2：The Conversation 的 Han Kang 文章 [0,3000)，R3 交付。明确 The Vegetarian 韩文出版 2007、英文翻译 2015、获 Man Booker International 2016。这是首个直接支持关键局部关系的窗口；原始语言出版年与英译年必须区分。
- R3 自动 e3：普通 Booker 百科的姊妹奖段 [23993,26993)，R4 交付。明确国际奖 2005 年成立、2016 改为年度单本英译作品奖，也描述另一个 2007 成立的 Man Asian 奖。该窗口解决“奖本身成立于 2000s”，没有给出任何城市。

全槽没有原生 read。R3 已认定韩江为获奖作者并自称她出生 Gwangju，但 e2 实际窗口没有 Gwangju。R3–R4 搜 2016 contender，R5 短暂考虑 Man Asian，随后 R6–R9 返回同一国际 Booker shortlist 查询。自动原文使它得到两条准确局部事实，但没有促成 Book A 的可靠识别或新的城市来源读取。

R10 首次提出 Orhan Pamuk / A Strangeness in My Mind 作 Book A，同时给出另一书名和候选列表；这些不在三个原文窗口中。它随后明确写 Pamuk grew up in Istanbul、actual birthplace Istanbul，却将题目条件强行解释为“Pamuk grew up in Gwangju”，最后声称题目 framing 要的是连接城市，提交 Gwangju refs=e2/e3。这是已显式察觉不相容后仍用题目条件覆盖候选事实，并将成长地替换成题目询问的出生地。

**支持程度分开判断**：奖成立 2005 与 The Vegetarian 英译 2015/获奖 2016 有实际原文；Book A 身份、2016 出版、超过 25 种语言、其作者成长城市、两作者城市相等，以及最终所问出生城市都没有完成原文支持。e2/e3 中均没有 Gwangju 或 Pamuk。因此核心答案 **不支持**，整套条件仅 **部分支持**；合法 refs 与 submitted 不能作为成功证据。本结论来自当前交付窗口和模型实际推理，不依赖历史错误标签或当前 judge。

## q774：自动取得大量非目标原文，支持兄妹关系后仍未解决其余条件

两臂均将原题异常 cm 单位自行解释为 m；baseline R2 又把“首次出现的季”收窄为整部剧 2001–2019 开始。婚姻应保留 3 或 4 次，不能只搜 3 次就认为排除了其他候选；演员性别也未由原题限定。

**baseline**：R1–R3 泛搜亲属、子女及婚姻；R4 转向 El Señor de los Cielos，R5 起锚定 Aurelio Casillas/Rafael Amaya。R6–R11 反复剧名、妻子子女和身高，未执行任何 read，也无 e 窗口。R12 bounded FINAL 合法 finish(abstain=true)。不能把模型说“没有证据”解释为完全没有返回导航；这里是有检索导航但没有原文交付。

**candidate 的六次自动尝试**：R1 e1 为 EW 逝者汇总的 Sue Johanson/Julian Sands/Nicolas Coster 等段落；R2 e2 为 BBC 长寿节目综述；R3 e3 为 IMDb Marcia Strassman 生平；R4 两条 search 分别取得 Sofia Pernas/Justin Hartley 的现实婚姻文章 e4，以及 Cartwright Curse 中圣经/神话婚姻故事 e5。它们都是真实原文，词面相关不构成同一演员的完整条件支持。e2 明确讨论 2024 节目季数，也不能不加区分地当作截至 2023 季数。

R5 根据 ScreenRant 导航中的 Harmon 兄妹线索，原生 read d42 得 e6=[0,3000)，此页首段未到 Harmon 小节；同轮另一个 search 首命中文档也是该页，自动词面选择得到 e7=[4119,7119)。两者 R6 都真正交付。e7 明确 Jessica/Richard 是现实兄妹，在 The 100 分别演无亲属关系的 Niylah/John Murphy；这是本槽首个直接支持关键亲属条件的原文，自动选窗确实覆盖了普通页首 read 漏掉的段落。

e7 同时说明 Jessica 在第三季出现，Richard 前两季反复出现、第三季升主要角色；不能把“升主要角色”当首次出演。其相邻不同家庭段落的结婚、孩子数字属于其他人物，不能借来填 Harmon 条件。e7 也没有明确本剧 2014 首播/七季，最终 reason 将这两项一并归于 e7，超过该窗支持范围。

R7 已说婚姻/孩子条件不符合 John Murphy，R8 考虑 Niylah 或别的剧，但 R9 后又反复回到 Murphy。R10 声称“读 John Murphy 页面”却原生 read d140，得到 Raven Reyes 的 e8=[0,3000)，R11 交付。其主语是 Raven，由 Lindsey Morgan 饰演，文中 Murphy 只是枪伤她的人；该窗口不能证明 Murphy 的婚姻或子女。R11–R15 搜 Murphy/Emori/身高，未再得到目标原文。R16 合法弃答，未将亲属局部匹配提升成最终姓名。

**支持程度**：现实兄妹与无亲属角色关系有实际支持；身高、3–4 次婚姻、仅一名孩子存活未支持，完整候选未确认；终态 **无提交**。机制在此确实增加原文并选中了有用段落，但没有解决主体读取错误、候选排除和其余条件绑定。后端 43 对 21、模型 16 对 12，成本更高，不能用原生 read 少或自动窗口多宣称有效提点。

## 总结边界

两个候选槽均按声明执行自动原文交付。q775 的提交来自局部关系正确后的错误逻辑延伸；q774 得到一个真实关键关系后仍缺其他条件并弃答。必须同时报告“取到了什么原文”“其支持谁的什么关系”和终态，不能用词面 matched、e 有效、submitted 或较短请求数替代正确性判断。
