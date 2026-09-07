#!/usr/bin/env python3
"""短板 A 离线重放：验证「方案 E' 观测对齐」能否救活 GOLD-MATCH 但 0-supported 的轨迹。

背景（2026-09-03，短板 A 量化）：
  100 条真实 ESR 轨迹里，有 12 条「最终 answer 含 gold、0 次 verifier supported」但未提交
  —— 疑似 4B verifier 对正确答案反复 needs_revision 的假打回。但那些 store 是【方案 E' 之前】
  跑的，当时 verify 喂的是 60k 全文（含 search 从未展示的越权实体），假打回可能正源于此。

本脚本对这 12 条轨迹离线重放：
  - 从 store 取『在线最后一次 verify 时模型给 answer + supporting_evidence』；
  - 每条 supporting evidence 的 content 用【方案 E' 的 chunk 视图】重建（_evidence_sort_query 排序基准；
    无 search_action_id 时回退 question）；
  - 用真实 4B OpenAICompatibleVerifier 重验该 (question, answer, chunk-view evidence)；
  - 对比在线 vs 离线重验的一致性与假打回是否消失。

用法：
  PYTHONPATH=/data1/ESR-GRPO/ESR-GRPO/src $VENV/bin/python replay_shortboardA.py \
      --stores /data1/ESR-GRPO-Code/exp1_results/exp100_merged_esr/stores \
      --report /data1/ESR-GRPO-Code/exp1_results/exp100_report.json \
      --verifier-url http://127.0.0.1:8005/v1 --model Qwen3.5-4B
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from esr_grpo.store import EpisodeStore
from esr_grpo.retrieval import EchoRetrievalClient
from esr_grpo.verification import OpenAICompatibleVerifier


def norm_match(gold: str, ans: str) -> bool:
    g = (gold or "").strip().lower()
    a = (ans or "").strip().lower()
    if not g or not a:
        return False
    if a in ("暂无候选", "(空/暂无候选)", "暂无候选答案 - 需要进一步搜索", "暂无充分证据，需要进一步搜索"):
        return False
    toks = g.split()[:3]
    if len(toks) >= 2 and " ".join(toks) in a:
        return True
    return g in a or a in g


def load_gold_match_unsubmitted(report_path: Path, stores_dir: Path) -> list[tuple[str, str, str]]:
    """返回 [(qid, gold, store_db)] 列表：未提交 + 最终answer含gold + 0次supported。"""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report = {r["query_id"]: r for r in report["esr"]}
    out: list[tuple[str, str, str]] = []
    for qid, r in report.items():
        if r.get("submitted"):
            continue
        db = stores_dir / f"{qid}.sqlite"
        if not db.exists():
            continue
        store = EpisodeStore(str(db))
        states = store.list_states()
        final_ans = states[-1].answer if states else ""
        if not norm_match(r["gold"], final_ans):
            continue
        # 确认 0 次 supported
        n_sup = sum(
            1 for a in store.list_actions()
            if a.kind.value == "verify_answer" and a.legal
            and (a.metadata or {}).get("verification_status") == "supported"
        )
        if n_sup == 0:
            out.append((qid, r["gold"], str(db)))
    return out


def replay_case(case: tuple[str, str, str], retriever, verifier) -> dict:
    qid, gold, db = case
    store = EpisodeStore(db)
    question = store.get_metadata("question")
    states = store.list_states()
    final = states[-1]
    answer = final.answer
    support = list(final.supporting_evidence)

    # 重建 chunk 视图证据（方案 E'：把每条 Evidence 的 content 换成 _chunk_view 文本）
    view_evidence = []
    for eid in support:
        ev = store.get_evidence(eid)
        q = _evidence_sort_query_store(store, ev)
        visible, view, cm = _chunk_view_stub(retriever, ev.source.docid, q, ev.content)
        view_evidence.append({"evidence_id": eid, "view": view, "content": visible,
                              "search_q": q, "docid": ev.source.docid})

    # 在线时该 evidence 的原始 content 长度（对比观测对齐前后）
    online_full_lens = [len(store.get_evidence(e).content) for e in support]

    # 真实 4B verifier 重验
    result = verifier.verify(question, answer, [store.get_evidence(e) for e in support])

    return {
        "qid": qid,
        "gold": gold,
        "question": question[:140],
        "answer": answer,
        "n_support": len(support),
        "online_full_lens": online_full_lens,
        "view_evidence": view_evidence,
        "replay_status": result.status.value,
        "replay_gaps": list(result.gaps),
        "replay_rationale": result.rationale,
        "gold_in_answer": norm_match(gold, answer),
    }


def _evidence_sort_query_store(store: EpisodeStore, ev) -> str:
    """方案 E' 排序基准：Evidence.search_action_id 对应 search 的 query，回退 question。"""
    if ev.search_action_id:
        try:
            act = store.get_action(ev.search_action_id)
            q = (act.metadata or {}).get("query")
            if q:
                return str(q)
        except Exception:
            pass
    return store.get_metadata("question") or ""


