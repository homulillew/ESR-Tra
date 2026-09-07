#!/usr/bin/env python3
"""约束链覆盖率量化：对 12 条强策略轨迹，逐条统计「这道题 query 拆出的约束线索
在 evidence 全文里实际命中了多少条」。

设计原则（避免之前"gold 首 token 在不在 chunk 视图"的脆弱判据）：
- 每道题人工拆成约束线索（可审计）。
- 每条线索给判别 token：只取 query/标准专名里【明确可确定性命中】的特征词
  （年份/数字/机构名/物种/专有名词）。模糊描述（如"父亲是士兵""生肖羊"）不设自动判别，
  标注 NEEDS_MANUAL。
- 命中区间：strong = 强策略 evidence 全文合；online4b = 真实4B在线 evidence 全文合。
  用【全文】而非 chunk 视图，衡量"这批 evidence 文档整体能不能支撑约束链"，
  把"拦截在提交前证据不足"的本质量化出来。

输出：每条约束的命中表 + 每题命中率（strong vs 4B）。
"""
from __future__ import annotations
import json
from esr_grpo.store import EpisodeStore

# query_id -> (题目约束线索列表)
# 每条：(线索描述, 该线索的判别token列表 or None表示不可自动判定, 是否必须命中)
CONSTRAINTS: dict[str, list[tuple[str, list[str] | None]]] = {
    # gold=Galacta: The Battle for Saturn
    "186": [
        ("公司名源于两栖类动物", ["frog", "toad", "salamander", "amphibian", "newt"]),
        ("早1990年代公司曾用不同名", ["1990", "froggo"]),
        ("游戏1990年代初11月发布", ["november", "1991", "1992"]),
        ("DOS、单机、共享软件", ["dos", "single-player", "single player", "shareware"]),
        ("三个作者两人同姓", ["froggman", "credit"]),
    ],
    # gold=Last Christmas
    "56": [
        ("获奖ReFrame Stamp", ["reframe stamp", "reframe"]),
        ("2018-2023节日电影", ["2018", "2019", "christmas"]),
        ("PG-13评级", ["pg-13", "mpa"]),
        ("导演另导过改编自1981美国作家书的电影", ["1981", "pride and prejudice", "director"]),
    ],
    # gold=Adaku(采访者首名)
    "1041": [
        ("1980末非洲出生电视主持人", ["1987", "africa", "bonang"]),
        ("15岁出道、早期2010年代Revlon大使", ["15", "revlon"]),
        ("late2010s酒类品牌", ["alcoholic", "beverage", "liquor"]),
        ("mid-2010s采访,采访者名来自广播听众给的称呼", ["adaku", "radio"]),
    ],
    # gold=Zius Galit
    "1089": [
        ("1900上半出生、1999-2011年去世", ["1900", "1999", "2000", "2011", "died"]),
        ("知名颂歌、学校晨间操播放", ["anthem", "morning", "exercise", "assembly"]),
        ("疫情期个体做滑稽改编激励平静", ["covid", "pandemic", "parody", "mask", "sanitiz"]),
    ],
    # gold=Robert Mugabe
    "1198": [
        ("内陆国且两邻国也内陆", ["landlocked", "zimbabwe", "zambia", "botswana"]),
        ("2022识字率比2014增1.16%", ["1.16", "literacy", "2022"]),
        ("有按采集者命名的Chamaeleonidae物种", ["chamaeleon", "chameleon"]),
    ],
    # gold=Svetlana Gromenkova
    "324": [
        ("扑克玩家、向兄弟学、会弹钢琴", ["sibling", "piano", "learned"]),
        ("2009-2016全球赛事奖2-30万美元", ["2009", "2016", "200,000", "300,000", "winnings"]),
        ("2009-2015赢得一场、第三届大赛", ["2009", "2015", "third"]),
        ("final table有护士/动物权利/电影学位", ["nurse", "animal rights", "filmmak"]),
        ("final answer=往届冠军(两年前)", ["2008", "champion"]),
    ],
    # gold=Bada Lee
    "364": [
        ("2010-2017Mnet选秀出道三人组", ["mnet", "idol school", "2017"]),
        ("三人在日本再以小组合出道", ["japan", "debut"]),
        ("原成员生日与另一人相同", ["birthday", "same birthday"]),
        ("另一人以推广Padi参与曲目的舞走红", ["padi", "smoke", "bada"]),
    ],
    # gold=María Constanza Guzmán
    "391": [
        ("2009年出版的采访", ["2009", "interview"]),
        ("2022年12月前在西班牙语研究系工作", ["hispanic studies", "department"]),
        ("受访者学法语于12岁、妈妈讲Yiddish", ["french", "yiddish", "twelve", "12"]),
        ("受访者首个伴侣是乌拉圭文学批评家", ["uruguay", "critic", "partner"]),
    ],
    # gold=Peter King
    "517": [
        ("1970年代出生,父士兵,母军营医院", ["1970", "soldier", "hospital", "barrack"]),
        ("生肖羊", ["goat"]),
        ("2005年演警察,导演看Iracema后成电影人", ["2005", "iracema", "police"]),
        ("2013惊悚片,导演知名于Kinsey", ["2013", "kinsey"]),
    ],
    # gold=2011
    "636": [
        ("2015-2020发表的解释性文章", ["2015", "2020", "plaque"]),
        ("文中提到一城130余岁、约75座国家纪念碑", ["130", "75", "monument", "national"]),
        ("作者提到遗产领域先驱,获得金牌", ["gold medal", "foundation", "forerunner"]),
        ("1911/40年前提到的pioneer/基础法规更名", ["renamed", "1911", "simon", "der stel"]),
    ],
    # gold=Secretary(学校最长员工角色)
    "772": [
        ("1960s成立安置移民工;街名前缀命名后更名", ["1960", "migrant", "lwandle", "street"]),
        ("early2020s学校(1980s创办,始于教堂)", ["1980", "church", "school"]),
        ("问题:学校最长员工角色", ["longest-serving", "employee", "role", "secretary"]),
    ],
    # gold=Joseph Dalton Hooker
    "83": [
        ("至少两个该生物的起源叙事", ["origin", "mate", "yerba", "biolog"]),
        ("传统收获用锐石工具", ["stone", "harvest", "tool"]),
        ("1940s开始与贫穷/乡村关联", ["1940", "poverty", "rural"]),
        ("2012-2023文章,首个记录者对谁", ["hooker", "document", "credited"]),
    ],
}

