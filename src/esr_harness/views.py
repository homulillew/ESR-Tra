"""Retrieval adapters and exact, immutable observation construction."""
from __future__ import annotations

import dataclasses
import json
import math
import re
import urllib.error
import urllib.request
from typing import Any, Protocol

from .protocol import HarnessError, digest


class Retriever(Protocol):
    def search(self, query: str, top_k: int) -> list: ...
    def get_document(self, docid: str) -> Any: ...


def mapping(value: Any) -> dict:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, dict):
        return dict(value)
    raise HarnessError("retrieval_error", "Retriever returned a non-object")


def document(row: Any, requested_id: str) -> dict:
    row = mapping(row)
    nested = row.get("document", row)
    docid = str(row.get("docid", nested.get("docid", requested_id)))
    if docid != requested_id:
        raise HarnessError("retrieval_error", "Document identity mismatch")
    content = nested.get("content", nested.get("contents", nested.get("text", "")))
    if not isinstance(content, str) or not content.strip():
        raise HarnessError("retrieval_error", "Document has no nonempty text")
    result = {"docid": docid, "title": str(nested.get("title", "")),
              "url": str(nested.get("url", "")), "content": content}
    result["document_hash"] = digest(result)
    return result


def hit(row: Any) -> dict:
    row = mapping(row)
    nested = row.get("document") or {}
    docid = str(row.get("docid", row.get("id", "")))
    if not docid:
        raise HarnessError("retrieval_error", "Search hit has no docid")
    score = row.get("score", 0.0)
    if not isinstance(score, (float, int)) or not math.isfinite(score):
        raise HarnessError("retrieval_error", "Invalid retrieval score")
    return {"docid": docid, "title": str(row.get("title", nested.get("title", "")))[:500],
            "url": str(row.get("url", nested.get("url", "")))[:2000], "score": score,
            "snippet": str(row.get("snippet", row.get("content", row.get("text", nested.get("contents", "")))))[:1600]}


def post_json(url: str, body: dict, *, timeout: float = 60, headers: dict | None = None) -> dict:
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Do not log response bodies or headers (may contain provider credentials).
        raise HarnessError("service_error", f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise HarnessError("service_error", f"Request failed: {type(exc).__name__}") from exc
    if not isinstance(result, dict):
        raise HarnessError("service_error", "Expected service JSON object")
    return result


class EchoRetriever:
    """Matches existing /retrieve, /get_doc and optional /get_doc_chunks contracts."""
    def __init__(self, base_url: str, timeout: float = 60):
        self.base_url, self.timeout = base_url.rstrip("/"), timeout
        self.identity = {"type": "echo", "base_url": self.base_url}

    def search(self, query: str, top_k: int) -> list:
        result = post_json(self.base_url + "/retrieve", {"queries": [query], "topk": top_k}, timeout=self.timeout)
        rows = result.get("result", result.get("results", []))
        if rows and isinstance(rows[0], list):
            rows = rows[0]
        if not isinstance(rows, list):
            raise HarnessError("retrieval_error", "Invalid search result list")
        return [hit(row) for row in rows]

    def get_document(self, docid: str) -> dict:
        return post_json(self.base_url + "/get_doc", {"docid": docid}, timeout=self.timeout)

    def get_doc_chunks(self, docid: str, query: str, topk: int = 3) -> dict:
        return post_json(self.base_url + "/get_doc_chunks", {"docid": docid, "query": query,
                         "topk": topk, "chunk_size": 512, "chunk_overlap": 64}, timeout=self.timeout)


class MemoryRetriever:
    """Deterministic lexical test adapter, not a benchmark retriever."""
    def __init__(self, documents: list[dict]):
        self.documents = {str(d["docid"]): document(d, str(d["docid"])) for d in documents}
        self.identity = {"type": "memory", "corpus_hash": digest(self.documents)}

    def search(self, query: str, top_k: int) -> list:
        terms = set(re.findall(r"\w+", query.lower()))
        scored = []
        for doc in self.documents.values():
            score = len(terms & set(re.findall(r"\w+", (doc["title"] + " " + doc["content"]).lower())))
            if score:
                scored.append({"docid": doc["docid"], "title": doc["title"], "snippet": doc["content"][:1600], "score": score})
        return sorted(scored, key=lambda h: (-h["score"], h["docid"]))[:top_k]

    def get_document(self, docid: str) -> dict:
        if docid not in self.documents:
            raise HarnessError("retrieval_error", f"Unknown document {docid}")
        return dict(self.documents[docid])


def merge_spans(spans: list[list[int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def make_view(doc: dict, retriever: Retriever, query: str, *, limit: int, top_k: int,
              offset: int | None = None) -> dict:
    """Remote chunks must map to raw text. Otherwise use a labelled local fallback.

    Character caps define the observation, not a hidden downstream truncation. Every
    returned character is stored; policy/read/audit use this exact stored rendering.
    """
    full, fallback, source = doc["content"], None, "remote_chunks"
    spans: list[list[int]] = []
    if offset is not None:
        if offset >= len(full):
            raise HarnessError("protocol_error", "offset is outside the document")
        spans, source = [[offset, min(offset + limit, len(full))]], "raw_window"
    else:
        chunks_fn = getattr(retriever, "get_doc_chunks", None)
        try:
            if chunks_fn is None:
                raise HarnessError("chunks_unavailable", "Adapter has no chunk endpoint")
            response = chunks_fn(doc["docid"], query, topk=top_k)
            chunks = response.get("chunks", [])
            if not chunks:
                raise HarnessError("chunks_unavailable", "Empty chunk list")
            for chunk in chunks[:top_k]:
                text = chunk.get("text", "")
                if not isinstance(text, str) or not text.strip() or text not in full:
                    raise HarnessError("chunks_not_verbatim", "Chunk cannot be mapped to raw text")
                start = full.find(text)
                spans.append([start, start + len(text)])
        except (HarnessError, KeyError, TypeError, ValueError, AttributeError, OSError, NotImplementedError) as exc:
            fallback = getattr(exc, "code", type(exc).__name__)
            source = "local_lexical_chunks"
            # Exact character windows make tail access possible even without the optional service.
            width = min(2000, limit)
            terms = set(re.findall(r"\w+", query.lower()))
            candidates = []
            for start in range(0, len(full), width):
                end = min(start + width, len(full))
                score = len(terms & set(re.findall(r"\w+", full[start:end].lower())))
                candidates.append((-score, start, end))
            spans = [[s, e] for _, s, e in sorted(candidates)[:top_k]]
    selected, remaining = [], limit
    for start, end in merge_spans(spans):
        if remaining <= 0:
            break
        end = min(end, start + remaining)
        selected.append([start, end])
        remaining -= end - start
    if not selected:
        raise HarnessError("retrieval_error", "No visible text")
    parts = [full[s:e] for s, e in selected]
    rendered = "\n\n".join(f"[chars {s}:{e}]\n{text}" for (s, e), text in zip(selected, parts))
    identity = {"docid": doc["docid"], "document_hash": doc["document_hash"], "spans": selected, "text": rendered}
    return {**identity, "view_hash": digest(identity), "source": source, "fallback": fallback,
            "query": query, "raw_parts": parts, "document_chars": len(full),
            "fully_visible": selected == [[0, len(full)]]}
