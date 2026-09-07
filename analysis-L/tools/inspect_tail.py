"""检查单条 baseline/ESR run 的动作序列尾部: finish 触发点诊断。

用法: python scripts/experiment1_pipeline/inspect_tail.py <store.sqlite> [n]
"""
import json
import sqlite3
import sys


def main() -> None:
    path = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute("PRAGMA table_info(actions)")
    cols = [r[1] for r in cur.fetchall()]
    payload_col = "payload_json" if "payload_json" in cols else "payload"
    cur.execute(f"select {payload_col} from actions order by sequence_index")
    acts = [json.loads(r[0]) for r in cur.fetchall()]
    print(f"total actions: {len(acts)}")
    for a in acts[-n:]:
        md = a.get("metadata") or {}
        kind = a.get("kind")
        legal = a.get("legal")
        print(f"  [{a.get('sequence_index')}] {kind} legal={legal}")
        if kind == "finish":
            print("    answer:", str(md.get("answer", ""))[:120])
        elif kind == "search":
            print("    query:", str(md.get("query", ""))[:80], "| hits:", len(md.get("hits", [])))
        elif kind == "open_page":
            print("    docid:", md.get("docid"))
        elif kind == "verify_answer":
            print("    status:", md.get("verification_status"))
    con.close()


if __name__ == "__main__":
    main()
