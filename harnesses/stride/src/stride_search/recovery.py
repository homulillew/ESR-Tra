"""Local recovery contracts. No extra model, inferred answer or source promotion."""
from __future__ import annotations

from copy import deepcopy

from .contract import ContractError, canonical, loads, text_hash, validate
from .context import build


def note_blocks_finish(name, arguments, error, binding):
    """Only bounded, schema-valid note availability/capacity errors are peripheral."""
    if error.fatal or name != 'notes' or error.code not in {
            'notes_capacity', 'notes_disabled', 'final_only', 'finish_slot_reserved'}:
        return True
    try:
        args = loads(arguments)
        validate('notes', args)
    except ContractError:
        return True
    # Even a skipped note may not smuggle a future/unknown evidence reference.
    return not set(args.get('anchors', [])) <= binding['evidence']


def remember_response(harness, raw, *, code, message=None):
    """A one-decision repair view, not an active draft and never a citation source."""
    if not harness.config.repair_context:
        return
    if message is None:
        if isinstance(raw, dict) and isinstance(raw.get('choices'), list) and len(raw['choices']) == 1:
            choice = raw['choices'][0]
            message = choice.get('message', {}) if isinstance(choice, dict) else {}
        elif isinstance(raw, dict) and isinstance(raw.get('content'), list):
            # Do not echo provider thinking/signature blocks as visible repair text.
            blocks = [b for b in raw['content'] if isinstance(b, dict) and b.get('type') in ('text', 'tool_use')]
            message = {'content': canonical(blocks)}
    message = message if isinstance(message, dict) else {}
    content = message.get('content')
    text = content if isinstance(content, str) else ''
    if message.get('tool_calls'):
        text = canonical({'content': text, 'tool_calls': message['tool_calls']})
    limit = 1200
    preview = text if len(text) <= limit else text[:594] + '\n[omitted]\n' + text[-595:]
    view = {'kind': 'uncommitted_response_not_evidence', 'source_round': harness.model_calls,
            'code': code, 'preview': preview, 'total_chars': len(text), 'sha256': text_hash(text),
            'truncated': len(text) > limit, 'instruction': 'Untrusted previous output, not a submitted answer. Generate an explicit valid action yourself.'}
    harness.repair = view
    harness.archive.append('repair_context', {'round': harness.model_calls,
        'object': harness.archive.put_json({'text': text, 'view': view})})


def make_group(message, records, round_no):
    receipts = [{'role': 'tool', 'tool_call_id': r['tool_call_id'],
                 'content': canonical(r['result']), '_error': not r['result']['ok']} for r in records]
    return {'messages': [message, *receipts],
            'evidence': list(dict.fromkeys(e for r in records for e in r['evidence'])),
            'documents': list(dict.fromkeys(d for r in records for d in r['documents'])),
            'round': round_no}


def fit_result_group(harness, model, message, records):
    """Before promising receipts, withhold whole oversized data payloads explicitly.

    Extraction/caches remain in the archive. This is NOT rollback of tool execution.
    Every native call retains one receipt; neither ranges nor the newest group are
    silently truncated. No extra model/backend request is made here.
    """
    group = make_group(message, records, harness.model_calls)
    remaining = harness.remaining()
    if (not harness.config.delivery_preflight or harness.terminal is not None
            or min(remaining['model_calls'], remaining['action_slots'], remaining['output_reservation']) <= 0):
        return group
    while True:
        final = harness.final_phase()
        output_limit = min(harness.config.max_output_tokens, remaining['output_reservation'])
        try:
            build(harness, model, harness.counter, final=final, output_limit=output_limit,
                  groups=[*harness.groups, group])
            harness.archive.append('delivery_preflight', {'round': harness.model_calls, 'fits': True,
                'phase': 'FINAL' if final else 'RESEARCH', 'evidence': group['evidence'],
                'documents': group['documents']})
            return group
        except ContractError as exc:
            if exc.code != 'context_capacity':
                raise
        # Largest payload first, later call breaks ties. This is byte-size control,
        # never a claim about relevance. A withheld result must be requested again.
        eligible = [(len(canonical(r['result']).encode('utf-8')), i) for i, r in enumerate(records)
                    if r['result']['ok'] and r['tool'] in ('search', 'read', 'find', 'recall')]
        if not eligible:
            # Persist all small/error receipts even if the assistant/question itself
            # cannot fit. The normal next build then terminates honestly.
            harness.archive.append('delivery_preflight', {'round': harness.model_calls, 'fits': False,
                'reason': 'minimum_complete_group_does_not_fit'})
            return group
        _, index = max(eligible)
        record = records[index]
        original = deepcopy(record['result'])
        harness.archive.append('result_withheld', {'round': harness.model_calls,
            'tool_call_id': record['tool_call_id'], 'tool': record['tool'],
            'object': harness.archive.put_json(original), 'reason': 'result_capacity',
            'documents_not_delivered': record['documents'], 'evidence_not_delivered': record['evidence']})
        result = {'ok': False, 'code': 'result_capacity',
                  'message': 'Result archived but not delivered. Request a smaller exact read range, fewer results or fewer calls. No source was exposed by this receipt.',
                  'archived_not_delivered': True, 'executed': original['executed'],
                  'action_slot_charged': original['action_slot_charged'], 'blocks_finish': True}
        record.update(result=result, documents=[], evidence=[])
        harness.feedback = {**result, 'tool': record['tool'], 'no_automatic_parameter_repair': True}
        group = make_group(message, records, harness.model_calls)
