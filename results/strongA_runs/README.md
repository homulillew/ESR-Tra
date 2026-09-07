# 强策略完整 ESR 轨迹 — 12 条归档

> 生成：2026-09-03（用户要求「让强策略跑完整 ESR 轨迹的 12 条」）。
> 脚本：`/tmp/strongA_batch.py`（强策略选 doc + 给正确答案，真实 BM25 检索 `:8000` + 真实 4B verifier `:8005`）。
> 轨迹账本：本目录 `results/strongA_runs/{qid}.sqlite`（**完整可回溯**，含每次 search/open_page/update_state/verify 的 path 与 answer/evidence/gap/rationale）。
> 结果 json：`analysis-L/strongA_12_result.json`（重跑更新，12 条 docid 与各 store 全吻合）。

## 结果：12/12 全 needs_revision → 全 blocked(verify)，0 提交（两次运行逐字复现）

| qid | gold | docid_open | 存储docid | verify | submit | gap(落盘 rationale 存的判词) |
|---|---|---|---|---|---|---|
| 186 | Galacta: The Battle for Saturn | 60075 | 60075 | needs_revision | blocked | 要游戏名称/两栖公司/1990s早期名/11月发布等全约束 |
| 56 | Last Christmas | 60892 | 60892 | needs_revision | blocked | 要全约束（ReFrame Stamp/节日/PG-13/导演） |
| 1041 | Adaku | 61696 | 61696 | needs_revision | blocked | 采访者'Adaku'未在原始证据中作为采访者出现 |
| 1089 | Zius Galit | 86834 | 86834 | needs_revision | blocked | unparseable output |
| 1198 | Robert Mugabe | 83077 | 83077 | needs_revision | blocked | 未提供国家名称（须核实2022识字率/变色龙线索） |
| 324 | Svetlana Gromenkova | 85213 | 85213 | needs_revision | blocked | 未提供 X 身份名称（实体身份规则） |
| 364 | Bada Lee | 31124 | 31124 | needs_revision | blocked | 证据未提及 Bada Lee / 未说明生日/舞蹈推广者/Padi |
| 391 | María Constanza Guzmán | 22666 | 22666 | needs_revision | blocked | unparseable output |
| 517 | Peter King | 53458 | 53458 | needs_revision | blocked | 证据未包含该名字 + 无法验证1970s出生/士兵父/生肖羊 |
| 636 | 2011 | 19992 | 19992 | needs_revision | blocked | '2011'年未被证据支持（仅Desmond Tutu 2011揭幕式） |
| 772 | Secretary | 94800 | 94800 | needs_revision | blocked | 缺学校最早员工角色具体信息 |
| 83 | Joseph Dalton Hooker | 39837 | 39837 | needs_revision | blocked | unparseable output |

## 判定（结合 chunk 视图逐字核对 —— gold 实体是否真在强策略 open 的 doc 的 chunk 视图里）

| 类别 | qid | 说明 |
|---|---|---|
| 假打回（gold 在视图却拒） | 1041 / 1198 / 324 / 636 | gold 实体在喂入 chunk 视图（324 idx0 "Oh Svetlana!"、1198 idx3 "became PM"、1041 idx0 Bonang 访谈、636 自引 2011）仍 needs_revision |
| 解析失败（unparseable） | 1089 / 391 / 83 | 4B 输出非干净 JSON 被吞成 needs_revision |
| 真阳性（open 到不含 gold 的 doc） | 186 / 56 / 364 / 517 / 772 | 强策略 open 的 top-hit doc chunk 视图不含 gold 实体段落 → 检索召回缺 gold，非 verifier |

**结论**：短板 A 非单一 bug。5/12 检索召回真缺口、4/12 4B verifier 语义误判、3/12 解析失败吞正确轨迹；
submit 门禁只认 SUPPORTED 无逃生放大噪声。修复应落 harness 容错出口 + 检索召回广度 + verifier/parser 可靠性。

## 复现性
两条硬证据：(1) gap 文本与上一轮 `strongA_12_result.json` 逐字一致；(2) store 中 verify 的
`verification_status/created_gap_ids/rationale` 与 result json 完全吻合，docid 12/12 对齐。