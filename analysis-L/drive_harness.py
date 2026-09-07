#!/usr/bin/env python3
"""用【强模型】作为策略、驱动【真实 ESREnvironment】的对照实验驱动脚本。

目标：区分"4B 能力底" vs "harness 残留缺陷"。
做法：严格复用实验1的同一个 harness ——
  - retriever：真实 BM25 EchoRetrievalClient（:8000）
  - verifier ：真实 OpenAICompatibleVerifier（4B，同批量配置，policy GPU）
  - environment：真实 ESREnvironment 状态机 / my leak-gate / coverage / stale-id / verify
唯一被替换的是【谁产出下一动作】：由人类（更强策略）读取 render_context 给出工具调用。
每条动作都经 environment 的 .search/.open_page/.update_state/.verify_answer/.submit_answer
真实门禁执行，拒绝文案与批量完全一致。

交互协议（stdin 每行一个 JSON 命令）：
  {"action":"next"}                    -> 打印当前 render_context（含 next_step_guidance）
  {"action":"act","name":"search","args":{"query":"..."}}
  {"action":"act","name":"open_page","args":{"docid":"d1","search_action_id":"a1"}}
  {"action":"act","name":"read_evidence","args":{"evidence_id":"e1"}}
  {"action":"act","name":"update_state","args":{"answer":"...","evidence_findings":[...],"supporting_evidence":[...]}}
  {"action":"act","name":"verify_answer","args":{}}
  {"action":"act","name":"submit_answer","args":{}}
  {"action":"end"}                      -> 打印最终 summary + 动作序列
每回合 turn_id 自动递增，token_spans 用占位自增（与批量一致的可视化性质）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from esr_grpo.environment import ESREnvironment
from esr_grpo.retrieval import EchoRetrievalClient
from esr_grpo.verification import OpenAICompatibleVerifier

RETRIEVAL_URL = "http://127.0.0.1:8000"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--query-id", required=True)
    ap.add_argument("--store", required=True, help="sqlite 输出路径")
    ap.add_argument("--policy-url", default="http://127.0.0.1:8005/v1")
    ap.add_argument("--policy-model", default="Qwen3.5-4B")
    ap.add_argument("--max-turns", type=int, default=50)
    args = ap.parse_args()

    # 取真实 query
    question = None
    with open(args.dataset, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(rec.get("query_id")) == str(args.query_id):
                question = rec.get("query", rec.get("question"))
                break
    if not question:
        print(json.dumps({"error": f"query {args.query_id} not found"}, ensure_ascii=False)); sys.exit(2)

    store = Path(args.store)
    if store.exists():
        store.unlink()
    retriever = EchoRetrievalClient(RETRIEVAL_URL)
    verifier = OpenAICompatibleVerifier(args.policy_url, args.policy_model)
    env = ESREnvironment(question, retriever, verifier, store_path=str(store))

    cursor = 0

    def span(n: int = 3) -> list:
        nonlocal cursor
        s = [{"segment_index": 0, "start": cursor, "end": cursor + n}]
        cursor += n
        return s

    turn = 0
    outcome = None
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        cmd = json.loads(line)
        action = cmd.get("action")
        if action == "end":
            break
        if action == "next":
            print(json.dumps({"turn": turn, "context": env.render_context(mode="esr")},
                             ensure_ascii=False, default=str))
            sys.stdout.flush()
            continue
        if action == "act":
            name = cmd.get("name")
            aargs = cmd.get("args") or {}
            turn += 1
            try:
                if name == "search":
                    r = env.search(aargs["query"], token_spans=span(), turn_id=f"t{turn}")
                    print(json.dumps({"legal": True, "kind": "search",
                                      "action_id": r["action_id"], "hits": r["results"]},
                                     ensure_ascii=False, default=str))
                elif name == "open_page":
                    r = env.open_page(aargs["docid"], search_action_id=aargs["search_action_id"],
                                      token_spans=span(), turn_id=f"t{turn}")
                    print(json.dumps({"legal": True, "kind": "open_page", "action_id": r["action_id"],
                                      "evidence_id": r["evidence_id"], "source": r.get("source"),
                                      "view": r.get("view"), "chunks": r.get("chunks"),
                                      "content": r.get("content", ""), "truncated": r.get("truncated"),
                                      "stored_content_chars": r.get("stored_content_chars")},
                                     ensure_ascii=False, default=str))
                elif name == "read_evidence":
                    r = env.read_evidence(aargs["evidence_id"],
                                          token_spans=span(), turn_id=f"t{turn}")
                    print(json.dumps({"legal": True, "kind": "read_evidence", "action_id": r["action_id"],
                                      "view": r.get("view"), "chunks": r.get("chunks"),
                                      "content": r.get("content", "")}, ensure_ascii=False, default=str))
                elif name == "update_state":
                    r = env.update_state(aargs.get("answer", ""),
                                         aargs.get("evidence_findings", []),
                                         aargs.get("supporting_evidence", []),
                                         token_spans=span(), turn_id=f"t{turn}")
                    print(json.dumps({"legal": True, "kind": "update_state", "result": r},
                                     ensure_ascii=False, default=str))
                elif name == "verify_answer":
                    r = env.verify_answer(token_spans=span(), turn_id=f"t{turn}")
                    print(json.dumps({"legal": True, "kind": "verify_answer", "result": r},
                                     ensure_ascii=False, default=str))
                elif name == "submit_answer":
                    r = env.submit_answer(token_spans=span(), turn_id=f"t{turn}")
                    print(json.dumps({"legal": True, "kind": "submit_answer", "result": r,
                                      "submitted_answer": env.submitted_answer},
                                     ensure_ascii=False, default=str))
                    outcome = "submitted"
                else:
                    print(json.dumps({"error": f"unknown tool {name}"}, ensure_ascii=False))
            except Exception as exc:
                # 非法动作用 IllegalActionError 抛出以记录轨迹 —— 与批量同一语义
                print(json.dumps({"legal": False, "kind": name, "rejected": str(exc)},
                                 ensure_ascii=False, default=str))
            sys.stdout.flush()
            if turn >= args.max_turns and outcome is None:
                outcome = "max_turns"
            if outcome:
                break
    # 收尾摘要
    from esr_grpo.environment import ActionKind
    acts = env.store.list_actions()
    summary = {
        "query_id": args.query_id,
        "outcome": outcome or "ended",
        "submitted_answer": env.submitted_answer,
        "turns": turn,
        "actions": [{"turn": a.turn_id, "kind": a.kind.value, "legal": a.legal,
                     "note": (a.metadata.get("note") or "")[:120] if a.metadata else "",
                     "rejected": str((a.metadata.get("error") if a.metadata else "") or "")[:120]}
                    for a in acts],
    }
    print(json.dumps({"final": summary}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()