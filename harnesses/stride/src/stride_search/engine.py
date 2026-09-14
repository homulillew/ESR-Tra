"""Single-policy read-first loop. No draft state, claim graph or implicit reviewer."""
from __future__ import annotations

from copy import deepcopy
import re
import time
from typing import Callable

from .archive import Archive
from .context import build
from .contract import PROTOCOL, Config, ContractError, canonical, digest, loads, text_hash, validate
from .providers import ByteCounter, usage_of
from .recovery import fit_result_group, make_group, note_blocks_finish, remember_response


class Harness:
    def __init__(self, question: str, retriever, *, path=":memory:", config: Config | None = None,
                 counter=None, clock: Callable[[], float] = time.monotonic):
        if not isinstance(question, str) or not question.strip():
            raise ValueError("A nonempty original question is required")
        self.question, self.retriever = question, retriever
        self.config, self.counter = config or Config(), counter or ByteCounter()
        self.clock, self.started = clock, clock()
        self.archive = Archive(path)
        self.groups, self.group_refs = [], []
        self.exposed, self.published_docs = set(), set()
        self.evidence_order, self.doc_order = [], []
        self.notes, self.note_history = {}, []
        self.search_cache = {}
        self.model_calls = self.action_slots = self.declared_calls = self.backend_calls = 0
        self.output_charged = 0
        self.feedback, self.terminal, self.model_identity = None, None, None
        self.repair = None
        self.archive.append("episode", {"protocol": PROTOCOL, "question": question,
            "config": self.config.to_dict(), "retriever": deepcopy(retriever.identity),
            "counter": deepcopy(self.counter.identity), "execution": "fresh_episode_only"})

    def remaining(self):
        return {"model_calls": self.config.max_model_calls - self.model_calls,
                "action_slots": self.config.max_actions - self.action_slots,
                "backend_calls": self.config.max_backend_calls - self.backend_calls,
                "output_reservation": self.config.max_total_output_tokens - self.output_charged}

    def final_phase(self):
        r = self.remaining()
        return self.config.reserve_finish and (r["model_calls"] == 1 or r["action_slots"] == 1
                or r["output_reservation"] <= self.config.max_output_tokens)

    def _time_check(self):
        if self.clock() - self.started >= self.config.max_seconds:
            raise ContractError("time_budget", "Time budget exhausted", fatal=True)

    def _end(self, outcome, **fields):
        if self.terminal is None:
            self.terminal = {"outcome": outcome, "answer": "", **fields,
                             "elapsed_seconds": self.clock() - self.started}
            self.archive.append("terminal", deepcopy(self.terminal))
        return deepcopy(self.terminal)

    def _backend(self, kind, args, function):
        self._time_check()
        if self.backend_calls >= self.config.max_backend_calls:
            raise ContractError("backend_budget", "No backend request budget remains; existing evidence is still usable")
        self.backend_calls += 1
        self.archive.append("backend_request", {"kind": kind, "arguments": args, "number": self.backend_calls})
        start = self.clock()
        try:
            value = function()
        except Exception as exc:
            code = exc.code if isinstance(exc, ContractError) else "backend_failure"
            self.archive.append("backend_error", {"kind": kind, "code": code,
                "exception_type": type(exc).__name__, "elapsed_seconds": self.clock() - start})
            raise ContractError(code, "Backend failed; no automatic retry or provider switch", fatal=True) from exc
        raw_wire = getattr(self.retriever, "last_wire_response", None)
        self.archive.append("backend_response", {"kind": kind, "object": self.archive.put_json(value),
            "raw_wire": self.archive.put_json(raw_wire) if raw_wire is not None else None,
            "wire_request": deepcopy(getattr(self.retriever, "last_wire_request", None)),
            "elapsed_seconds": self.clock() - start})
        return value

    def _snapshot(self, ref):
        doc = self.archive.doc(ref)
        if doc["snapshot"]:
            return doc["snapshot"]
        value = self._backend("get_document", {"docid": doc["backend"]},
                              lambda: self.retriever.get_document(doc["backend"]))
        if (not isinstance(value, dict) or value.get("docid") != doc["backend"]
                or not isinstance(value.get("content"), str) or not value["content"].strip()):
            raise ContractError("retrieval_protocol", "Document identity/text invalid", fatal=True)
        if len(value["content"]) > self.config.max_document_chars:
            raise ContractError("document_size", "Document exceeds the explicit local limit", fatal=True)
        return self.archive.snapshot(ref, value["content"])

    @staticmethod
    def _allowed(ref, allowed, kind):
        if ref not in allowed:
            raise ContractError("unreceived_reference", f"{kind} {ref} was not in this decision's received-reference scope")

    def _dispatch(self, name, args, binding):
        if name == "search":
            if len(args["queries"]) > self.config.max_queries_per_search:
                raise ContractError("query_batch_limit", "Too many queries for the current experimental arm")
            keys = [digest([self.retriever.identity, q, args.get("top_k", 5)]) for q in args["queries"]]
            needed = sum(k not in self.search_cache for k in keys)
            if needed > self.config.max_backend_calls - self.backend_calls:
                raise ContractError("backend_budget", "Not enough remaining backend budget for this query batch; reduce queries")
            outputs, docs = [], []
            for query in args["queries"]:
                top_k = args.get("top_k", 5)
                key = digest([self.retriever.identity, query, top_k])
                cached = key in self.search_cache
                if cached:
                    rows = deepcopy(self.search_cache[key])
                else:
                    rows = self._backend("search", {"query": query, "top_k": top_k},
                                         lambda: self.retriever.search(query, top_k))
                if not isinstance(rows, list):
                    raise ContractError("retrieval_protocol", "Search must return a list", fatal=True)
                # Validate the whole selected result before mutating navigation state.
                for row in rows[:top_k]:
                    if (not isinstance(row, dict) or not isinstance(row.get("docid"), str) or not row["docid"]
                            or not isinstance(row.get("title"), str) or not isinstance(row.get("snippet"), str)):
                        raise ContractError("retrieval_protocol", "Malformed search hit", fatal=True)
                self.search_cache[key] = deepcopy(rows[:top_k])
                hits = []
                for row in rows[:top_k]:
                    ref = self.archive.register_doc(row["docid"], row["title"][:300])
                    seen = ref in self.published_docs
                    hits.append({"ref": ref, "title": row["title"][:300], "snippet": row["snippet"][:400],
                                 "previously_received": seen, "kind": "navigation_not_evidence"})
                    docs.append(ref)
                outputs.append({"query": query, "hits": hits, "cached": cached})
            return {"results": outputs}, docs, []
        if name in ("read", "find"):
            ref = args["ref"]
            if ref.startswith("e"):
                self._allowed(ref, binding["evidence"], "Evidence")
                if set(args) != {"ref"}:
                    raise ContractError("replay_arguments", "Evidence replay uses the exact saved window; omit start/length")
                view = self.archive.evidence(ref)
                return {"evidence": view, "replayed": True}, [], [ref]
            self._allowed(ref, binding["documents"], "Document")
            sha = self._snapshot(ref)
            full = self.archive.get(sha)
            start = args.get("start", 0)
            if name == "find":
                if start > len(full):
                    raise ContractError("range", "Start exceeds the document length")
                needle, found, pos = args["text"], [], start
                for _ in range(8):
                    pos = full.find(needle, pos)
                    if pos < 0:
                        break
                    found.append({"start": pos, "end": pos + len(needle),
                                  "excerpt": full[max(0, pos - 60):min(len(full), pos + len(needle) + 60)][:250]})
                    pos += max(1, len(needle))
                return {"document": ref, "snapshot": sha, "matches": found,
                        "next_start": pos if len(found) == 8 and pos < len(full) else None,
                        "kind": "positions_not_evidence", "case_sensitive": True}, [], []
            view = self.archive.window(ref, start, args.get("length", self.config.read_chars))
            return {"evidence": view, "previously_received": view["ref"] in self.exposed,
                    "next_start": view["end"] if view["end"] < view["document_chars"] else None}, [], [view["ref"]]
        if name == "recall":
            terms = re.findall(r"\w+", args["query"].casefold())
            if not terms:
                raise ContractError("query_terms", "Recall needs at least one lexical term")
            scored = []
            for order, ref in enumerate(self.evidence_order):
                view = self.archive.evidence(ref)
                title = self.archive.doc(view["document"])["title"]
                text = title + " " + view["text"]
                score = sum(t in text.casefold() for t in terms)
                if score:
                    scored.append((score, order, {"ref": ref, "title": title[:160], "excerpt": view["text"][:400],
                                                  "kind": "evidence_navigation"}))
            for order, note in enumerate(self.note_history):
                score = sum(t in note["text"].casefold() for t in terms)
                if score:
                    scored.append((score, order, {"key": note["key"], "excerpt": note["text"],
                        "active": self.notes.get(note["key"]) == note, "kind": "agent_note_not_evidence"}))
            rows = [r[2] for r in sorted(scored, key=lambda r: (r[0], r[1]), reverse=True)[:8]]
            return {"matches": rows, "retrieval": "lexical_overlap_not_semantic", "excerpt_only": True}, [], []
        if name == "notes":
            if not self.config.notes_enabled:
                raise ContractError("notes_disabled", "This experimental arm has no note tool")
            key = args["key"]
            old = self.notes.get(key)
            if args["op"] == "delete":
                self.notes.pop(key, None)
                return {"key": key, "changed": old is not None, "deleted": True}, [], []
            for ref in args["anchors"]:
                self._allowed(ref, binding["evidence"], "Note anchor")
            if old is None and len(self.notes) >= self.config.max_notes:
                raise ContractError("notes_capacity", "Scratchpad is full; explicitly replace/delete a note or omit the write")
            changed = old is None or old["text"] != args["text"] or old["anchors"] != args["anchors"]
            if changed:
                note = {"key": key, "text": args["text"], "anchors": deepcopy(args["anchors"]),
                        "order": old["order"] if old else self.archive.seq + 1,
                        "revision": (old["revision"] + 1) if old else 1, "kind": "agent_note_not_evidence"}
                self.notes[key] = note
                self.note_history.append(deepcopy(note))
            return {"key": key, "changed": changed, "kind": "scratchpad_not_verified"}, [], []
        if args.get("abstain"):
            return {"terminal": self._end("abstained", reason=args["reason"])}, [], []
        refs, answer = args["refs"], args["answer"]
        if self.config.require_sources and not refs:
            raise ContractError("sources_required", "This experiment requires explicit delivered raw evidence")
        for ref in refs:
            self._allowed(ref, binding["evidence"], "Evidence")
        if ((self.config.answer_prefix and not answer.startswith(self.config.answer_prefix))
                or (self.config.answer_suffix and not answer.endswith(self.config.answer_suffix))):
            raise ContractError("literal_contract", "Exact answer violates the explicitly configured prefix/suffix; no automatic rewriting")
        basis = [{k: v for k, v in self.archive.evidence(ref).items() if k != "text"} for ref in refs]
        return {"terminal": self._end("submitted", answer=answer, refs=refs, basis=basis,
                                      semantic_status="not_automatically_verified")}, [], []

    def run(self, model):
        if self.model_identity is not None:
            raise ContractError("already_started", "An episode cannot be run twice or silently resumed")
        self.model_identity = deepcopy(model.identity)
        self.archive.append("model_identity", self.model_identity)
        try:
            while self.terminal is None:
                self._step(model)
        except ContractError as exc:
            self._end(exc.code, detail=str(exc)[:400])
        except Exception as exc:
            self._end("implementation_error", exception_type=type(exc).__name__)
            raise
        return deepcopy(self.terminal)

    def _step(self, model):
        self._time_check()
        r = self.remaining()
        if r["model_calls"] <= 0:
            self._end("model_budget")
            return
        if r["action_slots"] <= 0:
            self._end("action_budget")
            return
        if r["output_reservation"] <= 0:
            self._end("output_budget")
            return
        output_limit = min(self.config.max_output_tokens, r["output_reservation"])
        final = self.final_phase()
        plan = build(self, model, self.counter, final=final, output_limit=output_limit)
        self.groups = plan["groups"]
        self.model_calls += 1
        round_no = self.model_calls
        self.archive.append("model_request", {"round": round_no, "request": self.archive.save_request(plan["wire"]),
            "visible_evidence": plan["visible"], "visible_documents": plan["documents"],
            "final": final, "compacted": plan["compacted"], "capacity": plan["capacity"],
            "counter": self.counter.identity, "output_reservation": output_limit})
        start = self.clock()
        try:
            raw = model.send(deepcopy(plan["wire"]))
        except Exception as exc:
            self.output_charged += output_limit  # unknown charge, never zero-cost failure
            code = exc.code if isinstance(exc, ContractError) else "model_transport"
            self.archive.append("model_failure", {"round": round_no, "code": code,
                "exception_type": type(exc).__name__, "output_reserved": output_limit,
                "elapsed_seconds": self.clock() - start})
            self._end(code)
            return
        usage = usage_of(raw, getattr(model, "provider", "openai"))
        charged = usage.get("output_tokens", output_limit)
        self.output_charged += charged
        self.archive.append("model_response", {"round": round_no, "raw": self.archive.put_json(raw),
            "usage": usage, "output_charged": charged, "response_model": raw.get("model") if isinstance(raw, dict) else None,
            "elapsed_seconds": self.clock() - start})
        if charged > output_limit:
            self._end("provider_output_overrun")
            return
        self._time_check()
        try:
            reply = model.parse(raw)
        except ContractError as exc:
            if exc.fatal:
                self._end(exc.code)
            else:
                self.feedback = {"code": exc.code, "message": str(exc), "executed": False}
                remember_response(self, raw, code=exc.code)
            return
        self.repair = None  # Repair data lasts only until the next complete response.
        # A complete response acknowledges the input; this is delivery, not comprehension.
        self.exposed.update(plan["visible"])
        self.published_docs.update(plan["documents"])
        for ref in plan["visible"]:
            if ref not in self.evidence_order:
                self.evidence_order.append(ref)
        for ref in plan["documents"]:
            if ref not in self.doc_order:
                self.doc_order.append(ref)
        self.archive.append("delivery_ack", {"round": round_no, "evidence": plan["visible"], "documents": plan["documents"]})
        binding = {"documents": frozenset(self.published_docs), "evidence": frozenset(self.exposed)}
        calls = reply.message.get("tool_calls", [])
        if not calls:
            self.feedback = {"code": "explicit_finish_required", "message": "Use finish with an exact answer and refs, or abstain; prose is not silently submitted"}
            remember_response(self, raw, code="explicit_finish_required", message=reply.message)
            return
        self.declared_calls += len(calls)
        invalid_group = "batch_limit" if len(calls) > self.config.max_batch else None
        records = []
        previous_error, blocking_error, fatal = False, False, None
        for index, call in enumerate(calls):
            name, arguments = call["function"]["name"], call["function"]["arguments"]
            executed, charged_slot = False, False
            docs, evidence = [], []
            try:
                if invalid_group:
                    raise ContractError(invalid_group, "Batch exceeds limit; no call in this batch is executed")
                if fatal or self.terminal is not None:
                    raise ContractError("not_executed", "A fatal or terminal boundary stopped this suffix")
                if final and name != "finish":
                    raise ContractError("final_only", "Final decision accepts only finish, within the original budget")
                if name == "finish" and index != len(calls) - 1:
                    raise ContractError("finish_order", "finish must be the last declared call")
                if name == "finish" and blocking_error:
                    raise ContractError("not_executed", "A failed earlier action prevents a pre-generated finish")
                if self.action_slots >= self.config.max_actions:
                    raise ContractError("action_budget", "No action slots remain")
                if self.config.reserve_finish and name != "finish" and self.config.max_actions - self.action_slots <= 1:
                    raise ContractError("finish_slot_reserved", "One action slot is reserved for an explicit finish")
                self.action_slots += 1
                charged_slot = True
                args = loads(arguments)
                validate(name, args)
                executed = True
                result, docs, evidence = self._dispatch(name, args, binding)
                result = {"ok": True, **result}
            except ContractError as exc:
                previous_error = True
                if exc.fatal:
                    fatal = exc.code
                blocks = (not self.config.nonblocking_notes
                          or note_blocks_finish(name, arguments, exc, binding))
                blocking_error = blocking_error or blocks
                result = {"ok": False, "code": exc.code, "message": str(exc)[:500], "blocks_finish": blocks}
                self.feedback = {**result, "tool": name, "no_automatic_parameter_repair": True}
            result.update(executed=executed, action_slot_charged=charged_slot)
            records.append({"round": round_no, "tool_call_id": call["id"], "tool": name,
                "arguments": arguments, "executed": executed, "result": result,
                "documents": docs, "evidence": evidence})
            # Journal execution before delivery admission; not a promised tool receipt.
            self.archive.append("action_execution", {"round": round_no, "tool_call_id": call["id"],
                "object": self.archive.put_json(records[-1])})
        if not previous_error:
            self.feedback = None
        group = (make_group(reply.message, records, round_no) if fatal else
                 fit_result_group(self, model, reply.message, records))
        for record in records:
            self.archive.append("action_result", {k: v for k, v in record.items() if k not in ("documents", "evidence")})
        self.groups.append(group)
        group_ref = self.archive.put_json(group)
        self.group_refs.append(group_ref)
        self.archive.append("round_end", {"round": round_no, "group": group_ref,
            "notes": self.archive.put_json(sorted(self.notes.values(), key=lambda n: n["order"])),
            "remaining": self.remaining()})
        if fatal:
            self._end(fatal)

    def close(self):
        self.archive.close()