def _chunk_view_stub(retriever, docid: str, query: str, full: str, topk: int = 3) -> tuple[str, str, dict]:
    """离线重建 chunk 视图：复刻 environment._chunk_view（不含环境级 RLock/回退语义差异）。"""
    from esr_grpo.environment import ESREnvironment
    # 用一个最小的盘上建议：直接复用 ESREnvironment._chunk_view 的算法，但需要环境实例。
    # 为了不构造完整环境，这里用 InMemory 包装 retriever 的 get_doc_chunks + 手动拼接。
    try:
        chunks_call = getattr(retriever, "get_doc_chunks", None)
        raw_chunks = (chunks_call(docid, query, topk=topk).get("chunks")) or []
        items = sorted(
            (c for c in raw_chunks if (c.get("text") or "").strip()),
            key=lambda c: int(c.get("chunk_index", 0)),
        )
        parts = []
        chunk_meta = []
        for c in items:
            text = c["text"].strip()
            if not text:
                continue
            idx = int(c.get("chunk_index", 0))
            if parts:
                prev = parts[-1]
                max_ol = min(len(prev), len(text))
                ol = 0
                for k in range(max_ol, 0, -1):
                    if text[:k] == prev[-k:]:
                        ol = k
                        break
                if ol > 0:
                    text = text[ol:].strip()
                    if not text:
                        continue
            parts.append(text)
            chunk_meta.append({"chunk_index": idx, "score": c.get("score", 0.0)})
        if not parts:
            return full[:16000], "head", {}
        visible = "\n".join(f"[关键片段 #{m['chunk_index']}]\n{t}" for m, t in zip(chunk_meta, parts))
        return visible, "chunks", chunk_meta
    except Exception:
        return full[:16000], "head", {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--verifier-url", default="http://127.0.0.1:8005/v1")
    ap.add_argument("--model", default="Qwen3.5-4B")
    ap.add_argument("--out", default="/data1/ESR-GRPO-Code-L/analysis-L/replay_shortboardA_result.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    stores_dir = Path(args.stores)
    cases = load_gold_match_unsubmitted(Path(args.report), stores_dir)
    print(f"命中 GOLD-MATCH 且 0-supported 的未提交轨迹: {len(cases)} 条", file=sys.stderr)
    if args.limit:
        cases = cases[: args.limit]

    retriever = EchoRetrievalClient("http://127.0.0.1:8000")
    verifier = OpenAICompatibleVerifier(args.verifier_url, args.model)

    results = []
    for c in cases:
        print(f"  replaying {c[0]} (gold={c[1][:24]!r})...", file=sys.stderr)
        try:
            r = replay_case(c, retriever, verifier)
            results.append(r)
            print(f"    -> {r['replay_status']}  gaps={len(r['replay_gaps'])}", file=sys.stderr)
        except Exception as exc:
            print(f"    !! {c[0]} failed: {exc}", file=sys.stderr)
            results.append({"qid": c[0], "gold": c[1], "error": str(exc)})

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # 打印汇总
    ok = [r for r in results if r.get("replay_status")]
    supported = [r for r in ok if r["replay_status"] == "supported"]
    still_rev = [r for r in ok if r["replay_status"] == "needs_revision"]
    print(f"\n=== 汇总（{len(results)} 条重放）===")
    print(f"  supported (救活): {len(supported)}")
    print(f"  仍 needs_revision: {len(still_rev)}")
    for r in supported:
        print(f"    ++ {r['qid']}: gold={r['gold'][:22]!r} ans={r['answer'][:22]!r} 方案E'后 supported")
    for r in still_rev:
        print(f"    -- {r['qid']}: gold={r['gold'][:22]!r} ans={r['answer'][:22]!r} still needs_revision, gaps={len(r['replay_gaps'])}")
    err = [r for r in results if r.get("error")]
    if err:
        print(f"  重放异常: {len(err)}")
        for r in err:
            print(f"    !! {r['qid']}: {r['error'][:80]}")
    print(f"\n完整结果写入 {args.out}")


if __name__ == "__main__":
    main()