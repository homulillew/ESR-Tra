"""External post-run semantic judge: one attempt per immutable submitted answer."""
import argparse
from dataclasses import asdict
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch

from stride_search.archive import Archive
from trace_question_a3 import Budget, CaptureOpener, save, sha, utc


class JudgeBudget(Budget):
    def take(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            s = self.snapshot()
            if s['remaining'] <= 0 or s['this_run'] >= self.limit:
                raise ValueError('BLOCKED_BUDGET')
            n = self.db.execute('INSERT INTO requests(run,role,status) VALUES (?,?,?)',
                                (self.run, 'judge', 'unknown')).lastrowid
            self.db.execute('COMMIT')
            return n
        except Exception:
            self.db.execute('ROLLBACK')
            raise


def validate_response(raw, parsed):
    if raw.get('model') != 'glm-5.2':
        raise ValueError('judge_model_identity_changed')
    choices = raw.get('choices', [])
    if len(choices) != 1 or choices[0].get('finish_reason') != 'stop':
        raise ValueError('judge_incomplete_response')
    if not isinstance(parsed, dict) or type(parsed.get('correct')) is not bool:
        raise ValueError('judge_invalid_correct_type')
    if not all(isinstance(parsed.get(k), str) and parsed[k].strip() for k in ['extracted_answer', 'rationale']):
        raise ValueError('judge_invalid_schema')


def run(plan_path):
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    if sha(__file__) != plan['runner_sha256'] or sha(plan['judge_source']) != plan['judge_source_sha256']:
        raise ValueError('Frozen judge source changed')
    if sha(plan['capture_source']) != plan['capture_source_sha256']:
        raise ValueError('Frozen capture changed')
    cases = json.loads(Path(plan['cases_path']).read_text(encoding='utf-8'))
    if sha(plan['cases_path']) != plan['cases_sha256'] or len({c['qid'] for c in cases}) != len(cases):
        raise ValueError('Frozen cases changed or duplicated')
    for c in cases:
        source = Path(c['source_run'])
        if sha(source / 'MANIFEST.sha256.json') != c['source_manifest_sha256']:
            raise ValueError('Sealed source identity changed')
        a = Archive(source / 'episode.sqlite', readonly=True)
        try:
            report = a.report()
            if a.verify()['head'] != c['head'] or report['terminal']['outcome'] != 'submitted':
                raise ValueError('Wrong submitted ledger head')
            if report['terminal']['answer'] != c['response'] or report['header']['question'] != c['question']:
                raise ValueError('Original submission changed')
        finally:
            a.close()
    key = os.environ.get('ESR_API_KEY')
    if not key or os.environ.get('ESR_BASE_URL') != plan['base_url']:
        raise ValueError('Missing configured environment')
    root = Path(plan['output'])
    if root.exists():
        raise FileExistsError(root)
    budget = JudgeBudget(plan['budget_path'], str(root), len(cases))
    root.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location('frozen_project_judge', plan['judge_source'])
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    capture = CaptureOpener(root, budget, key, plan['base_url'].rstrip('/') + '/chat/completions')
    judge = module.OpenAICompatibleJudge(plan['base_url'], 'EB-GLM-5.2', api_key_env='ESR_API_KEY',
                                         timeout_seconds=180, max_tokens=2048)
    save(root / 'manifest.json', {**plan, 'utc_started': utc(), 'budget_before': budget.before,
         'scope': 'Original finish.answer only; no refs, model commentary, audit, or old trajectories supplied',
         'model_relationship': 'Separate post-run calls to the same configured model family; not independent model deployment'})
    results = []
    try:
        for i, c in enumerate(cases, 1):
            save(root / f'{i:03d}.input.json', c)
            with patch.object(module.urllib.request, 'urlopen', capture.open):
                result = judge.judge(c['question'], c['response'], c['correct_answer'])
            raw = json.loads((root / 'http' / f'{i:03d}' / 'response.body').read_bytes())
            parsed = module._parse_json_object(raw['choices'][0]['message']['content'])
            validate_response(raw, parsed)
            if result.parse_error or result.correct != parsed['correct']:
                raise ValueError('judge_parse_error')
            row = {'qid': c['qid'], 'slot': c['slot'], 'head': c['head'], 'correct': result.correct,
                   'project_judge_result': asdict(result), 'exact_string_match': c['response'] == c['correct_answer'],
                   'http_sequence': i, 'source_run': c['source_run'], 'utc': utc()}
            results.append(row)
            save(root / f'{i:03d}.judgment.json', row)
    except Exception as exc:
        save(root / 'stopped.json', {'type': type(exc).__name__, 'completed_qids': [r['qid'] for r in results],
                                    'attempts': len(capture.rows), 'utc': utc(), 'automatic_retries': 0})
        raise
    finally:
        save(root / 'budget-after.json', budget.snapshot())
        budget.close()
    save(root / 'judgments.json', results)
    save(root / 'external-labels.json', [{'slot': r['slot'], 'head': r['head'], 'correct': r['correct']} for r in results])
    print(json.dumps({'output': str(root), 'judged': len(results), 'correct': sum(r['correct'] for r in results)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    run(parser.parse_args().plan)
