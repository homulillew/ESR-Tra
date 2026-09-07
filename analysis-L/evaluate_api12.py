#!/usr/bin/env python3
"""api 驱动强策略标准评测 12 条 —— ESR vs baseline 评测与指标。

与 evaluate_strong12.py 同逻辑，仅指向 results/api12 输出（api 自动、无人工回填）。
读 results/api12/raw_results.jsonl，gold 用离线 ExactMatchJudge，运行期不接触 gold。

输出：
  results/api12/eval_summary.json
  results/api12/eval_report.md

用法：
  python analysis-L/evaluate_api12.py --dataset <jsonl> [--root results/api12]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from esr_grpo.judge import ExactMatchJudge
from esr_grpo.browsecomp import load_examples

QIDS = ["186", "56", "1041", "1089", "1198", "324", "364", "391", "517", "636", "772", "83"]


def load_raw(root: Path) -> dict[tuple[str, str], dict]:
    raw = root / "raw_results.jsonl"
    rows = {}
    if raw.exists():
        for line in open(raw, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            rows[(str(r.get("qid")), str(r.get("mode")))] = r
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--root", default="/data1/ESR-GRPO-Code-L/results/api12")
    args = ap.parse_args()

    examples = {ex.query_id: ex for ex in load_examples(args.dataset)}
    judge = ExactMatchJudge()
    rows = load_raw(Path(args.root))

    per_case = []
    for qid in QIDS:
        for mode in ("esr", "baseline"):
            rec = rows.get((qid, mode))
            gold = (examples.get(qid) or type("E", (), {"answer": ""})()).answer
            if rec is None or rec.get("error"):
                per_case.append({
                    "qid": qid, "mode": mode,
                    "outcome": rec.get("outcome") if rec else "no_record",
                    "submitted": False, "correct": False,
                    "answer": rec.get("submitted_answer") if rec else None,
                    "gold": gold, "error": rec.get("error") if rec else "missing",
                    "turns": None, "tool_calls": None,
                })
                continue
            answer = rec.get("submitted_answer") or ""
            submitted = bool(answer)
            correct = False
            if submitted:
                correct = judge.judge("", answer, gold).correct
            per_case.append({
                "qid": qid, "mode": mode, "outcome": rec.get("outcome"),
                "submitted": submitted, "correct": correct,
                "answer": answer, "gold": gold,
                "turns": rec.get("turns"), "tool_calls": rec.get("tool_calls"),
                "verify_rounds": rec.get("verify_rounds"),
            })

    summary = {}
    for mode in ("esr", "baseline"):
        recs = [c for c in per_case if c["mode"] == mode]
        n = len(recs)
        sub = [c for c in recs if c["submitted"]]
        corr_all = [c for c in recs if c["correct"]]
        corr_sub = [c for c in sub if c["correct"]]
        tc = [c["tool_calls"] for c in recs if c["tool_calls"]]
        avg_field = lambda k: (sum(c.get(k, 0) for c in tc) / len(tc)) if tc else 0.0
        summary[mode] = {
            "n": n, "submitted": len(sub),
            "submit_rate": len(sub) / n if n else 0.0,
            "acc_only_submitted": len(corr_sub) / len(sub) if sub else None,
            "acc_incl_unsubmitted": len(corr_all) / n if n else 0.0,
            "correct": len(corr_all),
            "avg_total_tool_calls": avg_field("total") if tc else None,
            "avg_turns": (sum(c.get("turns") or 0 for c in recs) / len(recs)) if recs else 0.0,
            "avg_search": avg_field("search"),
            "avg_open": avg_field("open_page"),
            "avg_read": avg_field("read_evidence"),
            "avg_update": avg_field("update_state"),
            "avg_verify": avg_field("verify_answer"),
        }

    out = {"cases": per_case, "summary": summary, "qids": QIDS}
    (Path(args.root) / "eval_summary.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 强策略标准评测 12 条（api 自动，ESR vs baseline）", ""]
    lines += ["| 指标 | ESR | baseline |", "|------|-----|----------|"]
    rows_t = [
        ("提交率", "submit_rate", "{:.0%}"),
        ("Accuracy (仅已提交)", "acc_only_submitted", "{:.0%}"),
        ("Accuracy (含未提交)", "acc_incl_unsubmitted", "{:.0%}"),
        ("平均工具调用轮数 total", "avg_total_tool_calls", "{:.1f}"),
        ("平均 turns", "avg_turns", "{:.1f}"),
        ("平均 search", "avg_search", "{:.1f}"),
        ("平均 open_page", "avg_open", "{:.1f}"),
        ("平均 read_evidence", "avg_read", "{:.1f}"),
        ("平均 update_state", "avg_update", "{:.1f}"),
        ("平均 verify_answer", "avg_verify", "{:.1f}"),
    ]
    for label, key, fmt in rows_t:
        esr = summary["esr"].get(key)
        base = summary["baseline"].get(key)
        esr_s = fmt.format(esr) if isinstance(esr, float) else ("-" if esr is None else str(esr))
        base_s = fmt.format(base) if isinstance(base, float) else ("-" if base is None else str(base))
        lines.append(f"| {label} | {esr_s} | {base_s} |")
    lines.append("")
    lines += ["## 逐条判定", ""]
    lines += ["| qid | mode | outcome | submitted | correct | answer | gold | turns | tool_total |", "|---|---|---|---|---|---|---|---|---|"]
    for c in per_case:
        ans = (c["answer"] or "")[:28].replace("|", "/")
        gld = (c["gold"] or "")[:28].replace("|", "/")
        tt = (c["tool_calls"] or {}).get("total") if c["tool_calls"] else None
        lines.append(f"| {c['qid']} | {c['mode']} | {c['outcome']} | {c['submitted']} | {c['correct']} | {ans} | {gld} | {c['turns']} | {tt} |")
    lines.append("")
    report = "\n".join(lines)
    (Path(args.root) / "eval_report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()