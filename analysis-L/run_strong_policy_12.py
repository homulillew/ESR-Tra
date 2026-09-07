#!/usr/bin/env python3
"""强策略(我)标准评测 12 条 —— ESR vs baseline 单局编排启动器。

用法（每次启动一局，我完成该局回填后再跑下一局，符合"忠实但慢"）：
  python analysis-L/run_strong_policy_12.py --dataset <jsonl> --qid 324 --mode esr
  python analysis-L/run_strong_policy_12.py --dataset <jsonl> --qid 324 --mode baseline
  # ... 依次跑完 12×2

行为：
  1) 以子进程调用 strong_policy_drive.py（--workdir results/strong12/workdir --
     workdir 里放 <qid>_<mode>.ctx.json / .act.json / .r<k>.verdict.json）。
  2) 等子进程结束（结束=已 submit/finish/max_turns），读回驱动返回的 result。
  3) 把 result 合并进 results/strong12/raw_results.jsonl（追加），并打印 summary。

store 轨迹写到 results/strong12/stores/<qid>_<mode>.sqlite（含 run 的 episode 轨迹）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRIVER = HERE / "strong_policy_drive.py"
VENV = "/data1/ESR-GRPO/ESR-GRPO/exper/arex_bcplus_native/.venv/bin/python"
SRC = "/data1/ESR-GRPO-Code-L/src"
OUT_ROOT = Path("/data1/ESR-GRPO-Code-L/results/strong12")


def _env() -> dict:
    import os
    e = dict(os.environ)
    e["PYTHONPATH"] = SRC + (os.pathsep + e["PYTHONPATH"] if e.get("PYTHONPATH") else "")
    return e


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--qid", required=True)
    ap.add_argument("--mode", required=True, choices=["esr", "baseline"])
    ap.add_argument("--max-turns", type=int, default=50)
    ap.add_argument("--search-top-k", type=int, default=20)
    ap.add_argument("--interactive-marker", default="marker", help="保留兼容，未用")
    args = ap.parse_args()

    stores = OUT_ROOT / "stores"
    workdir = OUT_ROOT / "workdir"
    stores.mkdir(parents=True, exist_ok=True)
    workdir.mkdir(parents=True, exist_ok=True)
    store = stores / f"{args.qid}_{args.mode}.sqlite"

    cmd = [VENV, str(DRIVER),
           "--dataset", args.dataset,
           "--query-id", args.qid,
           "--mode", args.mode,
           "--store", str(store),
           "--workdir", str(workdir),
           "--max-turns", str(args.max_turns),
           "--search-top-k", str(args.search_top_k)]
    print(f"== launch {args.qid} {args.mode} (store={store.name}) ==", flush=True)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=86400, env=_env())
    except subprocess.TimeoutExpired as ex:
        print(json.dumps({"qid": args.qid, "mode": args.mode, "error": "driver timed out"},
                         ensure_ascii=False))
        sys.exit(1)

    if proc.stdout.strip():
        try:
            tail = proc.stdout.strip().splitlines()[-1]
            result = json.loads(tail)
        except Exception as exc:
            result = {"qid": args.qid, "mode": args.mode,
                      "error": f"driver stdout not json: {exc}",
                      "stderr_tail": proc.stderr[-800:]}
    else:
        result = {"qid": args.qid, "mode": args.mode, "error": "driver no stdout",
                  "stderr_tail": proc.stderr[-800:]}

    if proc.returncode != 0:
        result.setdefault("error", f"driver rc={proc.returncode}")
        result.setdefault("stderr_tail", proc.stderr[-800:])

    raw = OUT_ROOT / "raw_results.jsonl"
    with open(raw, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(result, ensure_ascii=False) + "\n")

    print("---- result ----")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if proc.stderr.strip():
        print("---- stderr(tail) ----")
        print(proc.stderr[-1500:])


if __name__ == "__main__":
    main()