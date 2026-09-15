# Discovery 07 控制题独立来源审阅

2026-09-15。只读取四个SEALED控制槽；未读取judge/gold或活动文件。逐项机器核对见 CONTROLS_CHECKS.json，可复跑私有 audit_discovery07_controls.py。

结论：q771与q778两臂均有实际交付、最终引用的原文支持核心答案关系。四槽均未触发relation review，没有创建或呈现review memory；因此两臂轨迹和成本差异不能归因于该机制。该结论来自来源审阅，不以判分替代。

## 来源与范围

q771 baseline 的e2、memory臂e4均为同一原始快照[3000,6000)，窗口SHA256为01ef6425050ddf612695a672f50d2d88e296ce9e1e5d49338047f20a92856164。该窗口的完整上下文明确：Vitali Hakko于1982年与儿子Cem共同创立新品牌，紧接着将其命名为Vakkorama并说明面向青年。两个窗口均在最终请求可见且被引用。memory臂另引e3提供1982年青年店及后续品牌信息；无需从Vakko创始人的亲属身份反推出新品牌共同创立关系。此次来源通过，与上一轮候选仅读页头不同。

q778两臂e1[0,3000)为相同原文窗口。窗口先明确女儿、母亲及其关系，再在出生记录段写明母亲生育时21岁，指代完整；两臂均实际交付并引用。正文日期为2021-09-17，页面元数据日期2025-01-01，不能把元数据改写为事件年份。原文将亲子身份表述为当事人声称，审阅仅确认题目所问年龄的文本支持，不将该身份主张升级成已证实事实。

## 完整性与机制边界

四槽SEALED清单的全部文件逐byte SHA256匹配。以readonly模式验证SQLite完整对象与事件链，head匹配SEALED。16次model_request重建对象均与实际HTTP request.body解析后相等，16次原始model_response均与HTTP response.body相等；每个原文窗口均与snapshot对应切片及UTF8哈希一致。

q771两臂首请求字节相同，SHA256 a61deeac7f2debefea800747f21cf59eb495c83b3fe63081feaef2c7a704fe3b；q778对应为7c3b4de711393e1eb56749a873d6860c113e222b59f4a83f8c44136a147268b7。相同范围包括SYSTEM、工具schema前缀和首轮control。不是宣称后续整条轨迹相同。

未发现relation_review或review_memory事件，全部实际wire均无prior_relation_review_unverified。每槽4请求，且q771仅1次search、q778仅2次search，均没有达到连续3次successful search触发条件；3轮之后也已不足remaining>=4。

## 成本

| 槽 | 模型请求 | search/read/finish动作 | 后端次数 | 输入/输出token | cache read token | 模型耗时秒 | 后端耗时秒 | 事件跨度秒 |
|---|---:|---|---:|---|---:|---:|---:|---:|
| q771 baseline | 4 | 1/3/1 | 5 | 30363/538 | 15616 | 16.201 | 1.542 | 18.491 |
| q771 memory | 4 | 1/4/1 | 5 | 29084/422 | 13568 | 14.929 | 1.900 | 17.549 |
| q778 baseline | 4 | 2/1/1 | 7 | 36280/579 | 14720 | 17.988 | 4.396 | 23.356 |
| q778 memory | 4 | 2/1/1 | 7 | 29813/355 | 14464 | 13.391 | 5.380 | 19.636 |

后端耗时是CPU本地适配器调用的墙钟时间之和，日志没有进程CPU time，不能将其冒称CPU占用秒数。事件跨度为首末timed event间隔，不包含槽发布等外围工作。search动作可批量包含多个query，read可命中已有快照，因此动作数不等于后端次数。
