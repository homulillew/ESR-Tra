"""Offline defaults; live calls require explicit authorization and frozen identities."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import sys

from .archive import Archive
from .contract import INTEGER_ANSWER, ANSWER_CONTRACTS, Config, ContractError, canonical, loads
from .cpu_index import SQLiteFTS5
from .diagnostics import diagnose
from .engine import Harness
from .experiment import make_plan, read_cases, run_plan, summarize, write_new
from .fixtures import smoke_corpus, smoke_model
from .providers import AnthropicModel, ByteCounter, EchoRetriever, HFCounter, HTTP, OpenAIModel
from .workflow_contract import WorkflowConfig, toolset


def _json(path): return loads(Path(path).read_text(encoding="utf-8"))

def _counter(args):
    if args.counter == "hf_tokens":
        if not args.tokenizer or args.model_api != "openai": raise ValueError("HF estimate requires a local tokenizer and OpenAI-compatible messages")
        return HFCounter(args.tokenizer)
    return ByteCounter()

def _model(args, http):
    cls = AnthropicModel if args.model_api == "anthropic" else OpenAIModel
    return cls(args.base_url, args.model, revision=args.model_revision, http=http,
               api_key=os.environ.get(args.api_key_env), expected_response_model=args.expected_response_model,
               output_parameter=args.output_parameter, temperature=args.temperature)

def _retriever(args, http):
    if args.sqlite_index: return SQLiteFTS5(args.sqlite_index, index_id=args.index_id, timeout_seconds=args.timeout)
    return EchoRetriever(args.retrieval_url, index_id=args.index_id, http=http)

def _live_arguments(p):
    p.add_argument("--allow-network", action="store_true"); p.add_argument("--accept-counter-estimate", action="store_true")
    p.add_argument("--base-url", required=True); p.add_argument("--model", required=True); p.add_argument("--model-revision", required=True)
    p.add_argument("--expected-response-model"); p.add_argument("--model-api", choices=["openai", "anthropic"], default="openai")
    p.add_argument("--output-parameter", choices=["max_tokens", "max_completion_tokens"], default="max_tokens")
    p.add_argument("--api-key-env", default="STRIDE_API_KEY")
    source=p.add_mutually_exclusive_group(required=True); source.add_argument("--retrieval-url"); source.add_argument("--sqlite-index")
    p.add_argument("--index-id", required=True); p.add_argument("--counter", required=True, choices=["utf8_bytes", "hf_tokens"]); p.add_argument("--tokenizer")
    p.add_argument("--timeout", type=int, default=45); p.add_argument("--temperature", type=float, default=0.2)

def _workflow_arguments(p):
    p.add_argument("--workflow-profile", choices=["legacy", "interface", "full"], default="full")
    p.add_argument("--guided-read", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--gap-state", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--reuse-results", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--repetition", choices=["off", "observe", "bounded"])
    p.add_argument("--repeat-threshold", type=int, default=2); p.add_argument("--recovery-rounds", type=int, default=2)

def _workflow(args):
    changes={k:getattr(args,k) for k in ("guided_read","gap_state","reuse_results","repetition") if getattr(args,k) is not None}
    return replace(WorkflowConfig.profile(args.workflow_profile), **changes, repeat_threshold=args.repeat_threshold, recovery_rounds=args.recovery_rounds)

def parser():
    p=argparse.ArgumentParser(prog="stride-search",description=__doc__); commands=p.add_subparsers(dest="command",required=True)
    sp=commands.add_parser("schema"); sp.add_argument("--final",action="store_true"); sp.add_argument("--answer-contract",choices=ANSWER_CONTRACTS,default=INTEGER_ANSWER); _workflow_arguments(sp)
    commands.add_parser("smoke").add_argument("--output",required=True); commands.add_parser("replay").add_argument("--db",required=True)
    dp=commands.add_parser("diagnose"); dp.add_argument("--db",required=True); dp.add_argument("--include-text",action="store_true")
    r=commands.add_parser("run"); _live_arguments(r); _workflow_arguments(r)
    r.add_argument("--question-file",required=True); r.add_argument("--db",required=True); r.add_argument("--max-model-calls",required=True,type=int)
    r.add_argument("--context-limit",required=True,type=int); r.add_argument("--response-reserve",required=True,type=int)
    r.add_argument("--max-backend-calls",type=int,default=60); r.add_argument("--max-actions",type=int,default=80); r.add_argument("--max-output-tokens",type=int,default=2048)
    r.add_argument("--max-total-output-tokens",type=int,default=24000); r.add_argument("--max-seconds",type=int,default=900)
    r.add_argument("--no-notes",action="store_true"); r.add_argument("--no-final-reserve",action="store_true"); r.add_argument("--strict-note-failure",action="store_true")
    r.add_argument("--no-repair-context",action="store_true"); r.add_argument("--no-delivery-preflight",action="store_true"); r.add_argument("--hide-retriever-capabilities",action="store_true")
    r.add_argument("--compiled-query-cache",action="store_true"); r.add_argument("--evidence-shelf-size",type=int,default=3); r.add_argument("--no-recall-navigation",action="store_true")
    r.add_argument("--prefix-recall-excerpts",action="store_true"); r.add_argument("--max-batch",type=int,default=4); r.add_argument("--max-queries-per-search",type=int,default=3)
    r.add_argument("--context-mode",choices=["full","rolling"],default="rolling"); r.add_argument("--answer-prefix",default=""); r.add_argument("--answer-suffix",default="")
    r.add_argument("--answer-contract",choices=ANSWER_CONTRACTS,default=INTEGER_ANSWER)
    fp=commands.add_parser("plan")
    for flag in ("questions","config","arms","identities","output"): fp.add_argument("--"+flag,required=True)
    fp.add_argument("--seed",type=int,default=0); fp.add_argument("--repeats",type=int,default=1)
    cp=commands.add_parser("cohort"); _live_arguments(cp); cp.add_argument("--plan",required=True); cp.add_argument("--output",required=True); cp.add_argument("--max-total-model-calls",type=int,required=True)
    commands.add_parser("cohort-fixture").add_argument("--output",required=True)
    sr=commands.add_parser("summary"); sr.add_argument("--output",required=True); sr.add_argument("--judgments")
    return p

def execute(args):
    if args.command=="schema": return toolset(_workflow(args),notes_enabled=True,final=args.final,query_limit=3,answer_contract=args.answer_contract)
    if args.command=="diagnose": return diagnose(args.db,include_text=args.include_text)
    if args.command=="replay":
        a=Archive(args.db,readonly=True)
        try:return a.report()
        finally:a.close()
    if args.command=="smoke":
        root=Path(args.output); root.mkdir(parents=True,exist_ok=False); h=Harness("Who was the first director of Lumen Observatory?",smoke_corpus(),path=root/"episode.sqlite",config=Config(max_model_calls=3))
        try:
            h.run(smoke_model()); report=h.archive.report(); report["validation_kind"]="scripted_protocol_smoke_not_BCPlus"; write_new(root/"report.json",report); return report
        finally:h.close()
    if args.command=="plan":
        identities=_json(args.identities); wrapper=make_plan(read_cases(args.questions),Config(**_json(args.config)),_json(args.arms),model_identity=identities["model"],retriever_identity=identities["retriever"],counter_identity=identities["counter"],seed=args.seed,repeats=args.repeats); write_new(args.output,wrapper); return {"plan_sha256":wrapper["sha256"],"maximum_model_attempts":wrapper["plan"]["maximum_model_attempts"]}
    if args.command=="summary":
        judgments=[loads(l) for l in Path(args.judgments).read_text(encoding="utf-8").splitlines() if l.strip()] if args.judgments else None; return summarize(args.output,judgments=judgments)
    if args.command=="cohort-fixture":
        counter,corpus,model=ByteCounter(),smoke_corpus(),smoke_model(); wrapper=make_plan([{"id":"synthetic-lumen","question":"Who was the first director of Lumen Observatory?"}],Config(max_model_calls=3),{"notes_off":{"notes_enabled":False},"notes_on":{}},model_identity=model.identity,retriever_identity=corpus.identity,counter_identity=counter.identity); result=run_plan(wrapper,args.output,smoke_model,smoke_corpus,ByteCounter,max_total_model_calls=6); result["validation_kind"]="scripted_not_BCPlus"; return result
    if not args.allow_network or not args.accept_counter_estimate: raise ValueError("Live execution requires --allow-network and --accept-counter-estimate")
    http=HTTP(allow_network=True,timeout=args.timeout); counter=_counter(args)
    if args.command=="cohort": return run_plan(_json(args.plan),args.output,lambda:_model(args,http),lambda:_retriever(args,http),lambda:counter,max_total_model_calls=args.max_total_model_calls)
    config=Config(max_model_calls=args.max_model_calls,context_limit=args.context_limit,response_reserve=args.response_reserve,max_backend_calls=args.max_backend_calls,max_actions=args.max_actions,max_output_tokens=args.max_output_tokens,max_total_output_tokens=args.max_total_output_tokens,max_seconds=args.max_seconds,notes_enabled=not args.no_notes,reserve_finish=not args.no_final_reserve,nonblocking_notes=not args.strict_note_failure,repair_context=not args.no_repair_context,delivery_preflight=not args.no_delivery_preflight,disclose_retriever=not args.hide_retriever_capabilities,compiled_query_cache=args.compiled_query_cache,evidence_shelf_size=args.evidence_shelf_size,recall_navigation=not args.no_recall_navigation,centered_recall=not args.prefix_recall_excerpts,max_batch=args.max_batch,max_queries_per_search=args.max_queries_per_search,context_mode=args.context_mode,answer_prefix=args.answer_prefix,answer_suffix=args.answer_suffix)
    model=_model(args,http); question=Path(args.question_file).read_text(encoding="utf-8"); retriever=_retriever(args,http); h=None
    try:
        h=Harness(question,retriever,path=args.db,config=config,counter=counter,answer_contract=args.answer_contract,workflow=_workflow(args)); h.run(model); return h.archive.report()
    finally:
        if h is not None:h.close()
        if callable(getattr(retriever,"close",None)):retriever.close()

def main(argv=None):
    args=parser().parse_args(argv)
    try:result=execute(args)
    except (ValueError,OSError,sqlite3.Error,ContractError) as exc:
        print(canonical({"error":getattr(exc,"code",type(exc).__name__),"detail":str(exc)[:400]}),file=sys.stderr); return 2
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.command=="run" and result["terminal"]["outcome"] not in ("submitted","abstained"): return 2
    return 0
