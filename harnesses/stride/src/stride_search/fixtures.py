"""Synthetic, deterministic policies. They test protocol reachability, NOT model quality."""
from __future__ import annotations
from copy import deepcopy
from .contract import canonical
from .providers import HTTP, LocalCorpus, OpenAIModel

DOCUMENTS = [
    {"docid": "archive-entry", "title": "Lumen Observatory record",
     "content": "Lumen Observatory opened in 2012. Its first director was Ada Rowan.\nThe second director was Ivo Lane."},
    {"docid": "unrelated", "title": "Lumen press archive", "content": "Lumen press archive contains historical notices."},
]


def native(*calls, content=None, usage=None, finish_reason="tool_calls"):
    msg = {"role": "assistant", "content": content, "tool_calls": [
        {"id": f"call_{i}", "type": "function", "function": {"name": n, "arguments": canonical(a)}}
        for i, (n, a) in enumerate(calls)]}
    return {"model": "fixture", "choices": [{"finish_reason": finish_reason, "message": msg}],
            "usage": usage if usage is not None else {"prompt_tokens": 100, "completion_tokens": 20}}


class ScriptedModel(OpenAIModel):
    def __init__(self, responses):
        super().__init__("http://fixture.invalid/v1", "fixture", revision="scripted-1", http=HTTP())
        self.identity = {"kind": "fixture-scripted", "model": "fixture", "revision_label": "1"}
        self.responses, self.requests = list(responses), []

    def send(self, wire):
        self.requests.append(deepcopy(wire))
        if not self.responses:
            raise RuntimeError("Fixture script exhausted")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return deepcopy(response)


def smoke_model():
    return ScriptedModel([
        native(("search", {"queries": ["Lumen Observatory first director"], "top_k": 1})),
        native(("read", {"ref": "d1"})),
        native(("finish", {"answer": "Ada Rowan", "refs": ["e1"]})),
    ])


def smoke_corpus():
    return LocalCorpus(DOCUMENTS)
