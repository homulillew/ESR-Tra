#!/usr/bin/env python3
"""mev_12 基线重放：用 Qwen3-32B verifier 重判 12 条（纯 verifier 对比）。

基线 mev_12 = 强策略 + Claude 当 verifier + 真实 harness，12 条全部 submitted。
本脚本从 12 条 mev_12 sqlite 账本里重建【每条 verify 时的 (question, answer, evidence 原文)】，
用 OpenAICompatibleVerifier("http://127.0.0.1:8002/v1", "Qwen3-32B") 重判 supported/needs_revision，
与 4B(strongA) 和 Claude(mev_12) 对比。不重跑检索、不喂标准答案以外的注入。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, "/data1/ESR-GRPO-Code-L/src")
from esr_grpo.models import Evidence, EvidenceSource
from esr_grpo.verification import OpenAICompatibleVerifier

MEV_DIR = Path("/data1/ESR-GRPO-Code-L/results/mev_12")
QIDS = ["186", "56", "1041", "1089", "1198", "324",
        "364", "391", "517", "636", "772", "83"]


def load_question(qid: str) -> str:
    with open("/data1/ESR-GRPO/BrowseComp-Plus/data/prepared/browsecomp_plus_decrypted.jsonl",
              encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if str(rec.get("query_id")) == str(qid):
                return rec.get("query", rec.get("question", ""))
    return ""


def rebuild_case(db: Path) -> dict:
    con = sqlite3.connect(str(db))
    def meta(key):
        r = con.execute("SELECT value_json FROM metadata WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else None

    qid = Path(db).stem.replace("mev_", "")
    question = meta("question") or load_question(qid)
    answer = meta("submit_action_id") and None  # placeholder
    # submit action 定位最终轮 verify 的 (answer, referenced evidence)
    submit_aid = meta("submit_action_id")
    row = con.execute("SELECT payload_json FROM actions WHERE action_id=?"
                      , (submit_aid,)).fetchone()
    submit_payload = json.loads(row[0])
    answer = submit_payload["metadata"]["answer"]
    ref_eids = list(submit_payload["referenced_evidence_ids"])

    evidence = []
    for eid in ref_eids:
        er = con.execute("SELECT source_key, payload_json FROM evidence WHERE evidence_id=?"
                         , (eid,)).fetchone()
        if not er:
            evidence.append({"evidence_id": eid, "docid": "?", "content": "(missing)"})
            continue
        src_key, payload = er[0], json.loads(er[1])
        title = payload.get("title") or src_key
        evidence.append({"evidence_id": eid, "docid": src_key, "title": title,
                         "content": payload["content"], "sha": payload.get("content_sha256")})
    con.close()
    return {"qid": qid, "question": question, "answer": answer, "evidence": evidence,
            "n_evidence": len(evidence), "submit_aid": submit_aid}


def run(verifier_url: str, model: str, out: Path) -> None:
    verifier = OpenAICompatibleVerifier(verifier_url, model)
    results = []
    for qid in QIDS:
        db = MEV_DIR / f"mev_{qid}.db"
        if not db.exists():
            results.append({"qid": qid, "error": "db not found"})
            print(f"  !! {qid}: db missing", flush=True)
            continue
        case = rebuild_case(db)
        ev_objs = [Evidence(
            evidence_id=e["evidence_id"],
            source=EvidenceSource(docid=e["docid"], url="", title=e["title"]),
            content=e["content"],
            content_sha256=e["sha"] or "",
            created_by_action_id="",
            search_action_id=None,
            created_at="0",
        ) for e in case["evidence"]]
        print(f"== {qid}: verify (answer={case['answer']!r}, ev={len(ev_objs)})", flush=True)
        try:
            res = verifier.verify(case["question"], case["answer"], ev_objs)
            verdict = {
                "qid": qid,
                "status": res.status.value,
                "n_gaps": len(res.gaps),
                "gaps": [str(g) for g in res.gaps],
                "rationale": res.rationale,
                "answer": case["answer"],
                "evidence_ids": [e["evidence_id"] for e in case["evidence"]],
                "docids": [e["docid"] for e in case["evidence"]],
            }
            results.append(verdict)
            print(f"   -> {res.status.value}  gaps={len(res.gaps)}", flush=True)
        except Exception as ex:
            results.append({"qid": qid, "error": str(ex)})
            print(f"   !! {ex}", flush=True)

    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== SUMMARY ===")
    sup = [r for r in results if r.get("status") == "supported"]
    rev = [r for r in results if r.get("status") == "needs_revision"]
    err = [r for r in results if r.get("error")]
    print(f"supported: {len(sup)}/12 -> {[r['qid'] for r in sup]}")
    print(f"needs_revision: {len(rev)}/12 -> {[r['qid'] for r in rev]}")
    if err:
        print(f"errors: {len(err)}")
    print(f"\ncomplete results: {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verifier-url", default="http://127.0.0.1:8002/v1")
    ap.add_argument("--model", default="Qwen3-32B")
    ap.add_argument("--out", default="/data1/ESR-GRPO-Code-L/analysis-L/replay32b_mev12_result.json")
    args = ap.parse_args()
    run(args.verifier_url, args.model, Path(args.out))