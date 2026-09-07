"""固定语料检索接口及不依赖第三方库的调试实现。"""

from __future__ import annotations

import json
import math
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

from .models import RetrievedDocument, SearchHit


class Retriever(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[SearchHit]: ...

    def get_document(self, docid: str) -> RetrievedDocument: ...

    def get_doc_chunks(self, docid: str, query: str, topk: int = 3) -> dict:
        """第二段检索：把单篇文档按 token 分块，BM25 按 query 排序，返回 topk 个关键 chunk。

        返回 {"docid", "title", "total_chunks", "chunks": [{"chunk_index","score","text"}...]}。
        服务不可用/不支持时允许抛异常，由环境层回退到头截断。
        """


@dataclass
class InMemoryRetriever:
    """用于测试和 CPU 冒烟实验的确定性 BM25 风格检索器。"""

    documents: dict[str, RetrievedDocument]

    @classmethod
    def from_documents(cls, documents: Iterable[RetrievedDocument]) -> "InMemoryRetriever":
        return cls({item.docid: item for item in documents})

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "InMemoryRetriever":
        documents: list[RetrievedDocument] = []
        with Path(path).open("r", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                documents.append(
                    RetrievedDocument(
                        docid=str(row["docid"]),
                        content=str(row.get("content", row.get("text", row.get("contents", "")))),
                        title=str(row.get("title", "")),
                        url=str(row.get("url", "")),
                    )
                )
        return cls.from_documents(documents)

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        query_tokens = _tokens(query)
        ranked: list[tuple[float, RetrievedDocument]] = []
        for document in self.documents.values():
            document_tokens = _tokens(f"{document.title} {document.content}")
            counts = {token: document_tokens.count(token) for token in query_tokens}
            score = sum((1.0 + math.log(count)) if count else 0.0 for count in counts.values())
            if score > 0:
                ranked.append((score, document))
        ranked.sort(key=lambda item: (-item[0], item[1].docid))
        return [
            SearchHit(
                docid=document.docid,
                snippet=document.content[:1600],
                score=score,
                title=document.title,
                url=document.url,
            )
            for score, document in ranked[:top_k]
        ]

    def get_document(self, docid: str) -> RetrievedDocument:
        try:
            return self.documents[docid]
        except KeyError as exc:
            raise KeyError(f"unknown document: {docid}") from exc

    def get_doc_chunks(self, docid: str, query: str, topk: int = 3,
                       chunk_size: int = 512, chunk_overlap: int = 64) -> dict:
        """与 BM25 服务端 /get_doc_chunks 同构的内存实现：分块 + BM25 按 query 排序。

        供 CPU 冒烟/单测使用（确定性）。chunk_size/overlap 以"token≈4 char"换算成字符。
        """
        try:
            full = self.documents[docid].content
        except KeyError as exc:
            raise KeyError(f"unknown document: {docid}") from exc
        char_chunk = chunk_size * 4
        step = max(char_chunk - chunk_overlap * 4, 1)
        chunks: list[str] = []
        start = 0
        while start < len(full):
            chunk = full[start:start + char_chunk]
            if chunk.strip():
                chunks.append(chunk)
            start += step
            if start + char_chunk >= len(full) and start < len(full):
                # 保证覆盖末尾
                tail = full[start:]
                if tail.strip() and tail not in chunks:
                    chunks.append(tail)
                break
        if not chunks:
            return {"docid": docid, "title": "", "total_chunks": 0, "chunks": []}
        q_tokens = set(_tokens(query))
        scored: list[tuple[float, int, str]] = []
        for i, c in enumerate(chunks):
            c_tokens = _tokens(c)
            s = sum(1 + math.log(c_tokens.count(t)) for t in q_tokens if t in c_tokens)
            scored.append((s, i, c))
        scored.sort(key=lambda x: (-x[0], x[1]))
        top = scored[:max(0, min(topk, len(scored)))]
        return {
            "docid": docid,
            "title": self.documents[docid].title,
            "total_chunks": len(chunks),
            "chunks": [{"chunk_index": idx, "score": round(s, 4), "text": txt}
                       for s, idx, txt in top],
        }


@dataclass
class EchoRetrievalClient:
    """调用 ECHO BrowseComp 检索服务的轻量客户端。"""

    base_url: str = "http://127.0.0.1:8000"
    timeout_seconds: float = 60.0

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        payload = self._post("/retrieve", {"queries": [query], "topk": top_k})
        rows = payload.get("result", payload.get("results", payload))
        if rows and isinstance(rows[0], list):
            rows = rows[0]
        return [
            SearchHit(
                docid=str(row.get("docid", row.get("id", ""))),
                snippet=(
                    str(row.get("content", row.get("text", "")))
                    or str((row.get("document") or {}).get("contents", ""))
                )[:1600],
                score=float(row.get("score", 0.0)),
                title=(
                    str(row.get("title", ""))
                    or str((row.get("document") or {}).get("title", ""))
                ),
                url=str(row.get("url", "")),
            )
            for row in rows
        ]

    def get_document(self, docid: str) -> RetrievedDocument:
        row = self._post("/get_doc", {"docid": docid})
        # BM25 服务返回 {"document": {"contents": ..., "title": ..., "url": ...}, "docid": ...}
        document = row.get("document") if isinstance(row.get("document"), dict) else row
        return RetrievedDocument(
            docid=str(row.get("docid", document.get("docid", docid))),
            content=str(document.get("contents", document.get("content", document.get("text", "")))),
            title=str(document.get("title", "")),
            url=str(document.get("url", "")),
        )

    def get_doc_chunks(self, docid: str, query: str, topk: int = 3,
                       chunk_size: int = 512, chunk_overlap: int = 64) -> dict:
        """第二段检索：复用服务端 /get_doc_chunks，把单篇文档分块并按 query 用 BM25 排序。

        返回服务端原始结构：{"docid", "title", "total_chunks",
        "chunks": [{"chunk_index","score","text"}...]}。服务异常会抛异常，由环境回退。
        """
        payload = {
            "docid": docid,
            "query": query,
            "topk": topk,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        }
        return self._post("/get_doc_chunks", payload)

    def _post(self, endpoint: str, payload: dict[str, object]) -> dict:
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())

