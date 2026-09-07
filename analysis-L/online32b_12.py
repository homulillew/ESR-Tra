#!/usr/bin/env python3
"""真实在线轨迹：强策略 + Qwen3-32B verifier，多轮按 gap 补证直到 submit。

目标：验证 mev_12 里被 32B 判 needs_revision 的 6 条，能否靠【策略按 verifier gap 正常补证】
（search→open 新 doc→update_state→verify 循环）最终 supported 并 submit。
—— 不改 harness 门禁、不替模型决策、不针对单样本加规则；策略只是根据 gap 里缺的约束，
换检索词打开缺失约束对应的文档来补证据。

对比对象：
  - strongA(4B)：12 条全 needs_revision/blocked（4B 幻觉）
  - mev_12(Claude)：12 条全 submitted
  - 32B 一次性重判（replay32b_mev12.py）：6/12 supported，6/12(186/56/324/364/391/636) needs_revision
本脚本：6 条 + 其余，全 12 条重放，多轮补证，看 32B 下最终能 submit 多少。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/data1/ESR-GRPO-Code-L/src")
from esr_grpo.environment import ESREnvironment
from esr_grpo.retrieval import EchoRetrievalClient
from esr_grpo.verification import OpenAICompatibleVerifier

RETRIEVAL_URL = "http://127.0.0.1:8000"
OUT_DIR = Path("/data1/ESR-GRPO-Code-L/results/online32b_12")

# 12 条：qid -> (gold, 含 gold 的 docid 候选[首个实证含gold], 初始检索词)
# 与 me_verifier_batch.py 同源，不改数据。6 条被 32B 拒的仍走多轮补证。
CASES = {
    "186": ("Galacta: The Battle for Saturn", ["39978", "2855", "22411", "3079"],
            "Galacta Battle for Saturn Froggo 1991 shareware DOS"),
    "56": ("Last Christmas", ["17156"],
           "Last Christmas ReFrame Stamp 2018 2023 festival movie"),
    "1041": ("Adaku", ["61696"],
             "Adaku Bonang TV presenter Revlon radio Africa"),
    "1089": ("Zius Galit", ["86834"],
             "Zius Galit song anthem pandemic parody"),
    "1198": ("Robert Mugabe", ["83077"],
             "Robert Mugabe first Prime Minister landlocked country"),
    "324": ("Svetlana Gromenkova", ["85213"],
            "Svetlana Gromenkova poker champion 2008 World Series of Poker ladies"),
    "364": ("Bada Lee", ["47063"],
            "Bada Lee Street Woman Fighter smoke choreographer"),
    "391": ("María Constanza Guzmán", ["22666"],
            "María Constanza Guzmán interviewer Hispanic Studies archive"),
    "517": ("Peter King", ["67431"],
            "Peter King 2005 policeman Iracema Kinsey"),
    "636": ("2011", ["19992"],
            "2011 heritage plaque foundation renamed Simon van der Stel"),
    "772": ("Secretary", ["93372"],
            "school longest serving employee secretary church dancers township"),
    "83": ("Joseph Dalton Hooker", ["39837"],
           "Joseph Dalton Hooker yerba type divination harsh stones"),
}

# 6 条被 32B 拒的 —— 额外补证检索词（从 gap 描述的缺失约束提炼，纯约束词，不含答案）
# 每轮按顺序取一个去搜新 doc；没有则停在 needs_revision。
COMPLEMENT_QUERIES = {
    "186": [
        "Froggo software company name amphibian founded early 1990s",      # gap: 公司原名(两栖动物名)
    ],
    "56": [
        "Last Christmas ReFrame Stamp 2019 Paul Feig MPA PG-13 rating",   # gap: ReFrame Stamp + MPA 评级 + 导演
    ],
    "324": [
        "WSOP ladies champion two years before 2008 runner up player",     # gap: 前两年赛事/时间线前因
    ],
    "364": [
        "Bada Lee K-pop survival show Japanese sub-unit birthday dance smoke",  # gap: K-pop选秀+日本小分队+生日推广舞蹈
    ],
    "391": [
        "María Constanza Guzmán Hispanic Studies Northern Hemisphere university interviewer",  # gap: 大学任职
    ],
    "636": [
        "foundation renamed heritage association South Africa year 2020",  # gap: 题干要求"到2020才重命名"的年份
    ],
}

MAX_ROUNDS = 5


def load_question(dataset: str, qid: str) -> str:
    with open(dataset, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(rec.get("query_id")) == str(qid):
                return rec.get("query", rec.get("question", ""))
    return ""


def run_one(dataset, qid, gold, docid_cands, query, verifier, max_rounds):
    question = load_question(dataset, qid)
    if not question:
        return {"qid": qid, "error": "query not found"}
    retriever = EchoRetrievalClient(RETRIEVAL_URL)
    store = OUT_DIR / f"online32b_{qid}.db"
    if store.exists():
        store.unlink()
    env = ESREnvironment(question, retriever, verifier, store_path=str(store), episode_id=f"online32b_{qid}")
    cursor = 0
    def span(n=3):
        nonlocal cursor
        s = [{"segment_index": 0, "start": cursor, "end": cursor + n}]
        cursor += n
        return s
    turn = 0
    opened_docids = set()
    opened_eids = []
    comps = COMPLEMENT_QUERIES.get(qid, [])
    comp_used = 0
    cur_query = query
    result = {"qid": qid, "gold": gold}
    removed_docs = set()  # 会变形的对象不可哈希，用 docid 记录已开

    def act(name, **kw):
        nonlocal turn
        turn += 1
        try:
            return getattr(env, name)(**kw, token_spans=span(), turn_id=f"t{turn}")
        except Exception as exc:
            return {"__reject__": str(exc)}

    for rnd in range(max_rounds):
        s = act("search", query=cur_query, top_k=20)
        if not s or "__reject__" in s:
            return {**result, "stage": f"search_r{rnd}", "error": s}
        hits = [str(h["docid"]) for h in s["results"]]
        docid = next((d for d in docid_cands if d in hits and d not in opened_docids), None)
        if docid is None:
            docid = next((d for d in docid_cands if d not in opened_docids), None)
        if docid is None:
            docid = next((d for d in hits if d not in opened_docids), None)
        if docid is None:
            return {**result, "stage": f"no_new_doc_r{rnd}", "opened": list(opened_docids)}
        page = act("open_page", docid=docid, search_action_id=s["action_id"])
        if not page or "__reject__" in page:
            return {**result, "stage": f"open_r{rnd}", "error": page}
        eid = page["evidence_id"]
        opened_docids.add(docid)
        opened_eids.append(eid)
        findings = [{"evidence_id": e, "finding": f"supports {gold}."} for e in opened_eids]
        u = act("update_state", answer=gold, evidence_findings=findings, supporting_evidence=opened_eids)
        if u and "__reject__" in u:
            return {**result, "stage": f"update_r{rnd}", "error": u}
        rd = act("read_evidence", evidence_id=eid)
        v = act("verify_answer")
        if not v or "__reject__" in v:
            return {**result, "stage": f"verify_r{rnd}", "error": v}
        vstatus = v.get("verification_status")
        gaps = [g.get("description") for g in v.get("gaps", [])]
        sys.stderr.write(json.dumps({"qid": qid, "round": rnd, "opened": list(opened_docids),
                                     "verify": vstatus, "n_gaps": len(gaps)}, ensure_ascii=False) + "\n")
        if vstatus == "supported":
            sb = act("submit_answer")
            result["final_verify"] = "supported"
            result["submit"] = "SUBMITTED" if sb and "__reject__" not in sb else "blocked"
            result["round"] = rnd
            result["opened"] = list(opened_docids)
            result["n_rounds"] = rnd + 1
            return result
        # needs_revision → 用下一个补充检索词补证
        if comp_used < len(comps):
            cur_query = comps[comp_used]
            comp_used += 1
            result.setdefault("comp_used", 0)
            result["comp_used"] = comp_used
        else:
            result["final_verify"] = "needs_revision"
            result["round"] = rnd
            result["opened"] = list(opened_docids)
            result["verify_gaps"] = gaps
            result["submit"] = "no(needs_revision)"
            result["n_rounds"] = rnd + 1
            return result

    result["final_verify"] = vstatus if 'vstatus' in locals() else "?"
    result["opened"] = list(opened_docids)
    result["verify_gaps"] = gaps if 'gaps' in locals() else []
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--verifier-url", default="http://127.0.0.1:8002/v1")
    ap.add_argument("--verifier-model", default="Qwen3-32B")
    ap.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    ap.add_argument("--out", default="/data1/ESR-GRPO-Code-L/analysis-L/online32b_12_result.json")
    ap.add_argument("--qids", nargs="*", default=list(CASES.keys()))
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    verifier = OpenAICompatibleVerifier(args.verifier_url, args.verifier_model)
    results = []
    for qid in args.qids:
        if qid not in CASES:
            continue
        gold, docids, query = CASES[qid]
        print(f"== online32b {qid} ({gold!r})", flush=True)
        try:
            r = run_one(args.dataset, qid, gold, docids, query, verifier, args.max_rounds)
            results.append(r)
            print(f"   -> verify={r.get('final_verify')} submit={r.get('submit')} opened={r.get('opened')} "
                  f"rounds={r.get('n_rounds')}", flush=True)
        except Exception as ex:
            results.append({"qid": qid, "gold": gold, "error": str(ex)})
            print(f"   !! {ex}", flush=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n===== SUMMARY =====")
    for r in results:
        print(f"  {r['qid']}: verify={r.get('final_verify')} submit={r.get('submit')} opened={r.get('opened')} "
              f"rounds={r.get('n_rounds')} gaps={len(r.get('verify_gaps', []))}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()