#!/usr/bin/env python3
"""强策略(我)标准评测 12 条 —— ESR vs baseline 评测与指标。

读 results/strong12/raw_results.jsonl（每局一行）：
  {qid, mode, outcome, turns, submitted_answer, tool_calls, opened_docids, verify_rounds}
gold 用离线 ExactMatchJudge（ExactMatchJudge.judge：gold 归一化子串 ∈ submitted_answer），
gold 仅这里进判别，策略运行期从不接触 gold。

核心对比指标（每臂）：
  提交率                  submitted / N
  Accuracy(仅已提交)      correct / submitted
  Accuracy(含未提交)      correct / N                      （未提交计未答=错）
  平均工具调用轮数 total   平均 total_tool_calls/turns
  平均 search / open / read / update / verify / turns

输出：
  results/strong12/eval_summary.json
  results/strong12/eval_report.md   （对比表 + 逐条判定表）

用法：
  python analysis-L/evaluate_strong12.py --dataset <jsonl> [--root results/strong12]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from esr_grpo.judge import ExactMatchJudge
from esr_grpo.browsecomp import load_examples

# 实验固定的 12 条（与 CASES 一致）
QIDS = ["186", "56", "1041", "1089", "1198", "324", "364", "391", "517", "636", "772", "83"]


def load_raw(root: Path) -> dict[tuple[str, str], dict]:
    """读 raw_results.jsonl -> {(qid, mode): record}。"""
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
    ap.add_argument("--root", default="/data1/ESR-GRPO-Code-L/results/strong12")
    args = ap.parse_args()

    examples = {ex.query_id: ex for ex in load_examples(args.dataset)}
    judge = ExactMatchJudge()
    rows = load_raw(Path(args.root))

    # 逐条判定
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
            if submitted:
                res = judge.judge("", answer, gold)
                correct = res.correct
            else:
                correct = False
            per_case.append({
                "qid": qid, "mode": mode,
                "outcome": rec.get("outcome"),
                "submitted": submitted, "correct": correct,
                "answer": answer, "gold": gold,
                "turns": rec.get("turns"),
                "tool_calls": rec.get("tool_calls"),
                "verify_rounds": rec.get("verify_rounds"),
            })

    # 每臂汇总
    summary = {}
    for mode in ("esr", "baseline"):
        recs = [c for c in per_case if c["mode"] == mode]
        n = len(recs)
        sub = [c for c in recs if c["submitted"]]
        corr_all = [c for c in recs if c["correct"]]
        corr_sub = [c for c in sub if c["correct"]]
        avg = lambda key, subset, default=0.0: (
            sum(c.get(key) or 0 for c in subset) / len(subset) if subset else default)
        tc = [c["tool_calls"] for c in recs if c["tool_calls"]]
        avg_field = lambda k: (sum(c.get(k, 0) for c in tc) / len(tc)) if tc else 0.0
        summary[mode] = {
            "n": n,
            "submitted": len(sub),
            "submit_rate": len(sub) / n if n else 0.0,
            "acc_only_submitted": len(corr_sub) / len(sub) if sub else None,
            "acc_incl_unsubmitted": len(corr_all) / n if n else 0.0,
            "correct": len(corr_all),
            "avg_total_tool_calls": avg_field("total") if tc else None,
            "avg_turns": avg("turns", recs),
            "avg_search": avg_field("search"),
            "avg_open": avg_field("open_page"),
            "avg_read": avg_field("read_evidence"),
            "avg_update": avg_field("update_state"),
            "avg_verify": avg_field("verify_answer"),
        }

    out = {"cases": per_case, "summary": summary, "qids": QIDS}
    out_path = Path(args.root) / "eval_summary.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # 打印 markdown 报告
    lines = ["# 强策略标准评测 12 条（ESR vs baseline）", ""]
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