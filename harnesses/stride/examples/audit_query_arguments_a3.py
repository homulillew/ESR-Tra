"""Correct offline query declaration counts without altering archived actions."""
import argparse
import json
from pathlib import Path
from trace_question_a3 import save


def audit(root):
    root = Path(root)
    if (root / 'MANIFEST.sha256.json').exists():
        raise ValueError('Never modify an already sealed case')
    rows = []; declared = 0; invalid_shape = 0
    for path in sorted(root.glob('http/*/response.body')):
        response = json.loads(path.read_bytes())
        for call in response['choices'][0]['message'].get('tool_calls', []):
            if call['function']['name'] != 'search':
                continue
            args = json.loads(call['function']['arguments']); queries = args.get('queries')
            valid_shape = isinstance(queries, list) and all(isinstance(q, str) for q in queries)
            count = len(queries) if valid_shape else None
            declared += count or 0; invalid_shape += not valid_shape
            rows.append({'round': int(path.parent.name), 'tool_call_id': call['id'],
                         'queries_type': type(queries).__name__, 'declared_array_items': count,
                         'valid_shape': valid_shape})
    corrections = []
    for name in ('POSTHOC_CHECKS.json', 'REVIEW_DIGEST.json'):
        path = root / name; raw = path.read_bytes(); data = json.loads(raw)
        previous = data['metrics']['declared_search_queries']
        if previous != declared:
            backup = root / (path.stem + '.before-query-count-correction.json')
            with backup.open('xb') as stream:
                stream.write(raw)
            data['metrics']['declared_search_queries'] = declared
            data['metrics']['invalid_search_queries_shape_calls'] = invalid_shape
            data['metrics']['query_count_correction'] = 'String-valued queries is one invalid argument, not one query per character; original report preserved'
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            corrections.append({'file': name, 'before': previous, 'after': declared, 'preserved_original': backup.name})
    save(root / 'QUERY_ARGUMENTS_AUDIT.json', {'declared_array_query_items': declared,
         'invalid_shape_calls': invalid_shape, 'calls': rows, 'corrections': corrections,
         'original_http_archive_and_executed_queries_unchanged': True, 'production_calls': 0})
    print(json.dumps({'declared_query_items': declared, 'invalid_shape_calls': invalid_shape, 'corrections': corrections}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('root'); audit(p.parse_args().root)
