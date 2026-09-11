"""Explicit network adapters and a deterministic offline fixture retriever."""
from __future__ import annotations

from copy import deepcopy
import math
import re
import urllib.error
import urllib.parse
import urllib.request

from .protocol import ContractError, canonical, digest, parse_json


def post_json(url, body, *, api_key=None, timeout=60, max_bytes=50_000_000):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password or parsed.query:
        raise ValueError('Use an http(s) endpoint without embedded credentials or query secrets')
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = 'Bearer ' + api_key
    req = urllib.request.Request(url, data=canonical(body).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ContractError('service_error', 'Response exceeds configured byte limit')
        value = parse_json(data.decode('utf-8'))
    except urllib.error.HTTPError as exc:
        # Do not log provider error bodies/headers; they may contain credentials.
        raise ContractError('service_error', f'HTTP {exc.code}') from exc
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeError) as exc:
        raise ContractError('service_error', f'HTTP transport failed: {type(exc).__name__}') from exc
    if not isinstance(value, dict):
        raise ContractError('service_error', 'Expected a JSON object response')
    return value


class OpenAICompatible:
    """Native chat-completions only. No text-first-call extraction or hidden retry."""
    def __init__(self, base_url, model, *, api_key=None, timeout=60, temperature=0):
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.username or parsed.password or parsed.query or parsed.scheme not in ('http', 'https'):
            raise ValueError('Invalid base URL; credentials must be passed separately')
        self.base_url, self.model, self.key = base_url.rstrip('/'), model, api_key
        self.timeout, self.temperature = timeout, temperature
        self.identity = {'kind': 'openai-compatible', 'endpoint': self.base_url, 'requested_model': model,
                         'temperature': temperature}

    def complete(self, request):
        payload = {**deepcopy(request), 'model': self.model, 'temperature': self.temperature}
        if payload.get('tools'):
            payload['tool_choice'] = 'auto'
        self.last_request = deepcopy(payload)  # Auth headers are deliberately not retained.
        return post_json(self.base_url + '/chat/completions', payload, api_key=self.key, timeout=self.timeout)


class EchoRetriever:
    """Same /retrieve and /get_doc contracts as the existing ESR main adapter."""
    def __init__(self, base_url, *, index_fingerprint, timeout=60):
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.username or parsed.password or parsed.query or parsed.scheme not in ('http', 'https'):
            raise ValueError('Invalid retrieval endpoint; no embedded credentials')
        if not index_fingerprint:
            raise ValueError('Provide a frozen corpus/index fingerprint for exact-request caching')
        self.base_url, self.timeout = base_url.rstrip('/'), timeout
        self.identity = {'kind': 'echo-http', 'endpoint': self.base_url, 'index_fingerprint': index_fingerprint}

    def search(self, query, top_k):
        response = post_json(self.base_url + '/retrieve', {'queries': [query], 'topk': top_k}, timeout=self.timeout)
        rows = response.get('result', response.get('results', []))
        if rows and isinstance(rows[0], list):
            rows = rows[0]
        if not isinstance(rows, list):
            raise ContractError('retrieval_error', 'Expected search list')
        result = []
        for row in rows:
            nested = row.get('document') or {}
            docid = str(row.get('docid', row.get('id', '')))
            score = row.get('score', 0)
            if not docid or type(score) not in (int, float) or not math.isfinite(score):
                raise ContractError('retrieval_error', 'Invalid document ID or score')
            result.append({'docid': docid, 'title': str(row.get('title', nested.get('title', ''))),
                           'snippet': str(row.get('snippet', row.get('content', row.get('text', nested.get('contents', '')))))})
        return result

    def get_document(self, docid):
        return post_json(self.base_url + '/get_doc', {'docid': docid}, timeout=self.timeout)


class MemoryRetriever:
    """Fixture only; never presented as a BC+ retriever or semantic search model."""
    def __init__(self, documents):
        self.documents = {str(d['docid']): deepcopy(d) for d in documents}
        self.identity = {'kind': 'fixture-lexical', 'index_fingerprint': digest(self.documents)}

    def search(self, query, top_k):
        terms = set(re.findall(r'\w+', query.casefold()))
        scored = []
        for docid, d in self.documents.items():
            score = len(terms & set(re.findall(r'\w+', (d.get('title', '') + ' ' + d['content']).casefold())))
            if score:
                scored.append((score, docid, {'docid': docid, 'title': d.get('title', ''), 'snippet': d['content'][:1000]}))
        return [r[2] for r in sorted(scored, key=lambda r: (-r[0], r[1]))[:top_k]]

    def get_document(self, docid):
        return deepcopy(self.documents[docid])


def hf_counter(tokenizer_path):
    """Deployment must validate that this template matches the serving endpoint."""
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True, trust_remote_code=False)
    def count(messages, definitions):
        kwargs = {'tokenize': True, 'add_generation_prompt': True}
        if definitions:
            kwargs['tools'] = definitions
        value = tokenizer.apply_chat_template(messages, **kwargs)
        return len(value)
    return count, 'local_chat_template_tokens'


def run_episode(harness, policy):
    while not harness.terminal:
        try:
            decision = harness.begin()
        except ContractError as exc:
            harness.end('context_capacity' if exc.code == 'context_capacity' else exc.code)
            break
        start = __import__('time').monotonic()
        try:
            raw = policy.complete(decision.payload)
        except Exception as exc:
            harness.ledger.append('policy_transport_metadata', {'decision': decision.id,
                'wire_request': deepcopy(getattr(policy, 'last_request', None))})
            harness.fail(decision, f'policy transport: {type(exc).__name__}')
            break
        harness.ledger.append('policy_timing', {'decision': decision.id, 'seconds': __import__('time').monotonic() - start,
                                               'requested_identity': policy.identity, 'response_model': raw.get('model'),
                                               'wire_request': deepcopy(getattr(policy, 'last_request', None))})
        try:
            message = raw['choices'][0]['message']
        except (KeyError, IndexError, TypeError):
            message = {}
        try:
            harness.respond(decision, message, raw=raw, usage=raw.get('usage'))
        except Exception:
            harness.end('execution_error')
            raise  # Implementation failures must not masquerade as a semantic bad case.
    return harness.terminal
