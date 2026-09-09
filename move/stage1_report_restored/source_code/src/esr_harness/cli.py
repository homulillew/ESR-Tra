"""Run, inspect and replay forward inference without invoking the legacy RL pipeline."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from .audit import ModelAuditor
from .client import ChatClient, ChatConfig, HFTokenCounter, UsageBudget
from .demo import smoke
from .engine import Harness
from .ledger import Ledger
from .protocol import Config, HarnessError, canonical, digest
from .prompts import POLICY_PROMPT_VERSION, policy_system
from .runner import replay, run, summary
from .views import EchoRetriever


def load_question(path: str, qid: str) -> str:
    matches = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            identity = row.get("query_id", row.get("qid", row.get("id")))
            if str(identity) == qid:
                question = row.get("query", row.get("question"))
                if not isinstance(question, str) or not question.strip():
                    raise ValueError("Selected dataset row has no question")
                matches.append(question.strip())
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one question for qid={qid}, got {len(matches)}")
    return matches[0]  # Gold/answers/document labels are deliberately not returned.


def code_revision() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(Path(__file__).resolve().parents[2]),
                                        "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
    except (subprocess.SubprocessError, OSError):
        return "unavailable"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ESR forward harness 2.1 (no training)")
    commands = p.add_subparsers(dest="command", required=True)
    s = commands.add_parser("smoke", help="CPU synthetic repair fixture; no model or retrieval services")
    s.add_argument("--store", default=":memory:")
    r = commands.add_parser("replay", help="Verify and inspect a versioned ledger without live services")
    r.add_argument("store")
    r.add_argument("--export", help="Export the exact trace (may contain full copyrighted/private evidence)")
    r = commands.add_parser("run", help="One live question; independent policy and audit contexts")
    source = r.add_mutually_exclusive_group(required=True)
    source.add_argument("--question")
    source.add_argument("--dataset", help="Question JSONL; labels are never sent to the model")
    r.add_argument("--qid")
    r.add_argument("--mode", choices=["esr", "baseline"], default="esr")
    r.add_argument("--audit-mode", choices=["hard", "soft", "off"], help="Required explicitly for ESR")
    r.add_argument("--policy-url", required=True, help="OpenAI-compatible base URL including /v1")
    r.add_argument("--model", required=True)
    r.add_argument("--model-revision", default="unspecified")
    r.add_argument("--tokenizer", required=True, help="Exact tokenizer path/name of served policy")
    r.add_argument("--tokenizer-revision")
    r.add_argument("--thinking", action=argparse.BooleanOptionalAction, default=True)
    r.add_argument("--temperature", type=float, default=0.6)
    r.add_argument("--audit-url")
    r.add_argument("--audit-model")
    r.add_argument("--audit-model-revision", default="unspecified")
    r.add_argument("--audit-tokenizer")
    r.add_argument("--audit-tokenizer-revision")
    r.add_argument("--audit-thinking", action=argparse.BooleanOptionalAction, default=False)
    r.add_argument("--retrieval-url", default="http://127.0.0.1:8000")
    r.add_argument("--retrieval-revision", default="unspecified")
    r.add_argument("--max-actions", type=int, default=64)
    r.add_argument("--max-context-tokens", type=int, default=32768)
    r.add_argument("--max-output-tokens", type=int, default=2048)
    r.add_argument("--audit-max-output-tokens", type=int, default=2048)
    r.add_argument("--max-total-completion-tokens", type=int, default=24000)
    r.add_argument("--search-top-k", type=int, default=5)
    r.add_argument("--view-chars", type=int, default=8000)
    r.add_argument("--max-pending-views", type=int, default=4)
    r.add_argument("--recent-actions", type=int, default=4)
    r.add_argument("--deterministic-retrieval", action=argparse.BooleanOptionalAction, default=True,
                   help="Declare fixed deterministic index; cache also requires --retrieval-revision")
    r.add_argument("--store", required=True, help="New SQLite episode path (2.1 schema only; old files use replay)")
    r.add_argument("--resume", action="store_true")
    r.add_argument("--output", help="Summary JSON; default is <store>.summary.json")
    return p


def live(args) -> dict:
    if args.dataset and not args.qid:
        raise ValueError("--dataset requires --qid")
    if args.mode == "esr" and args.audit_mode is None:
        raise ValueError("Select --audit-mode hard|soft|off explicitly; gate changes are experimental conditions")
    if args.mode == "baseline" and args.audit_mode not in {None, "off"}:
        raise ValueError("Baseline uses audit-mode off")
    if Path(args.store).exists() and not args.resume:
        raise ValueError("Store already exists; use --resume with identical config or a new path")
    if args.resume and not Path(args.store).exists():
        raise ValueError("Cannot resume a missing store")
    question = load_question(args.dataset, args.qid) if args.dataset else args.question
    counter = HFTokenCounter(args.tokenizer, args.tokenizer_revision)
    if args.resume:
        check = Ledger(args.store, readonly=True)
        schema = check.header.get("schema_version")
        check.close()
        if schema != 3:
            raise ValueError("Live resume requires a 2.1 ledger (schema 3); old ledgers are replay-only here")
    ledger = Ledger(args.store)
    if args.resume and not ledger.header:
        raise ValueError("Cannot resume a store without an episode header")
    budget = UsageBudget(args.max_total_completion_tokens, ledger.events())
    policy = ChatClient(ChatConfig(base_url=args.policy_url, model=args.model, model_revision=args.model_revision,
                                  max_context_tokens=args.max_context_tokens, max_output_tokens=args.max_output_tokens,
                                  temperature=args.temperature, thinking=args.thinking), counter, budget, ledger)
    audit_mode = args.audit_mode or "off"
    auditor = None
    if args.mode == "esr" and audit_mode != "off":
        if args.audit_model and args.audit_model != args.model and not args.audit_tokenizer:
            raise ValueError("A different audit model requires --audit-tokenizer")
        acounter = HFTokenCounter(args.audit_tokenizer, args.audit_tokenizer_revision) if args.audit_tokenizer else counter
        audit_client = ChatClient(ChatConfig(base_url=args.audit_url or args.policy_url, model=args.audit_model or args.model,
                                            model_revision=args.audit_model_revision if args.audit_model else args.model_revision,
                                            max_context_tokens=args.max_context_tokens, max_output_tokens=args.audit_max_output_tokens,
                                            temperature=0.0, thinking=args.audit_thinking), acounter, budget, ledger)
        auditor = ModelAuditor(audit_client)
    config = Config(mode=args.mode, audit_mode=audit_mode, max_actions=args.max_actions,
                    search_top_k=args.search_top_k, view_chars=args.view_chars,
                    recent_actions=args.recent_actions, max_pending_views=args.max_pending_views)
    retriever = EchoRetriever(args.retrieval_url)
    retriever.identity["index_revision"] = args.retrieval_revision
    retriever.deterministic = args.deterministic_retrieval
    retriever.identity["deterministic"] = args.deterministic_retrieval
    manifest = {"qid": args.qid, "policy": policy.identity, "code_revision": code_revision(),
                "policy_prompt": {"version": POLICY_PROMPT_VERSION,
                                  "system_hash": digest(policy_system(config) + "\nTools:\n" + canonical(config.tools))},
                "generation_budget": budget.limit,
                "dataset_sha256": hashlib.sha256(Path(args.dataset).read_bytes()).hexdigest() if args.dataset else None,
                "note": "Served model/index revisions are operator declarations, not remotely attested hashes."}
    harness = Harness(question, retriever, auditor, config=config, ledger=ledger, manifest=manifest)
    result = run(harness, policy)
    ledger.verify()
    output = Path(args.output) if args.output else Path(args.store).with_suffix(".summary.json")
    if output.resolve() == Path(args.store).resolve() or (args.dataset and output.resolve() == Path(args.dataset).resolve()):
        raise ValueError("Summary output cannot overwrite the dataset or ledger")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    ledger.close()
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "smoke":
            result = smoke(args.store)
        elif args.command == "replay":
            harness = replay(args.store)
            result = summary(harness, UsageBudget(harness.ledger.header["manifest"].get("generation_budget", 24000), harness.ledger.events()))
            if args.export:
                harness.ledger.export(args.export)
            harness.ledger.close()
        else:
            result = live(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result["terminal"] and result["terminal"]["outcome"] in {"service_error", "context_overflow"} else 0
    except (HarnessError, ValueError, RuntimeError, OSError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
