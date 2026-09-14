"""Validate, package and publish sealed hard-cohort artifacts locally; no network."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

from stride_search.archive import Archive
from publish_trace_bundle_a3 import build, reading_views, sha, write
from trace_question_a3 import utc


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def seal(root):
    inventory = {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*'))
                 if p.is_file() and not p.name.endswith(('-wal', '-shm'))
                 and p.name != 'MANIFEST.sha256.json'}
    target = root / 'MANIFEST.sha256.json'
    if target.exists():
        raise FileExistsError(target)
    write(target, inventory)


def publish(cohort_path, output, private_host, private_user):
    cohort_path = Path(cohort_path).resolve(); cohort_root = cohort_path.parent
    cohort = read(cohort_path); output = Path(output).resolve()
    repo = Path(__file__).resolve().parents[3]
    examples = Path(__file__).resolve().parent
    core = repo / 'harnesses/stride/src/stride_search'
    summary = read(cohort_root / 'evaluation/summary.json')
    completed = read(Path(cohort['status_dir']) / 'completed.json')
    if [r['qid'] for r in completed['finished']] != cohort['qids']:
        raise ValueError('Incomplete cohort')
    prereg = read(cohort_root / 'PRE_RUN_MANIFEST.sha256.json')
    for name, expected in prereg.items():
        if sha(cohort_root / name) != expected:
            raise ValueError('Preregistration changed: ' + name)
    sources = {}; validations = []; requests = []
    for entry in cohort['plans']:
        plan = read(entry['path']); qid = plan['qid']; root = Path(plan['output'])
        if sha(plan['collector_path']) != plan['collector_sha256']:
            raise ValueError('Collector changed')
        for name, expected in plan['source_hashes'].items():
            source = core / name
            git_bytes = subprocess.check_output(['git', 'show',
                plan['release_commit'] + ':harnesses/stride/src/stride_search/' + name], cwd=repo)
            if sha(source) != expected or source.read_bytes() != git_bytes:
                raise ValueError('Core changed: ' + name)
        a = Archive(root / 'episode.sqlite', readonly=True)
        try:
            verified = a.verify()
            if verified['head'] != read(root / 'INTEGRITY_CHECKS.json')['archive']['head']:
                raise ValueError('Archive head changed')
            if a.report()['header']['question'] != (root / 'question.txt').read_text(encoding='utf-8').rstrip('\n'):
                raise ValueError('Question changed')
        finally:
            a.close()
        checks = read(root / 'SUPPLEMENTAL_CHECKS.json')
        post = read(root / 'POSTHOC_CHECKS.json'); data = read(root / 'analysis-data.json')
        assert all(r['response_json_equivalent'] for r in checks['response_correspondence'])
        assert all(r['ids_match_in_order'] for r in checks['native_execution_order'])
        assert checks['raw_windows_match_saved_snapshot']
        assert all(all(r[k] for k in ('native_call_found', 'name_matches', 'arguments_exact', 'action_result_found')) for r in post['tool_checks'])
        assert all(r['offsets_match_original'] for r in post['find_checks'])
        assert all(r['next_input_receipt'] for r in data['actions'] if r['next_request'] is not None)
        for name in ('INTERACTION_ANALYSIS.md', 'EVIDENCE_AUDIT.md', 'ROUND_ANALYSIS.md'):
            assert (root / name).is_file()
        for metadata_path in sorted(root.glob('http/*/metadata.json')):
            metadata = read(metadata_path)
            assert sha(metadata_path.parent / 'request.body') == metadata['request_body_sha256']
            assert sha(metadata_path.parent / 'response.body') == metadata['saved_response_body_sha256']
            assert metadata['http_status'] == 200 and metadata['returned_model'] == 'glm-5.2'
            requests.append({'qid': qid, 'sequence': metadata['sequence'], 'ledger_id': metadata['ledger_id'],
                             'role': 'policy', 'request_sha256': metadata['request_body_sha256'],
                             'response_sha256': metadata['saved_response_body_sha256']})
        validations.append({'qid': qid, 'head': verified['head'], 'event_count': verified['event_count'],
                            'source_and_collector_unchanged': True, 'trace_correspondence_valid': True})
        sources['q' + qid] = root
    judge = cohort_root / 'judge/results'
    for path in sorted(judge.glob('http/*/metadata.json')):
        meta = read(path)
        assert sha(path.parent / 'request.body') == meta['request_body_sha256']
        assert sha(path.parent / 'response.body') == meta['saved_response_body_sha256']
        assert meta['http_status'] == 200 and meta['returned_model'] == 'glm-5.2'
        requests.append({'sequence': meta['sequence'], 'ledger_id': meta['ledger_id'], 'role': 'judge',
                         'request_sha256': meta['request_body_sha256'], 'response_sha256': meta['saved_response_body_sha256']})
    assert len(requests) == summary['total_attempts']
    assert len({r['ledger_id'] for r in requests}) == len(requests)
    assert sorted(r['ledger_id'] for r in requests) == list(range(63, 552))
    context = cohort_root / 'publication-context'; context.mkdir(exist_ok=False)
    for p in cohort_root.iterdir():
        if p.is_file() and p.suffix in {'.json', '.log', '.md'}:
            shutil.copyfile(p, context / p.name)
    for name in ('capture_source', 'plans', 'questions', 'execution-status'):
        shutil.copytree(cohort_root / name, context / name)
    for p in (cohort_root / 'validation').rglob('*'):
        if p.is_file() and p.suffix in {'.log', '.json'}:
            dest = context / p.relative_to(cohort_root); dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dest)
    for p in (cohort_root / 'judge').iterdir():
        if p.is_file():
            dest = context / 'judge-preparation' / p.name; dest.parent.mkdir(exist_ok=True)
            shutil.copyfile(p, dest)
    helper_names = ['review_hard_cohort_a3.py', 'inspect_hard_case_a3.py', 'seal_hard_case_a3.py',
        'audit_query_arguments_a3.py', 'test_audit_query_arguments_a3.py', 'prepare_hard_judge_a3.py',
        'summarize_hard_cohort_a3.py', 'publish_hard_cohort_a3.py', 'publish_trace_bundle_a3.py']
    (context / 'post_run_source').mkdir()
    for name in helper_names:
        shutil.copyfile(examples / name, context / 'post_run_source' / name)
    write(context / 'FINAL_SOURCE_TRACE_CHECKS.json', {'utc': utc(), 'preregistration_unchanged': True,
        'cases': validations, 'http_attempts': len(requests), 'ledger_ids_unique_and_contiguous': True,
        'requests': requests})
    for name, source in [('cohort', context), ('judge', judge), ('evaluation', cohort_root / 'evaluation')]:
        seal(source); sources[name] = source
    identities = build(sources, output, private_host, private_user)
    for qid in cohort['qids']:
        reading_views(output / ('q' + qid))
    rows = read(output / 'evaluation/cases.json')
    labels = read(output / 'judge/judgments.json')
    public_checks = []
    for row in rows:
        label = 'q' + row['qid']; root = output / label
        a = Archive(root / 'episode.sqlite', readonly=True)
        try:
            assert a.verify()['head'] == row['head'] == identities[label]['published_head']
            assert a.report()['terminal']['answer'] == row['answer']
        finally:
            a.close()
        if row['submitted']:
            assert next(x for x in labels if x['qid'] == row['qid'])['head'] == row['head']
        assert len(list((root / 'rounds').glob('round-*.md'))) == row['policy_attempts']
        public_checks.append({'qid': row['qid'], 'head': row['head'], 'judge_binding_valid': True,
                              'reading_rounds': row['policy_attempts']})
    write(output / 'PUBLICATION_VALIDATION.json', {'utc': utc(), 'cases': public_checks,
        'http_attempts': len(requests), 'all_raw_http_bodies_byte_exact': True,
        'all_private_source_manifests_valid': True, 'core_source_unchanged': True})
    lines = ['# STRIDE a3：12 题完整轨迹与评估', '',
        '**6/12 正确（6 个正式提交全部 judge 判对，4 个预算耗尽，2 个弃答）。本批 489 次调用，累计剩余 449 次。**', '',
        '先读 [完整批次分析](evaluation/BATCH_ANALYSIS.md) 与 [机器可读结果](evaluation/cases.json)。q788 名称判对，但条件解释存在证据矛盾；正式标签与证据审阅分别保留。', '',
        '| 题号 | policy 调用 | 正式结果 | 交互分析 | 证据审阅 | 每轮原始请求与响应 |',
        '| --- | ---: | --- | --- | --- | --- |']
    for row in rows:
        q = row['qid']; result = 'judge 对' if row['score_correct'] else row['outcome']
        lines.append(f'| {q} | {row["policy_attempts"]} | {result} | [分析](q{q}/INTERACTION_ANALYSIS.md) | [证据](q{q}/EVIDENCE_AUDIT.md) | [逐轮](q{q}/rounds/README.md) |')
    lines += ['', '每题保留 episode.sqlite、完整 FULL_INTERACTION、逐轮 ROUND_ANALYSIS、原始 HTTP .body、查询实际编译与返回、可见性表、工具完整性表、文档与证据原文。逐题报告在 gold/judge 前封存，其 formal_correct=null 保持历史原貌；最终分数见 evaluation 与 judge。', '',
        '[费用及额度](evaluation/summary.json) · [原始 judge](judge/judgments.json) · [运行前预算](cohort/budget-plan.json) · [gold 读取时间](cohort/judge-preparation/gold-access.json) · [源代码与 489 次请求核对](cohort/FINAL_SOURCE_TRACE_CHECKS.json)', '',
        '公开 archive 只脱敏部署信息并重算事件哈希链；模型消息、工具结果、文档、证据和原始 HTTP 请求/响应正文保持相同。使用 [head 映射](ARCHIVE_HEAD_MAP.json) 对照私有封存与公开 archive；[文件变换记录](PUBLICATION_FILES.json) 说明脱敏范围。最终公开文件以根 MANIFEST.sha256.json 核验，SOURCE_FILE_HASHES 保存原始来源哈希。', '',
        '全量生产索引、语料、未选 gold、凭据、虚拟环境与跨会话预算数据库不在发布包中。运行代码版本为 5d7752be94a9d40aa757383d8899504bc0f81e81；仓库本次提交保存实验材料，不改变该运行身份。', '']
    (output / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
    for path in output.rglob('*'):
        if not path.is_file():
            continue
        data = path.read_bytes()
        for encoding in ('utf-8', 'utf-16-le', 'utf-16-be'):
            if private_host.encode(encoding) in data or private_user.encode(encoding) in data:
                raise ValueError('Private deployment marker remains')
        if re.search(rb'sk-[A-Za-z0-9_-]{20,}', data):
            raise ValueError('Credential pattern remains')
        if path.stat().st_size >= 100_000_000:
            raise ValueError('File exceeds publication size limit')
    seal(output)
    print(json.dumps({'output': str(output), 'files': len(read(output / 'MANIFEST.sha256.json')),
                      'bytes': sum(p.stat().st_size for p in output.rglob('*') if p.is_file())}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort', required=True); p.add_argument('--output', required=True)
    p.add_argument('--private-host', required=True); p.add_argument('--private-user', required=True)
    a = p.parse_args(); publish(a.cohort, a.output, a.private_host, a.private_user)
