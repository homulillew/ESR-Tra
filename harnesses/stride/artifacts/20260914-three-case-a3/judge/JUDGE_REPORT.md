# STRIDE a3 三题正式提交判分

q26、q72、q661 的原始 finish.answer 均与本地基准答案逐字相同，项目语义 judge 也全部判为正确。本次结果为 **3/3**，仅描述这三道已分析题，不用于推断总体准确率。

| 题号 | 与基准答案逐字一致 | 语义 judge | 外部 formal_correct |
|---|---|---|---|
| q26 | 是 | 正确 | true |
| q72 | 是 | 正确 | true |
| q661 | 是 | 正确 | true |

## 判分合同与输入

使用当前冻结仓库 `src/esr_grpo/judge.py` 的 `OpenAICompatibleJudge`：判断候选回答与标准答案是否语义一致。每题只输入原始题目、本地基准答案和原始 finish.answer。没有输入模型提交前的解释、正式 refs、过程审计、旧轨迹或其他题目的结果。

基准来源为 `D:/AgentSearchAssets/BrowseComp-Plus/data/prepared/browsecomp_plus_decrypted.jsonl`，共 2,127,119,849 字节，整文件 SHA-256 为：

```text
f1958aa81bbaca21cb14a58ba009f53c070fa047f0107414226dbec76a242807
```

该哈希与此前数据选择记录一致。三题均按 query_id 提取，并逐字核对基准 query 与对应 Archive 的原题。每条基准记录的行号、行哈希以及题目／答案保存在私有 `*.input.json`，没有将 gold 传回 policy 或重跑问题。

被评估的 release 为 `5d7752be94a9d40aa757383d8899504bc0f81e81`。判分入口只增加 HTTP 采集、既有总账计账、冻结身份检查和严格结果验证；没有改变仓库 judge 的提示词。输入和采集器哈希在 manifest.json。源码副本、离线测试结果与判分计划一并封存。

## 模型与调用

每题恰好一次请求，共 3 次；请求模型 EB-GLM-5.2，返回模型 glm-5.2，temperature=0、top_p=1、max_tokens=2048。三次均 HTTP 200、finish_reason=stop，无解析错误、重试、截断或模型身份变化。使用的是既有 GLM 服务的独立事后调用，模型家族与 policy 相同，不声称具有独立模型交叉验证。

三条 judge rationale 均为候选与标准答案完全一致。原始 JSON、usage、时延、请求／响应正文及正文哈希按 HTTP 序号保存。`project_judge_result.confidence=1.0` 是项目代码从候选回答提取不到 confidence 时的默认值，并非 judge 模型返回的置信度，不能当作“100% 确定”。

调用前剩余额度 941，调用后 cap=1000、used=62、remaining=938。本次三条总账记录的 role 为 judge，失败或未知请求也按相同发送前计账机制计数；本次没有失败。

## 与原始轨迹的绑定

| 题号 | 原始 Archive head |
|---|---|
| q26 | 83e67edc8f5dc9bc1e0bd706c6c76f212f5bbaf8f01fe7b2e586e43521a04571 |
| q72 | 67a4a409700e8dd767ce94980fa8602e3e3aa847ccd7e3e1bcb70098b24c3c52 |
| q661 | cfbd6742545d9fbe477a3e784ed9e8cd7a51eb8dd1cef8c0d3b9620420c3cf1f |

启动前核验了三份原运行 MANIFEST.sha256.json 中的全部文件及 Archive 完整性。判断绑定上述 head 和原提交；`external-labels.json` 使用 STRIDE 接受的 slot/head/correct 结构，slot 0000、0001、0002 在本判分目录分别对应 q26、q72、q661。`judgments.json` 同时给出 qid 与源运行路径，不能把这些 slot 无映射地套用到其他 cohort。

原来的运行目录、报告与 formal_correct=null 均保持封存时状态；本次外部判断作为带时间与 head 的新记录追加。消费这些数据时，应通过上述绑定读取新的外部 formal_correct，不应把旧报告未判分状态误认为本次判分失败。

## 对此前轨迹分析的影响

这次判分确认三题最终名称命中基准。它没有否定此前的过程诊断：q26 的部分辅助条件缺少正式引用；q72 没有核实精确步行距离，并误解释 e3；q661 未取得工具持续使用及周年庆祝的直接证据。最终答案正确和论证尚不充分可以同时成立。

本次未将模型提交前的解释附加到 finish.answer，也未要求 judge 按过程证据重新打分。若评估解释事实性或引用充分性，须采用另外明确的评测对象和合同，不能把本次答案判分当作过程审计已通过。

## 私有产物

`judgments.json` 和 `external-labels.json` 是结果；`001–003.input.json`、`001–003.judgment.json` 与 `http/001–003/` 支持逐项复核；`FINAL_CHECKS.json` 保存预算和原轨迹复验，`COST.json` 分别统计 tokens、缓存、请求字节及 HTTP 耗时。`MANIFEST.sha256.json` 覆盖封存文件。

全部数据仅保留本地，未公开上传原题、gold、答案、HTTP 或数据库。没有保存秘密请求头。正式判分新增 3 次调用，未改变原始三次自然运行。
