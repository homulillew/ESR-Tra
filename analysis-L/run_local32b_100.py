#!/usr/bin/env python3
"""本地 Qwen3-32B 强策略标准评测 —— 并行编排随机 100 qid × 2 mode（全自动、无人工回填）。

每 (qid, mode) = 一个独立子进程，内部新建【全新 Local32BSession】+ 全新 ESREnvironment
→ 杜绝跨样本/跨方法污染（同 api12 设计）。

- 抽样：--seed 固定，从数据集按文件序取 query_id 列表，random.sample(全量, N) 抽取，
  **不排除**原 12 条（用户裁定）。默认 seed=20260904，N=100。
- max_turns 默认 100（32B 策略高轮次上限）。
- 并行：有界 worker 池（--workers 默认 2，本地单个 TP=2 32B 承载能力有限，过高互相拖慢）。
- 单局内部对 32B api 请求做指数退避重试；子进程非正常终止可整体重跑。
- raw_results.jsonl 合并式 upsert（按 (qid,mode) 覆盖，防子批重跑覆盖全量）。

输出：results/local32b100/raw_results.jsonl；轨迹 stores/<qid>_<mode>.sqlite
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRIVER = HERE / "local32b_policy_drive.py"
VENV = "/data1/ESR-GRPO/ESR-GRPO/exper/arex_bcplus_native/.venv/bin/python"
SRC = "/data1/ESR-GRPO-Code-L/src"
OUT_ROOT = Path("/data1/ESR-GRPO-Code-L/results/local32b100")


def dataset_query_ids(dataset: str) -> list[str]:
    """按文件行序收集所有 query_id（用于确定性 seed 抽样）。"""
    ids = []
    with open(dataset, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            qid = rec.get("query_id")
            if qid is not None:
                ids.append(str(qid))
    return ids


def build_qids(dataset: str, seed: int | None, n: int, explicit: str | None) -> list[str]:
    if explicit:
        return [q for q in explicit.split(",") if q.strip()]
    all_ids = dataset_query_ids(dataset)
    if seed is None:
        # 无 seed：取前 n（确定性顺序），便于调试
        return all_ids[:n]
    rng = random.Random(seed)
    return [all_ids[i] for i in rng.sample(range(len(all_ids)), min(n, len(all_ids)))]


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
            # max_turns=100 → 放宽容限（每局可能很久）
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=max(1800, max_turns * 240), env=_env())
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
    ap.add_argument("--n", type=int, default=100, help="随机抽多少条")
    ap.add_argument("--seed", type=int, default=20260904, help="random seed；None=取前n")
    ap.add_argument("--max-turns", type=int, default=100)
    ap.add_argument("--search-top-k", type=int, default=20)
    ap.add_argument("--retries", type=int, default=5)
    ap.add_argument("--subprocess-retries", type=int, default=3)
    ap.add_argument("--qids", default=None, help="逗号分隔 qid 列表（覆盖抽样）")
    ap.add_argument("--modes", default="esr,baseline")
    ap.add_argument("--workers", type=int, default=2, help="本地32B并发 worker 数")
    ap.add_argument("--only-missing", action="store_true", help="跳过 raw_results.jsonl 已正常提交的 (qid,mode)")
    args = ap.parse_args()

    qids = build_qids(args.dataset, args.seed, args.n, args.qids)
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
            if r.get("outcome") in ("submitted",):
                done_keys.add((str(r.get("qid")), str(r.get("mode"))))

    jobs = [(q, m) for q in qids for m in modes
            if not (args.only_missing and (q, m) in done_keys)]
    print(f"sampled {len(qids)} qids; total jobs: {len(jobs)} "
          f"(seed={args.seed}, n={args.n}, workers={args.workers}, max_turns={args.max_turns})", flush=True)

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

    # 合并到既有 raw_results.jsonl（按 (qid, mode) 覆盖，防子批覆盖全量）
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