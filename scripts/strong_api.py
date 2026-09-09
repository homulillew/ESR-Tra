"""Bounded research entry point. Agent decisions remain exclusively in esr_harness."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
import yaml
from api.lanz_client import LanzClient
from esr_harness.audit import ModelAuditor
from esr_harness.client import UsageBudget
from esr_harness.engine import Harness
from esr_harness.ledger import Ledger
from esr_harness.local_retrieval import SQLiteRetriever
from esr_harness.protocol import Config, canonical, digest
from esr_harness.remote import AnthropicClient, GlobalBudget, RemoteConfig
from esr_harness.runner import run
from esr_harness.views import MemoryRetriever


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def append(path, value):
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(canonical(value) + "\n")
        f.flush()
        os.fsync(f.fileno())


def snapshot():
    def git(*a): return subprocess.check_output(["git",*a],cwd=ROOT,text=True,encoding="utf-8").strip()
    sources={str(p.relative_to(ROOT)).replace("\\","/"):digest(p.read_text(encoding="utf-8"))
             for folder in ("src/esr_harness", "api", "scripts") for p in (ROOT/folder).rglob("*.py")}
    return {"sha":git("rev-parse","HEAD"),"branch":git("branch","--show-current"), "source_hashes": sources,
            "dirty_status":git("status","--short"),"dirty_diff":git("diff","--no-ext-diff"),
            "python":sys.version,"timestamp_utc":datetime.now(timezone.utc).isoformat()}


def export(ledger, directory):
    names={"generation_request":"provider_requests.jsonl","generation":"provider_responses.jsonl"}
    for event in ledger.events():
        append(directory/"trajectory.jsonl", event)
        if event["type"] in names: append(directory/names[event["type"]],event)


def systemic_failure(result, directory):
    """Pause repeated execution breakdowns, not every recovered error on a long task."""
    terminal=(result.get("terminal") or {}).get("outcome")
    if terminal in {None,"service_error"}: return "infrastructure_or_unfinished"
    events=[json.loads(x) for x in (directory/"trajectory.jsonl").read_text(encoding="utf-8").splitlines()]
    actions=[e for e in events if e["type"]=="tool"]
    errors=[e for e in actions if not e["result"]["ok"]]
    signatures=Counter((e["action"],e["result"].get("error_code"),digest(e["arguments"])) for e in errors)
    if signatures and max(signatures.values())>=3: return "same_failed_proposal_three_times"
    if sum(e["action"]=="verify_answer" and e["result"].get("error_code")=="audit_protocol_error" for e in errors)>=2:
        return "repeated_audit_protocol_failure"
    if len(errors)>=4 and len(errors)*2>=len(actions):return "majority_invalid_actions"
    for i in range(len(actions)-2):
        if all(not e["result"]["ok"] for e in actions[i:i+3]):return "three_consecutive_errors"
    return None


def episode(root, budget, transport, settings, *, question, qid, arm, category, index=None, replicate=0):
    from strong_api_freeze_guard import check_episode_input, check_final_freeze
    check_episode_input(root,category,qid,question,arm)
    if category=='confirmation':
        frozen=check_final_freeze(root,snapshot(),settings)
        if arm not in frozen['confirmation_plan']['arms']:
            raise ValueError('Arm differs from final confirmation plan')
    rid=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+f"_{category}_{arm}_{qid}_{replicate}"
    directory=root/rid
    directory.mkdir()
    budget.episode(rid,category)
    append(root/"experiment_registry.jsonl",{"run_id":rid,"status":"started","category":category,"qid":qid,"arm":arm,"replicate":replicate})
    p=settings["provider"]
    config=Config(mode="baseline" if arm=="B" else "esr",audit_mode="off" if arm in {"B","E-off"} else "soft",
                  max_actions=min(12,settings["max_actions_per_episode"]) if category=="fixture" else settings["max_actions_per_episode"])
    rc=RemoteConfig(model=transport.model,max_output_tokens=p["max_output_tokens"],temperature=p["temperature"],
                    context_operating_cap=p["context_operating_cap"],timeout=p["transport_timeout_seconds"],
                    transport_attempts=settings["max_transport_attempts_per_request"],
                    recovery_headroom=p["context_recovery_headroom"])
    ledger=Ledger(directory/"ledger.sqlite")
    usage=UsageBudget(settings["max_completion_tokens_per_episode_including_audit"])
    started=time.monotonic()
    client=AnthropicClient(transport,usage,ledger,budget,config=rc,deadline=started+settings["max_wall_seconds_per_episode"])
    if category=="fixture":
        retriever=MemoryRetriever([{"docid":"fixture-1","title":"Orin Observatory opening record",
                                   "content":"The fictional Orin Observatory opened in 2041. Its first director was Sela Venn."}])
    else:
        retriever=SQLiteRetriever(index,log=ledger.append)
    auditor=ModelAuditor(client) if config.audit_mode!="off" else None
    manifest={**snapshot(),"run_id":rid,"category":category,"qid":qid,"arm":arm,"replicate":replicate,
              "settings":settings,"input_hash":digest({"qid":qid,"question":question}),"provider":client.identity,
              "shared_cache_warmth":"OS page cache uncontrolled; adjacent interleaved arms; no cross-episode application cache"}
    write_json(directory/"manifest.json",manifest)
    harness=Harness(question,retriever,auditor,config=config,ledger=ledger,manifest=manifest)
    error=None
    try:
        with (directory/'stdout.log').open('x',encoding='utf-8') as stdout, (directory/'stderr.log').open('x',encoding='utf-8') as stderr:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result=run(harness,client)
    except Exception as exc:
        error={"type":type(exc).__name__,"traceback":traceback.format_exc()}
        # Source contains no credential literal; do not stringify the transport or its headers.
        error["traceback"]=error["traceback"].replace(transport.token,"[REDACTED]")
        write_json(directory/"failure.json",error)
        with (directory/'stderr.log').open('a',encoding='utf-8') as stderr:
            print(error['traceback'],file=stderr)
        from esr_harness.runner import summary
        result=summary(harness,usage)
        result["execution_error"]=error["type"]
    result["elapsed_seconds"]=time.monotonic()-started
    result["run_id"]=rid
    export(ledger,directory)
    write_json(directory/"summary.json",result)
    write_json(directory/"exit.json",{"exit_code":1 if error else 0,"terminal":harness.terminal,
                                      "status":"unfinished" if harness.terminal is None else "finished"})
    ledger.close()
    with budget.db:
        budget.db.execute("UPDATE episodes SET status=? WHERE id=?",("unfinished" if harness.terminal is None else "finished",rid))
    append(root/"experiment_registry.jsonl",{"run_id":rid,"status":"unfinished" if harness.terminal is None else "finished", "elapsed_seconds":result["elapsed_seconds"]})
    console_record=json.dumps({"run_id":rid,"terminal":(harness.terminal or {}).get("outcome"),"attempts":harness.attempts,
                               "invalid_actions":result["invalid_actions"],"usage":usage.summary()},ensure_ascii=False)
    with (directory/'stdout.log').open('a',encoding='utf-8') as stdout:print(console_record,file=stdout)
    print(console_record,flush=True)
    return result,directory


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("stage",choices=["probe","fixture","run"])
    parser.add_argument("--root",default=str(ROOT/"runs/strong_api_esr/CURRENT"))
    parser.add_argument("--config",default=str(ROOT/"configs/strong_api_forward.yaml"))
    parser.add_argument("--key-stdin",action="store_true",help="Read credential from a private pipe, never command-line text")
    parser.add_argument("--native",action="store_true",help="Probe the actual native tool schema mapping")
    parser.add_argument("--questions",help="Questions-only JSONL; label-bearing input rejected")
    parser.add_argument("--qid")
    parser.add_argument("--arms",nargs="+",choices=["B","E-off","E-soft"],default=["B","E-off","E-soft"])
    parser.add_argument("--category",choices=["known-regression","pilot","development","confirmation"],default="known-regression")
    parser.add_argument("--index",default="D:/AgentSearchAssets/BrowseComp-Plus/indexes/esr-sqlite-bm25-20260909.sqlite")
    args=parser.parse_args()
    settings=yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    root=Path(args.root)
    if root.is_file(): root=Path(root.read_text(encoding="utf-8").strip())
    root.mkdir(parents=True,exist_ok=True)
    key=os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not key:
        print("Awaiting credential from private stdin" if args.key_stdin else "Credential required",flush=True)
        key=sys.stdin.readline().strip() if args.key_stdin else getpass.getpass("ANTHROPIC_AUTH_TOKEN: ")
    if not key: raise ValueError("Missing ANTHROPIC_AUTH_TOKEN")
    p=settings["provider"]
    transport=LanzClient(base_url=os.environ.get("ANTHROPIC_BASE_URL",p["base_url"]),token=key,model=p["model"])
    budget=GlobalBudget(root/"global_budget.sqlite",input_limit=settings["max_input_tokens_all_remote_calls"],
                        output_limit=settings["max_completion_tokens_all_remote_calls"],episode_limit=settings["max_real_episodes_total"],
                        probe_limit=settings["max_auxiliary_connectivity_requests"])
    if args.stage=="probe":
        path=root/("probe_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")); path.mkdir()
        ledger=Ledger(path/"ledger.sqlite"); ledger.initialize({"kind":"connectivity_probe",**snapshot()})
        client=AnthropicClient(transport,UsageBudget(4096),ledger,budget,config=RemoteConfig(max_output_tokens=512,temperature=p["temperature"]))
        try:
            if args.native:
                from esr_harness.prompts import policy_system
                cfg=Config(mode="baseline",audit_mode="off")
                messages=[{"role":"system","content":policy_system(cfg)+"\nTools:\n"+canonical(cfg.tools)},
                          {"role":"user","content":"This is a synthetic connectivity fixture. Use finish with answer API_OK."}]
            else:
                messages=[{"role":"system","content":"Return exactly one JSON object and no other text."},
                          {"role":"user","content":'Return {"status":"API_OK"}.'}]
            text=client.complete(messages,purpose="probe")
            write_json(path/"result.json",{"text":text,"usage":client.budget.summary()})
            print(text,flush=True)
        finally:
            export(ledger,path); ledger.close()
    elif args.stage=="fixture":
        episode(root,budget,transport,settings,question="Who was the first director of the fictional Orin Observatory that opened in 2041?",qid="synthetic-orin",arm="E-soft",category="fixture")
    else:
        if not args.questions or not args.qid: parser.error("run requires --questions and --qid")
        rows=[json.loads(x) for x in Path(args.questions).read_text(encoding="utf-8").splitlines() if x.strip()]
        if any(set(r)!={"qid","question"} for r in rows): raise ValueError("Rollout input must contain only qid and question")
        matches=[r for r in rows if r["qid"]==args.qid]
        if len(matches)!=1: raise ValueError("Expected exactly one question")
        if args.category=="confirmation" and not (root/"FINAL_FREEZE.json").exists(): raise ValueError("Confirmation requires final freeze")
        for arm in args.arms:
            result,path=episode(root,budget,transport,settings,question=matches[0]["question"],qid=args.qid,arm=arm,category=args.category,index=args.index)
            pause=systemic_failure(result,path)
            if pause:
                print("Batch paused: "+pause,flush=True)
                break
    print(json.dumps(budget.summary()),flush=True)


if __name__=="__main__": main()
