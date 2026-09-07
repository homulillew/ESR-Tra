#!/usr/bin/env python3
"""本地32B ESR bad case 深度分析：从轨迹账本重建每局行为并分类失败模式。

读 results/local32b100/stores/<qid>_esr.sqlite，按 actions 时序重建每局：
  - 工具分布（search/open/read/update/verify/submit/finish）
  - verify 轮次数、各轮 status + gaps + rationale
  - 是否更新过候选答案、提交前答案/支持证据/gaps
  - 是否出现"打满轮次不提交"（max_turns）
配合 raw_results 的 outcome 与离线 ExactMatch 判定，分三类产出明细。
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

ROOT = Path("/data1/ESR-GRPO-Code-L/results/local32b100")
STORES = ROOT / "stores"


def load_actions(store: Path) -> list[dict]:
    acts = []
    if not store.exists():
        return acts
    db = sqlite3.connect(str(store))
    for aorder, payload in db.execute(
            "select sequence_index, payload_json from actions order by sequence_index"):
        try:
            p = json.loads(payload)
        except Exception:
            continue
        p["_seq"] = aorder
        acts.append(p)
    db.close()
    return acts


def per_episode(qid: str) -> dict:
    acts = load_actions(STORES / f"{qid}_esr.sqlite")
    kinds = {}          # kind -> count
    verifies = []       # 每轮 verify 的 status/gaps/rationale
    updates = []        # update_state 的 answer/findings
    searches = []       # query + hits len + top docids
    opened = set()
    last_update_before_verify = None
    final_verify = None
    for a in acts:
        k = a.get("kind")
        kinds[k] = kinds.get(k, 0) + 1
        md = a.get("metadata", {}) or {}
        if k == "verify_answer":
            status = md.get("verification_status")
            rationale = md.get("rationale")
            verifies.append({
                "round": len(verifies) + 1,
                "status": status,
                "created_gaps": md.get("created_gap_ids", []),
                "resolved_gaps": md.get("resolved_gap_ids", []),
                "rationale": (rationale or "")[:160],
            })
            final_verify = verifies[-1]
        elif k == "update_state":
            updates.append({
                "answer": md.get("answer"),
                "supporting": md.get("supporting_evidence"),
                "gaps": md.get("gaps"),
            })
            last_update_before_verify = updates[-1]
        elif k == "search":
            query = md.get("query")
            hits = md.get("hits", []) or []
            searches.append({
                "query": query,
                "nhits": len(hits) if isinstance(hits, list) else 0,
                "top_docid": (hits[0].get("docid") if hits and isinstance(hits[0], dict) else None),
                "top_docids": [h.get("docid") for h in hits[:5] if isinstance(h, dict)][:5],
            })
        elif k == "open_page":
            if md.get("docid"):
                opened.add(str(md.get("docid")))
    return {
        "qid": qid,
        "kinds": kinds,
        "searches": searches,
        "opened_docids": sorted(opened),
        "updates": updates,
        "verifies": verifies,
        "final_verify": final_verify,
        "n_distinct_queries": len({s["query"] for s in searches}),
        "n_repeat_search": sum(1 for i in range(1, len(searches)) if searches[i]["query"] == searches[i - 1]["query"]),
    }


def main() -> None:
    rows = {}
    raw = ROOT / "raw_results.jsonl"
    for line in open(raw, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["mode"] == "esr":
            rows[r["qid"]] = r

    out = []
    for qid, rec in rows.items():
        ep = per_episode(qid)
        ep["outcome"] = rec.get("outcome")
        ep["turns"] = rec.get("turns")
        ep["submitted_answer"] = rec.get("submitted_answer")
        out.append(ep)

    with open(ROOT / "badcase_analysis.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"analyzed {len(out)} esr episodes -> results/local32b100/badcase_analysis.json")

    # 汇总工具分布
    print("\n=== 工具分布（均值，62条未提交 vs 全部）===")
    for group, filt in [("全部ESR", lambda e: True),
                        ("max_turns", lambda e: e["outcome"] == "max_turns"),
                        ("submitted", lambda e: e["outcome"] != "max_turns")]:
        es = [e for e in out if filt(e)]
        if not es:
            continue
        agg = {}
        for k in ("search", "open_page", "read_evidence", "update_state", "verify_answer", "submit_answer", "finish"):
            vals = [e["kinds"].get(k, 0) for e in es]
            agg[k] = round(sum(vals) / len(es), 1)
        print(f"{group}(n={len(es)}): {agg}")


if __name__ == "__main__":
    main()