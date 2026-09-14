"""Prepare one external judge per submitted answer, only after the cohort ends."""
import argparse
import hashlib
import json
from pathlib import Path

from stride_search.archive import Archive
from trace_question_a3 import save, sha, utc


def prepare(cohort_path, gold_path, output):
    cohort = json.loads(Path(cohort_path).read_text(encoding='utf-8'))
    status = Path(cohort['status_dir'])
    completed = json.loads((status / 'completed.json').read_text(encoding='utf-8'))
    if [r['qid'] for r in completed['finished']] != cohort['qids'] or (status / 'stopped.json').exists():
        raise ValueError('All preregistered episodes must have ended normally before gold access')
    cases = []
    for entry in cohort['plans']:
        plan = json.loads(Path(entry['path']).read_text(encoding='utf-8'))
        root = Path(plan['output'])
        inventory = json.loads((root / 'MANIFEST.sha256.json').read_text(encoding='utf-8'))
        for name, expected in inventory.items():
            if sha(root / name) != expected:
                raise ValueError('Sealed source changed')
        a = Archive(root / 'episode.sqlite', readonly=True)
        try:
            report = a.report()
            cases.append({'qid': plan['qid'], 'slot': plan['slot'], 'head': a.verify()['head'],
                          'source_run': str(root), 'source_manifest_sha256': sha(root / 'MANIFEST.sha256.json'),
                          'question': report['header']['question'], 'terminal': report['terminal']['outcome'],
                          'response': report['terminal'].get('answer')})
        finally:
            a.close()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = utc(); digest = hashlib.sha256(); wanted = {c['qid'] for c in cases}; gold = {}
    with Path(gold_path).open('rb') as stream:
        for line_number, line in enumerate(stream, 1):
            digest.update(line)
            row = json.loads(line)
            qid = str(row['query_id'])
            if qid in wanted:
                if qid in gold:
                    raise ValueError('Duplicated gold query id')
                gold[qid] = {'question': row['query'], 'answer': row['answer'],
                             'line_number': line_number, 'line_sha256': hashlib.sha256(line).hexdigest()}
    if set(gold) != wanted:
        raise ValueError('Gold query ids missing')
    if digest.hexdigest() != 'f1958aa81bbaca21cb14a58ba009f53c070fa047f0107414226dbec76a242807':
        raise ValueError('Gold dataset hash differs from frozen source identity')
    for c in cases:
        if c['question'] != gold[c['qid']]['question']:
            raise ValueError('Gold question differs from original policy question')
        c['correct_answer'] = gold[c['qid']]['answer']
    submitted = [c for c in cases if c['terminal'] == 'submitted']
    save(output / 'all-cases.json', cases)
    save(output / 'cases.json', submitted)
    save(output / 'gold-access.json', {'started': started, 'finished': utc(), 'source_path': str(gold_path),
         'source_sha256': digest.hexdigest(), 'source_bytes': Path(gold_path).stat().st_size,
         'after_cohort_completed': completed['utc'], 'selected_rows': gold,
         'not_submitted_scoring': 'No paid semantic judge without a formal answer; score false, judge_correct null, outcome preserved'})
    script_dir = Path(__file__).resolve().parent
    runner = script_dir / 'judge_frozen_a3.py'; capture = script_dir / 'trace_question_a3.py'
    source = script_dir.parents[2] / 'src/esr_grpo/judge.py'
    first = json.loads(Path(cohort['plans'][0]['path']).read_text(encoding='utf-8'))
    save(output / 'plan.json', {'runner_sha256': sha(runner), 'judge_source': str(source),
         'judge_source_sha256': sha(source), 'capture_source': str(capture), 'capture_source_sha256': sha(capture),
         'cases_path': str(output / 'cases.json'), 'cases_sha256': sha(output / 'cases.json'),
         'base_url': first['base_url'], 'budget_path': first['budget_path'],
         'output': str(output / 'results'), 'policy_rollouts_completed_utc': completed['utc'],
         'one_attempt_per_submitted_answer': True, 'automatic_retries': 0})
    print(json.dumps({'plan': str(output / 'plan.json'), 'submitted': len(submitted), 'total': len(cases)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort', required=True); p.add_argument('--gold', required=True); p.add_argument('--output', required=True)
    args = p.parse_args(); prepare(args.cohort, args.gold, args.output)