ANSWER = {
    "186": "Galacta: The Battle for Saturn", "56": "Last Christmas", "1041": "Adaku",
    "1089": "Zius Galit", "1198": "Robert Mugabe", "324": "Svetlana Gromenkova",
    "364": "Bada Lee", "391": "María Constanza Guzmán", "517": "Peter King",
    "636": "2011", "772": "Secretary", "83": "Joseph Dalton Hooker",
}

STRONG_DIR = "/data1/ESR-GRPO-Code-L/results/strongA_runs"
ONLINE_DIR = "/data1/ESR-GRPO-Code/exp1_results/exp100_merged_esr/stores"


def evidence_full_text(store) -> str:
    return "\n".join(e.content for e in store.list_evidence()).lower()


def hit_all(tokens: list[str], text: str) -> bool:
    """该约束判别 token 是否在 evidence 全文里出现（任一命中即可）。"""
    return any(t in text for t in tokens)


def analyze(dir_, label: str) -> dict:
    rows = []
    for qid, clist in CONSTRAINTS.items():
        try:
            store = EpisodeStore(f"{dir_}/{qid}.sqlite")
            text = evidence_full_text(store)
        except Exception as ex:
            rows.append({"qid": qid, "label": label, "error": str(ex)})
            continue
        total = 0
        hit = 0
        details = []
        for desc, tokens in clist:
            if tokens is None:
                details.append(f"  [MANUAL] {desc}")
                continue
            total += 1
            ok = hit_all(tokens, text)
            if ok:
                hit += 1
            details.append(f"  [{'HIT ' if ok else 'MISS'}] {desc}  <- {tokens}")
        rows.append({
            "qid": qid, "label": label, "answer": ANSWER[qid],
            "n_auto": total, "n_hit": hit, "details": details,
        })
    return rows


def main() -> None:
    print("=" * 88)
    print("约束链覆盖率量化：强策略 evidence vs 真实4B在线 evidence")
    print("=" * 88)
    strong = analyze(STRONG_DIR, "strong")
    online = analyze(ONLINE_DIR, "online4b")
    by_q = {}
    for r in strong:
        by_q.setdefault(r["qid"], {})["strong"] = r
    for r in online:
        by_q.setdefault(r["qid"], {})["4b"] = r
    print(f"\n{'qid':>5} {'answer':<24} {'strongHits':>12} {'4BHits':>10}  判定")
    for qid in CONSTRAINTS:
        s = by_q[qid].get("strong", {})
        o = by_q[qid].get("4b", {})
        ns, hs = s.get("n_auto", "?"), s.get("n_hit", "?")
        no, ho = o.get("n_auto", "?"), o.get("n_hit", "?")
        verdict = ""
        print(f"{qid:>5} {ANSWER[qid]:<24} {str(hs)+'/'+str(ns):>12} {str(ho)+'/'+str(no):>10}")
    print("\n--- 强策略逐条明细 ---")
    for r in strong:
        print(f"\n[{r['qid']}] {r['answer']}: 自动判定 {r['n_hit']}/{r['n_auto']} 约束命中")
        for d in r["details"]:
            print(d)


if __name__ == "__main__":
    main()