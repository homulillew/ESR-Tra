#!/usr/bin/env python3
"""从 strong12 各局 sqlite store 重建 raw_results.jsonl（权威轨迹）。

每个 store 的 actions 表记录了该局全部动作(含 legal:false 的被拒动作)及其 kind，
metadata 记录了 submitted_answer。据此重建 evaluate_strong12.py 期望的
raw_results.jsonl schema：{qid, mode, outcome, turns, submitted_answer, tool_calls,
opened_docids, verify_rounds}。

用法：
  python analysis-L/rebuild_raw_results.py --root results/strong12 --out results/strong12/raw_results.jsonl
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

QIDS = ["186", "56", "1041", "1089", "1198", "324", "364", "391", "517", "636", "772", "83"]


def mode_from_filename(stem: str) -> str:
    base = stem
    if base.endswith("_baseline"):
        return "baseline", base[: -len("_baseline")]
    if base.endswith("_base"):       # 1198_base.sqlite 的历史命名
        return "baseline", base[: -len("_base")]
    if base.endswith("_esr"):
        return "esr", base[: -len("_esr")]
    raise ValueError(f"unknown stem {stem!r}")


def process_store(path: Path, qid: str, mode: str) -> dict | None:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    meta: dict[str, str] = {}
    for r in cur.execute("SELECT key, value_json FROM metadata"):
        meta[r["key"]] = json.loads(r["value_json"]) if str(r["value_json"]).startswith(("[", "{")) else json.loads(r["value_json"])

    submitted_answer = meta.get("submitted_answer") or ""

    actions = []
    for r in cur.execute("SELECT action_id, sequence_index, payload_json FROM actions ORDER BY sequence_index"):
        p = json.loads(r["payload_json"])
        actions.append(p)

    conn.close()

    if not actions:
        return {"qid": qid, "mode": mode, "error": "no_actions", "outcome": "no_record",
                "turns": None, "submitted_answer": submitted_answer, "tool_calls": None,
                "opened_docids": [], "verify_rounds": None}

    # tool_calls：按 kind 统计（含 legal:false 的被拒动作；与 driver._tool_counts 一致）
    from collections import Counter
    c: Counter = Counter()
    opened_docids: list[str] = []
    for p in actions:
        kind = p.get("kind")
        c[kind] += 1
        if kind == "open_page" and p.get("legal") and (p.get("metadata") or {}).get("docid"):
            opened_docids.append(str(p["metadata"]["docid"]))
    total_actions = len(actions)

    # outcome
    if submitted_answer:
        outcome = "submitted"
    else:
        outcome = "max_turns"

    # turns：等于动作数（driver 每执行一个动作 self.turn+1，含被拒；与 actions 行数一致）
    # 注意：driver 会在 submit/finish 后再自增一次才 break，故动作行数 = turn。
    verify_rounds = 0
    for p in actions:
        if p.get("kind") == "verify_answer" and p.get("legal"):
            md = p.get("metadata") or {}
            verify_rounds += 1

    return {
        "qid": qid,
        "mode": mode,
        "outcome": outcome,
        "turns": total_actions,
        "submitted_answer": submitted_answer,
        "tool_calls": {
            "search": c["search"], "open_page": c["open_page"], "read_evidence": c["read_evidence"],
            "update_state": c["update_state"], "verify_answer": c["verify_answer"],
            "submit_answer": c["submit_answer"], "finish": c["finish"], "total": total_actions,
        },
        "opened_docids": opened_docids,
        "verify_rounds": verify_rounds,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/data1/ESR-GRPO-Code-L/results/strong12")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    root = Path(args.root)
    stores = list((root / "stores").glob("*.sqlite"))
    by_key: dict[tuple[str, str], dict] = {}
    for sp in sorted(stores):
        mode, qid = mode_from_filename(sp.stem)
        rec = process_store(sp, qid, mode)
        by_key[(qid, mode)] = rec
        print(f"{qid} {mode:8s} outcome={rec['outcome']:9s} turns={rec['turns']} ans={ (rec['submitted_answer'] or '')[:36]!r}")

    # 补缺：12 qid × 2 mode 每格都应有
    missing = []
    for qid in QIDS:
        for mode in ("esr", "baseline"):
            if (qid, mode) not in by_key:
                missing.append((qid, mode))
    if missing:
        print("!! MISSING:", missing)

    out_path = Path(args.out) if args.out else (root / "raw_results.jsonl")
    with open(out_path, "w", encoding="utf-8") as fh:
        for qid in QIDS:
            for mode in ("esr", "baseline"):
                rec = by_key.get((qid, mode))
                if rec is None:
                    rec = {"qid": qid, "mode": mode, "error": "missing", "outcome": "no_record",
                           "turns": None, "submitted_answer": None, "tool_calls": None,
                           "opened_docids": [], "verify_rounds": None}
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()