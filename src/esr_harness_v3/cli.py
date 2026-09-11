"""Offline smoke/schema/replay/export and explicitly authorized live runs."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path

from .adapters import EchoRetriever, MemoryRetriever, OpenAICompatible, hf_counter, run_episode
from .engine import Harness
from .protocol import Config, VERSION, canonical, tools
from .store import Ledger
from .training import training_export


def call(harness, name, arguments):
    decision = harness.begin()
    return harness.respond(decision, {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': 'fixture_' + decision.id, 'type': 'function',
         'function': {'name': name, 'arguments': canonical(arguments)}}]})[0]


def smoke(path=':memory:'):
    retriever = MemoryRetriever([{'docid': 'fixture-1', 'title': 'Orin leadership record',
                                 'content': 'The first director of the Orin institute was Mira Vale.'}])
    h = Harness('Who was the first director of the Orin institute?', retriever, ledger=path,
                config=Config(require_sources=True))
    try:
        search = call(h, 'search', {'query': 'Orin'})
        opened = call(h, 'open_page', {'ref': search['hits'][0]['ref']})
        submitted = call(h, 'submit_answer', {'answer': 'Mira Vale', 'refs': ['this']})
        assert submitted['ok'] and submitted['terminal']['basis']['direct_refs'] == opened['delivered_observations']
        h.ledger.verify()
        return {'fixture_only': True, 'protocol': VERSION, 'terminal': h.terminal,
                'model_decisions': h.state['model_calls'], 'backend_calls': h.state['backend_calls'],
                'real_model_calls': 0, 'benchmark_accuracy': None, 'event_count': h.ledger.seq}
    finally:
        h.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='ESR v3 reference-light harness; old v2 is unchanged')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('smoke'); p.add_argument('--db', default=':memory:')
    sub.add_parser('schema')
    p = sub.add_parser('replay'); p.add_argument('--db', required=True)
    p = sub.add_parser('export'); p.add_argument('--db', required=True); p.add_argument('--output', required=True); p.add_argument('--require-rl', action='store_true')
    p = sub.add_parser('cohort-fixture', help='Offline frozen this on/off queue; not a benchmark')
    p.add_argument('--output', required=True)
    p = sub.add_parser('cohort-summary', help='Read every registered slot, including NOT_RUN')
    p.add_argument('--run-dir', required=True); p.add_argument('--output', required=True)
    p = sub.add_parser('prefix', help='Copy the exact recorded request for one completed decision')
    p.add_argument('--db', required=True); p.add_argument('--decision', required=True); p.add_argument('--output', required=True)
    p = sub.add_parser('run')
    p.add_argument('--question-file', required=True)
    p.add_argument('--db', required=True)
    p.add_argument('--base-url', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--api-key-env', default='ESR_API_KEY')
    p.add_argument('--retrieval-url', required=True)
    p.add_argument('--index-fingerprint', required=True)
    p.add_argument('--tokenizer', required=True)
    p.add_argument('--allow-network', action='store_true')
    p.add_argument('--audit-mode', choices=['diagnostic', 'hard', 'off'], default='diagnostic')
    p.add_argument('--require-sources', action='store_true')
    p.add_argument('--disable-this', action='store_true')
    p.add_argument('--max-model-calls', type=int, required=True, help='Explicit total policy + audit request cap')
    p.add_argument('--max-actions', type=int, default=100)
    p.add_argument('--context-limit', type=int, default=32000)
    p.add_argument('--output-reserve', type=int, default=2048)
    p.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args(argv)
    if args.command == 'smoke':
        result = smoke(args.db)
    elif args.command == 'schema':
        result = {'protocol': VERSION, 'tools': tools()}
    elif args.command in ('replay', 'export'):
        ledger = Ledger(args.db, readonly=True)
        try:
            if args.command == 'replay':
                export = ledger.export()
                result = {'verified_events': export['event_count'], 'head': export['head'], 'terminal': export['state']['terminal']}
            else:
                result = training_export(ledger, require_rl=args.require_rl)
                out = Path(args.output)
                out.parent.mkdir(parents=True, exist_ok=True)
                with out.open('x', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                result = {'output': str(out), 'rl_ready': result['rl_ready'], 'records': len(result['records'])}
        finally:
            ledger.close()
    elif args.command in ('cohort-fixture', 'cohort-summary', 'prefix'):
        from .experiments import exact_prefix, run_fixture_cohort, summarize_cohort, write_new
        if args.command == 'cohort-fixture':
            summary = run_fixture_cohort(args.output)
            result = {k: summary[k] for k in ('fixture_only', 'real_model_calls', 'stopped_because', 'conditions')}
        elif args.command == 'cohort-summary':
            result = summarize_cohort(args.run_dir)
            write_new(args.output, result)
            result = {'output': args.output, 'scheduled': len(result['rows']), 'formal_accuracy': None}
        else:
            ledger = Ledger(args.db, readonly=True)
            try:
                result = exact_prefix(ledger, args.decision)
                write_new(args.output, result)
                result = {'output': args.output, 'request_sha256': result['request_sha256']}
            finally:
                ledger.close()
    else:
        if not args.allow_network:
            parser.error('Live calls require --allow-network and an explicit request cap; smoke never uses credentials')
        question = Path(args.question_file).read_text(encoding='utf-8')
        count, unit = hf_counter(args.tokenizer)
        cfg = Config(max_model_calls=args.max_model_calls, max_actions=args.max_actions,
                     context_limit=args.context_limit, output_reserve=args.output_reserve,
                     audit_mode=args.audit_mode, require_sources=args.require_sources, enable_this=not args.disable_this)
        client = OpenAICompatible(args.base_url, args.model, api_key=os.environ.get(args.api_key_env), timeout=args.timeout)
        retriever = EchoRetriever(args.retrieval_url, index_fingerprint=args.index_fingerprint, timeout=args.timeout)
        h = Harness(question, retriever, ledger=args.db, config=cfg, auditor=client if cfg.audit_mode != 'off' else None,
                    counter=count, counter_name=unit)
        try:
            result = run_episode(h, client)
        finally:
            h.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
