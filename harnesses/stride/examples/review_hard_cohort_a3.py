"""Offline audit and review views of finished cases; never invokes a provider."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import time

from stride_search.archive import Archive
from analyze_q26_a3 import analyze
from audit_trace_supplement_a3 import audit
from trace_question_a3 import save


def review(root):
    root = Path(root)
    with contextlib.redirect_stdout(io.StringIO()):
        analyze(root)
        audit(root)
    data = json.loads((root / 'analysis-data.json').read_text(encoding='utf-8'))
    post = json.loads((root / 'POSTHOC_CHECKS.json').read_text(encoding='utf-8'))
    rounds = json.loads((root / 'ROUND_REVIEW_INPUT.json').read_text(encoding='utf-8'))
    archive = Archive(root / 'episode.sqlite', readonly=True)
    try:
        digest = []
        for row in rounds:
            r = row['round']; actions = []
            for action in row['actions']:
                args = json.loads(action['arguments'])
                result = action['result']
                summary = {k: v for k, v in result.items() if k not in ('results', 'text', 'matches')}
                if 'matches' in result:
                    summary['matches'] = result['matches']
                selection = []
                if action['tool'] in ('read', 'find'):
                    ref = args.get('ref')
                    if isinstance(ref, str) and ref.startswith('e'):
                        try:
                            ref = archive.evidence(ref)['document']
                        except (KeyError, ValueError):
                            pass
                    for q in data['queries']:
                        if q['round'] >= r:
                            continue
                        for dref, hit in zip(q['returned_dN'], q['result_docs']):
                            if ref == dref:
                                selection.append({'ref': ref, 'round': q['round'], 'query': q['query'],
                                                  'title': hit.get('title'), 'snippet': hit.get('snippet')})
                actions.append({'tool': action['tool'], 'arguments': args, 'executed': action['executed'],
                                'result': summary, 'prior_search_selections': selection[-3:]})
            digest.append({'round': r, 'content': row['message'].get('content'),
                           'actions': actions, 'visible': row['context']['visible'],
                           'shelf': row['context']['shelf_restored'],
                           'compacted': row['context']['compacted'],
                           'queries': [q for q in post['queries'] if q['round'] == r]})
        save(root / 'REVIEW_DIGEST.json', {'metrics': post['metrics'], 'rounds': digest,
             'question': archive.report()['header']['question'], 'evidence': data['evidence']})
        lines = ['# 逐轮轨迹核对', '',
                 '本文件从已结束的归档生成。模型原话仅表示当轮判断；人工结论见 INTERACTION_ANALYSIS.md。完整实际输入、工具结果及原文见 FULL_INTERACTION.md 和 HTTP 正文。', '']
        for row in digest:
            r = row['round']
            lines += [f'## 第 {r} 轮', '',
                      f"压缩：{row['compacted']}；实际可见原文：{row['visible']}；shelf 恢复：{row['shelf']}。", '',
                      '模型当轮原话：', '', '```text', row['content'] or '(无正文)', '```', '']
            for action in row['actions']:
                lines += ['```json', json.dumps(action, ensure_ascii=False, indent=2), '```', '']
            if row['queries']:
                lines += ['查询执行与此前结果集合的比较：', '', '```json',
                          json.dumps(row['queries'], ensure_ascii=False, indent=2), '```', '']
        (root / 'ROUND_ANALYSIS.md').write_text('\n'.join(lines), encoding='utf-8')
    finally:
        archive.close()


def watch(cohort_path):
    cohort = json.loads(Path(cohort_path).read_text(encoding='utf-8'))
    status = Path(cohort['status_dir'])
    done = set()
    while True:
        for path in sorted(status.glob('*.finished.json')):
            row = json.loads(path.read_text(encoding='utf-8'))
            if row['qid'] in done:
                continue
            review(row['output'])
            done.add(row['qid'])
            print(json.dumps({'offline_reviewed': row['qid'], 'count': len(done)}), flush=True)
        if (status / 'completed.json').exists() or (status / 'stopped.json').exists():
            return
        time.sleep(5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', required=True)
    watch(parser.parse_args().cohort)
