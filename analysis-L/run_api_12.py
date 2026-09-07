#!/usr/bin/env python3
"""api 驱动强策略标准评测 —— 并行编排 12 qid × 2 mode（无人工回填、无污染）。

每 (qid, mode) = 一个独立子进程，内部新建【全新 LanzClient session】 + 全新
ESREnvironment → 杜绝跨样本/跨方法污染（修复 strong12 中"同一个持续上下文逐局推进"）。

并行：有界 worker 池（--workers，默认 4），避免打爆 api 网关（用户提示 api 并行易 error）。
单局内部对 api 请求做指数退避重试（--retries，向 api_policy_drive 透传）；
若单局子进程因未知原因退出且非正常终止，编排层对其整体重跑（--subprocess-retries）。

输出：results/api12/raw_results.jsonl（追加，逐行 result dict）
store 轨迹：results/api12/stores/<qid>_<mode>.sqlite
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRIVER = HERE / "api_policy_drive.py"
VENV = "/data1/ESR-GRPO/ESR-GRPO/exper/arex_bcplus_native/.venv/bin/python"
SRC = "/data1/ESR-GRPO-Code-L/src"
OUT_ROOT = Path("/data1/ESR-GRPO-Code-L/results/api12")

# 与 strong12 相同的 12 条 BrowseComp-Plus 样本（保证与先前强策略结果可比）
QIDS = ["186", "56", "1041", "1089", "1198", "324", "364", "391", "517", "636", "772", "83"]
MODES = ["esr", "baseline"]


def _env() -> dict:
    e = dict(os.environ)
    e["PYTHONPATH"] = SRC + (os.pathsep + e["PYTHONPATH"] if e.get("PYTHONPATH") else "")
    return e


def run_one(qid: str, mode: str, *, dataset: str, max_turns: int, search_top_k: int,
            retries: int, subprocess_retries: int, stores: Path) -> dict:
    store = stores / f"{qid}_{mode}.sqlite"
    cmd = [VENV, str(DRIVER),
           "--dataset", dataset, "--query-id", qid, "--mode", mode,
           "--store", str(store), "--max-turns", str(max_turns),
           "--search-top-k", str(search_top_k), "--retries", str(retries)]
    last_err = None
    for attempt in range(1, subprocess_retries + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=max(600, max_turns * 120), env=_env())
        except subprocess.TimeoutExpired:
            last_err = f"driver timed out (attempt {attempt})"
            continue
        tail = (proc.stdout or "").strip().splitlines()
        if tail:
            try:
                result = json.loads(tail[-1])
            except Exception as exc:
                last_err = f"stdout not json: {exc}"
                continue
            result.setdefault("error", None)
            if proc.returncode != 0:
                result["error"] = f"driver rc={proc.returncode}: {proc.stderr[-300:]}"
            return result
        last_err = f"no stdout (rc={proc.returncode}): {proc.stderr[-300:]}"
    return {"qid": qid, "mode": mode, "outcome": "error", "error": last_err,
            "turns": 0, "submitted_answer": None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--max-turns", type=int, default=50)
    ap.add_argument("--search-top-k", type=int, default=20)
    ap.add_argument("--model", default="Lanz-Medium")
    ap.add_argument("--retries", type=int, default=5, help="单局内部 api 重试次数")
    ap.add_argument("--subprocess-retries", type=int, default=3, help="单局子进程整体重跑次数")
    ap.add_argument("--qids", default=",".join(QIDS), help="逗号分隔 qid 列表")
    ap.add_argument("--modes", default=",".join(MODES), help="逗号分隔 mode 列表")
    ap.add_argument("--workers", type=int, default=4, help="并行 worker 数")
    ap.add_argument("--only-missing", action="store_true", help="跳过 raw_results.jsonl 已存在的 (qid,mode)")
    args = ap.parse_args()

    qids = [q for q in args.qids.split(",") if q.strip()]
    modes = [m for m in args.modes.split(",") if m.strip()]

    stores = OUT_ROOT / "stores"
    stores.mkdir(parents=True, exist_ok=True)
    raw = OUT_ROOT / "raw_results.jsonl"

    done_keys = set()
    if args.only_missing and raw.exists():
        for line in raw.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            # 只跳过"正常终止"的结果；equiring error/max_turns 仍可重跑
            if r.get("outcome") in ("submitted",):
                done_keys.add((r.get("qid"), r.get("mode")))

    jobs = [(q, m) for q in qids for m in modes
            if not (args.only_missing and (q, m) in done_keys)]
    print(f"total jobs: {len(jobs)} (qids={qids}, modes={modes})", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(run_one, q, m, dataset=args.dataset, max_turns=args.max_turns,
                        search_top_k=args.search_top_k, retries=args.retries,
                        subprocess_retries=args.subprocess_retries, stores=stores): (q, m)
            for q, m in jobs
        }
        for fut in as_completed(futures):
            q, m = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:
                res = {"qid": q, "mode": m, "outcome": "error", "error": str(exc),
                       "turns": 0, "submitted_answer": None}
            results.append(res)
            marker = "OK" if res.get("outcome") == "submitted" else f"!!{res.get('outcome')}"
            print(f"[{marker}] {q}_{m}: turns={res.get('turns')} ans={str(res.get('submitted_answer'))[:40]!r}", flush=True)

    # 合并到既有 raw_results.jsonl（按 (qid, mode) 覆盖，避免子批重跑覆盖全量）
    merged: dict[tuple[str, str], dict] = {}
    if raw.exists():
        for line in raw.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            merged[(str(r.get("qid")), str(r.get("mode")))] = r
    for r in results:
        merged[(str(r.get("qid")), str(r.get("mode")))] = r
    merged_list = sorted(merged.values(), key=lambda r: (str(r.get("qid")), str(r.get("mode"))))
    with open(raw, "w", encoding="utf-8") as fh:
        for r in merged_list:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(merged_list)} rows (merged) -> {raw}", flush=True)


if __name__ == "__main__":
    main()