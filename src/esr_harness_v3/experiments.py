"""Private frozen this-ablation plans, complete ledger summaries, and exact prefixes.

The only executor in this module is an offline scripted fixture. A qualified
non-ESR baseline, provider acceptance, and independent BC+ judge remain separate.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from .adapters import MemoryRetriever, run_episode
from .audit import AUDIT_SYSTEM
from .engine import Harness
from .protocol import Config, ContractError, SYSTEM, VERSION, canonical, digest, parse_json, tools
from .store import Ledger


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def implementation_hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))}


def freeze_this_plan(output, cases, config, *, identity, repetitions=1, seed=0):
    """Freeze only this on/off; shared retrieval/submission/audit/budgets cannot vary."""
    if type(repetitions) is not int or not 1 <= repetitions <= 10 or type(seed) is not int:
        raise ValueError('Specify a bounded repetition count and integer seed')
    if not cases or any(set(c) != {'id', 'question'} or not all(isinstance(v, str) and v.strip() for v in c.values()) for c in cases):
        raise ValueError('Cases contain only id and question; keep labels outside policy inputs')
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate case ID')
    conditions = {'this_on': replace(config, enable_this=True).to_dict(),
                  'this_off': replace(config, enable_this=False).to_dict()}
    schedule = []
    for case in cases:
        for repeat in range(repetitions):
            for condition in conditions:
                schedule.append({'slot': f'{len(schedule):04d}', 'case_id': case['id'], 'repeat': repeat,
                                 'condition': condition, 'question_sha256': digest(case['question'])})
    plan = {'protocol': VERSION, 'created_utc': datetime.now(timezone.utc).isoformat(),
            'comparison': 'ESR this on/off; neither condition is a non-ESR baseline',
            'cases': deepcopy(cases), 'conditions': conditions, 'schedule': schedule,
            'seed': seed, 'order': 'case, repetition, this_on, this_off; no shuffle',
            'identity': deepcopy(identity), 'source_sha256': implementation_hashes(),
            'policy_prompt_sha256': digest(SYSTEM), 'audit_prompt_sha256': digest(AUDIT_SYSTEM),
            'schema_sha256': digest(tools()), 'max_scheduled_model_attempts': len(schedule) * config.max_model_calls,
            'judge': 'NOT_IMPLEMENTED', 'formal_accuracy': None,
            'stop_rules': ['first service/protocol failure stops queue', 'no retry or implicit resume',
                           'every planned slot remains in summary', 'no source edits after freezing']}
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    write_new(root/'plan.json', {'sha256': digest(plan), 'plan': plan})
    return plan


def load_plan(root):
    wrapper = parse_json((Path(root)/'plan.json').read_text(encoding='utf-8'))
    if digest(wrapper['plan']) != wrapper['sha256']:
        raise ContractError('plan_integrity', 'Frozen plan changed')
    return wrapper['plan']


def exact_prefix(ledger, decision_id):
    """Copy recorded messages, never reconstruct evidence or inject feedback/gold."""
    events = ledger.verify()
    request = next((e['payload'] for e in events if e['kind'] == 'policy_request' and e['payload']['decision'] == decision_id), None)
    response = next((e for e in events if e['kind'] == 'policy_response' and e['payload']['decision'] == decision_id), None)
    if request is None or response is None:
        raise ContractError('prefix_not_delivered', 'Require an original request and its recorded response')
    timing = next((e['payload'] for e in events if e['kind'] == 'policy_timing' and e['payload']['decision'] == decision_id), {})
    wire = timing.get('wire_request')
    if not isinstance(wire, dict):
        raise ContractError('prefix_wire_missing', 'Actual adapter request was not recorded; no reconstructed prefix')
    return {'decision': decision_id, 'request': deepcopy(wire), 'request_sha256': digest(wire),
            'binding': deepcopy(request['binding']), 'response_event_hash': response['hash'],
            'requested_identity': timing.get('requested_identity'), 'response_model': timing.get('response_model'),
            'additional_labels_injected': False, 'scope': 'recorded request only; no teacher continuation'}


def summarize_cohort(output):
    """Read all planned slots, including failed, interrupted and unexecuted ones."""
    root = Path(output)
    plan = load_plan(root)
    rows = []
    for slot in plan['schedule']:
        row = {**slot, 'status': 'NOT_RUN', 'formal_correct': None}
        path = root / (slot['slot'] + '.sqlite')
        if path.exists():
            ledger = Ledger(path, readonly=True)
            try:
                export = ledger.export()
                state, events = export['state'], export['events']
                header = events[0]['payload']
                if (header['config'] != plan['conditions'][slot['condition']]
                        or digest(state['question']) != slot['question_sha256']
                        or header['retriever'] != plan['identity']['retriever']):
                    raise ContractError('cohort_mismatch', 'Episode does not match its frozen condition/question/index')
                counts = Counter(e['kind'] for e in events)
                terminal = state.get('terminal') or {'outcome': 'INTERRUPTED', 'answer': ''}
                commits = [e['payload'] for e in events if e['kind'] == 'action_commit']
                seen, new_raw_rounds = set(), 0
                for event in events:
                    if event['kind'] == 'policy_request':
                        visible = set(event['payload']['binding']['visible_observations'])
                        new_raw_rounds += bool(visible - seen)
                        seen.update(visible)
                timing_path = root / (slot['slot'] + '.result.json')
                timing = parse_json(timing_path.read_text(encoding='utf-8')) if timing_path.exists() else {}
                if timing and timing['ledger_head'] != export['head']:
                    raise ContractError('cohort_mismatch', 'Timing receipt belongs to a different ledger head')
                row.update(status=terminal['outcome'], submitted_answer=terminal['answer'],
                           ledger_head=export['head'], model_attempts=state['model_calls'],
                           policy_attempts=counts['policy_request'], audit_attempts=counts['audit_request'],
                           audit_repairs=sum(e['payload']['attempt'] > 1 for e in events if e['kind'] == 'audit_request'),
                           tool_actions=state['actions'], backend_calls=state['backend_calls'], usage=state['usage'],
                           search_cache_hits=sum(bool(s['cache_source']) for s in state['searches']),
                           audit_cache_hits=sum(bool(c['result'].get('cached')) for c in commits if c['name'] == 'verify_answer'),
                           maintenance_actions=sum(c['name'] == 'update_state' for c in commits),
                           noop_updates=sum(bool(c['result'].get('changes', {}).get('noop')) for c in commits),
                           policy_rounds_receiving_new_raw=new_raw_rounds, elapsed_seconds=timing.get('elapsed_seconds'))
            finally:
                ledger.close()
        rows.append(row)
    conditions = {}
    for condition in plan['conditions']:
        group = [r for r in rows if r['condition'] == condition]
        conditions[condition] = {'planned': len(group), 'status_counts': dict(Counter(r['status'] for r in group)),
            'model_attempts': sum(r.get('model_attempts', 0) for r in group),
            'backend_calls': sum(r.get('backend_calls', 0) for r in group),
            'tool_actions': sum(r.get('tool_actions', 0) for r in group),
            'known_input_tokens': sum(r.get('usage', {}).get('input_tokens', 0) for r in group),
            'known_output_tokens': sum(r.get('usage', {}).get('output_tokens', 0) for r in group),
            'unknown_usage_calls': sum(r.get('usage', {}).get('unknown_calls', 0) for r in group),
            'formal_accuracy': None, 'correct_completion_seconds': None}
    return {'plan_sha256': digest(plan), 'rows': rows, 'conditions': conditions,
            'model_usage_kind': plan['identity']['usage_kind'], 'judge': 'NOT_IMPLEMENTED',
            'formal_accuracy': None, 'decision': 'inconclusive',
            'limitations': ['this_off is not a non-ESR baseline', 'no independent semantic judge',
                            'legal-but-wrong bindings need independent source labels; no guessed metric',
                            'elapsed time without formal correctness is not correct-completion speed']}


class FixturePolicy:
    identity = {'kind': 'fixture-scripted', 'requested_model': 'fixture'}
    def __init__(self, mode):
        self.mode, self.calls = mode, 0

    def complete(self, request):
        self.calls += 1
        self.last_request = deepcopy(request)
        if self.mode == 'service_failure':
            raise ContractError('service_error', 'Injected fixture failure; no HTTP')
        receipts = [parse_json(m['content']) for m in request['messages'] if m['role'] == 'tool']
        if self.calls == 1:
            name, args = 'search', {'query': 'Orin'}
        elif self.calls == 2:
            name, args = 'open_page', {'ref': next(r for r in receipts if 'hits' in r)['hits'][0]['ref']}
        else:
            view = next(r['observation'] for r in reversed(receipts) if 'observation' in r)
            tail = parse_json(request['messages'][-1]['content'].split('\n', 1)[1])
            ref = 'this' if tail['this'] else view['observation']
            if self.mode == 'reference_repair' and self.calls == 3:
                ref = 'o999'
            # Answer is derived from the actually delivered fixture observation.
            answer = view['text'].split('director: ', 1)[1].rstrip('.')
            name, args = 'submit_answer', {'answer': answer, 'refs': [ref]}
        return {'model': 'fixture', 'choices': [{'finish_reason': 'tool_calls', 'message': {'role': 'assistant',
                'content': None, 'tool_calls': [{'id': f'fixture_{self.calls}', 'type': 'function',
                    'function': {'name': name, 'arguments': canonical(args)}}]}}]}


def run_fixture_cohort(output):
    """Exercise queue stop and full-denominator reporting; never read credentials."""
    retriever = MemoryRetriever([{'docid': 'fixture-record', 'title': 'Orin institute',
                                  'content': 'Orin director: Mira Vale.'}])
    cases = [{'id': mode, 'question': 'Who is the Orin director?'}
             for mode in ('direct', 'reference_repair', 'service_failure', 'after_failure')]
    plan = freeze_this_plan(output, cases, Config(max_model_calls=5, require_sources=True, audit_mode='off'),
                            identity={'policy': FixturePolicy.identity, 'retriever': retriever.identity,
                                      'capacity_unit': 'utf8_bytes', 'usage_kind': 'fixture_no_provider_usage',
                                      'dataset': 'synthetic', 'new_paid_calls_authorized': 0})
    root = Path(output)
    stop = None
    for slot in plan['schedule']:
        if implementation_hashes() != plan['source_sha256']:
            stop = 'source_changed'
            break
        started = time.monotonic()
        write_new(root/(slot['slot']+'.started.json'), {'slot': slot, 'utc': datetime.now(timezone.utc).isoformat()})
        question = next(c['question'] for c in cases if c['id'] == slot['case_id'])
        h = Harness(question, retriever, ledger=root/(slot['slot']+'.sqlite'),
                    config=Config(**plan['conditions'][slot['condition']]))
        try:
            terminal = run_episode(h, FixturePolicy(slot['case_id']))
        finally:
            write_new(root/(slot['slot']+'.result.json'), {'elapsed_seconds': time.monotonic() - started,
                                                          'ledger_head': h.ledger.head})
            h.close()
        if terminal['outcome'] in ('service_error', 'retrieval_error', 'audit_service_error',
                                   'audit_protocol_error', 'response_protocol_error', 'incomplete_response'):
            stop = terminal['outcome']
            break
    result = summarize_cohort(root)
    result.update(fixture_only=True, real_model_calls=0, stopped_because=stop,
                  implementation_unchanged=implementation_hashes() == plan['source_sha256'])
    write_new(root/'summary.json', result)
    return result
