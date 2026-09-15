"""Single-policy read-first loop. No draft state, claim graph or implicit reviewer."""
from __future__ import annotations

from copy import deepcopy
import re
import time
from typing import Callable

from . import search_support
from .archive import Archive
from .context import build
from .contract import (PROTOCOL, INTEGER_ANSWER, ANSWER_CONTRACTS, Config, ContractError,
                       answer_text, canonical, digest, loads, text_hash)
from .goal_read import select_window
from .providers import ByteCounter, usage_of
from .recovery import fit_result_group, make_group, note_blocks_finish, remember_response
from .workflow import WorkflowState, navigation_result, check_search_recovery
from .workflow_contract import WorkflowConfig, validate_call
from .decision_protocol import identity as decision_identity, SearchPivotState, OnceProseState, RelationReviewState


class Harness:
    def __init__(self, question: str, retriever, *, path=":memory:", config: Config | None = None,
                 counter=None, clock: Callable[[], float] = time.monotonic,
                 validation_feedback: str = "legacy", answer_contract: str = "legacy",
                 workflow: WorkflowConfig | None = None, decision_protocol: str = "baseline"):
        decision_identity(decision_protocol)
        self.decision_protocol = decision_protocol
        self.search_pivot = SearchPivotState() if decision_protocol == "search-pivot-v1" else None
        self.once_prose = OnceProseState() if decision_protocol == "once-prose-reset-v1" else None
        self.relation_review = RelationReviewState() if decision_protocol in {"relation-review-once-v1", "relation-review-memory-v1"} else None
        self.review_memory = None
        self.workflow = WorkflowState(workflow or WorkflowConfig())
        if answer_contract not in ANSWER_CONTRACTS:
            raise ValueError("Unknown answer contract")
        self.answer_contract = answer_contract
        if validation_feedback not in ("legacy", "field"):
            raise ValueError("Unknown validation feedback experiment")
        self.validation_feedback = validation_feedback
        if not isinstance(question, str) or not question.strip():
            raise ValueError("A nonempty original question is required")
        self.question, self.retriever = question, retriever
        self.config, self.counter = config or Config(), counter or ByteCounter()
        self.clock, self.started = clock, clock()
        self.archive = Archive(path)
        self.groups, self.group_refs = [], []
        self.first_complete_round = None
        self.exposed, self.published_docs = set(), set()
        self.evidence_order, self.doc_order = [], []
        self.notes, self.note_history = {}, []
        self.search_cache = {}
        self.search_capabilities = search_support.capabilities(retriever)
        self.navigation_history, self.navigation_acked_rounds = [], set()
        self.model_calls = self.action_slots = self.declared_calls = self.backend_calls = 0
        self.output_charged = 0
        self.feedback, self.terminal, self.model_identity = None, None, None
        self.repair = None
        self.archive.append("episode", {"protocol": PROTOCOL, "question": question,
            "config": self.config.to_dict(), "retriever": deepcopy(retriever.identity),
            "counter": deepcopy(self.counter.identity), "search_capabilities": deepcopy(self.search_capabilities),
            "execution": "fresh_episode_only",
            **({"answer_contract": answer_contract} if answer_contract != "legacy" else {}),
            **({"workflow_contract": self.workflow.options.identity()} if self.workflow.options.enabled else {}),
            **({"decision_protocol": decision_identity(decision_protocol)} if decision_protocol != "baseline" else {})})

    def set_answer_contract(self, value):
        if value not in ANSWER_CONTRACTS or self.terminal is not None:
            raise ValueError("Invalid answer contract transition")
        if value != self.answer_contract:
            self.archive.append("answer_contract", {"previous": self.answer_contract, "current": value,
                                "after_round": self.model_calls})
            self.answer_contract = value

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
        if name == "update_gap" and self.workflow.options.gap_state:
            return self.workflow.update_gap(self, args, binding), [], []
        if name == "search":
            if self.workflow.options.enabled:
                check_search_recovery(self, args)
            if len(args["queries"]) > self.config.max_queries_per_search:
                raise ContractError("query_batch_limit", "Too many queries for the current experimental arm")
            specs = [search_support.query_spec(self, q, args.get("top_k", 5)) for q in args["queries"]]
            keys = [s[0] for s in specs]
            needed = len(set(keys) - set(self.search_cache))
            if needed > self.config.max_backend_calls - self.backend_calls:
                raise ContractError("backend_budget", "Not enough remaining backend budget for this query batch; reduce queries")
            outputs, docs = [], []
            for query, (key, equivalent, compiled) in zip(args["queries"], specs):
                top_k = args.get("top_k", 5)
                cached = key in self.search_cache
                self.archive.append("query_execution", {"round": self.model_calls, "query": query, "top_k": top_k,
                    "compiled": compiled, "equivalence_key": equivalent, "cache_key": key, "cached": cached})
                rows = deepcopy(self.search_cache[key]) if cached else self._backend("search", {"query": query, "top_k": top_k}, lambda: self.retriever.search(query, top_k))
                if not isinstance(rows, list):
                    raise ContractError("retrieval_protocol", "Search must return a list", fatal=True)
                for row in rows[:top_k]:
                    if (not isinstance(row, dict) or not isinstance(row.get("docid"), str) or not row["docid"]
                            or not isinstance(row.get("title"), str) or not isinstance(row.get("snippet"), str)):
                        raise ContractError("retrieval_protocol", "Malformed search hit", fatal=True)
                self.search_cache[key] = deepcopy(rows[:top_k])
                hits = []
                for row in rows[:top_k]:
                    ref = self.archive.register_doc(row["docid"], row["title"][:300])
                    hits.append({"ref": ref, "title": row["title"][:300], "snippet": row["snippet"][:400],
                                 "previously_received": ref in self.published_docs, "kind": "navigation_not_evidence"})
                    docs.append(ref)
                batch = {"query": query, "hits": hits, "cached": cached}
                if self.workflow.options.enabled:
                    batch.update(navigation_result(self, query, top_k, hits, replay=args.get("replay", False)))
                outputs.append(batch)
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
            sha = self._snapshot(ref); full = self.archive.get(sha); start = args.get("start", 0)
            if name == "find":
                if start > len(full): raise ContractError("range", "Start exceeds the document length")
                needle, found, pos = args["text"], [], start
                pattern = re.compile(re.escape(needle), re.IGNORECASE if args.get("ignore_case", False) else 0)
                for _ in range(8):
                    match = pattern.search(full, pos)
                    if match is None: break
                    found.append({"start": match.start(), "end": match.end(),
                                  "excerpt": full[max(0, match.start() - 60):min(len(full), match.end() + 60)][:250]})
                    pos = match.end()
                return {"document": ref, "snapshot": sha, "matches": found,
                        "next_start": pos if len(found) == 8 and pos < len(full) else None,
                        "kind": "positions_not_evidence", "case_sensitive": not args.get("ignore_case", False)}, [], []
            if "goal" in args:
                selection = select_window(full, args["goal"], args.get("length", self.config.read_chars))
                if not selection["matched"]:
                    return {"matched": False, "document": ref, "snapshot": sha, "selection": selection,
                            "kind": "navigation_not_evidence", "next_step": "Try literal find terms, a different goal, or read the original page from a stated start."}, [], []
                view = self.archive.window(ref, selection["start"], selection["end"] - selection["start"])
                return {"evidence": view, "selection": selection, "title": self.archive.doc(ref)["title"],
                        "previously_received": view["ref"] in self.exposed,
                        "next_start": view["end"] if view["end"] < view["document_chars"] else None}, [], [view["ref"]]
            view = self.archive.window(ref, start, args.get("length", self.config.read_chars))
            return {"evidence": view, "previously_received": view["ref"] in self.exposed,
                    "next_start": view["end"] if view["end"] < view["document_chars"] else None}, [], [view["ref"]]
        if name == "recall": return search_support.recall(self, args["query"])
        if name == "notes":
            if not self.config.notes_enabled: raise ContractError("notes_disabled", "This experimental arm has no note tool")
            key = args["key"]; old = self.notes.get(key)
            if args["op"] == "delete":
                self.notes.pop(key, None); return {"key": key, "changed": old is not None, "deleted": True}, [], []
            for ref in args["anchors"]: self._allowed(ref, binding["evidence"], "Note anchor")
            if old is None and len(self.notes) >= self.config.max_notes: raise ContractError("notes_capacity", "Scratchpad is full; explicitly replace/delete a note or omit the write")
            changed = old is None or old["text"] != args["text"] or old["anchors"] != args["anchors"]
            if changed:
                note = {"key": key, "text": args["text"], "anchors": deepcopy(args["anchors"]), "order": old["order"] if old else self.archive.seq + 1,
                        "revision": (old["revision"] + 1) if old else 1, "kind": "agent_note_not_evidence"}
                self.notes[key] = note; self.note_history.append(deepcopy(note))
            return {"key": key, "changed": changed, "kind": "scratchpad_not_verified"}, [], []
        if args.get("abstain"): return {"terminal": self._end("abstained", reason=args["reason"])}, [], []
        refs = args["refs"]; answer = answer_text(args["answer"], answer_contract=self.answer_contract)
        if self.config.require_sources and not refs: raise ContractError("sources_required", "This experiment requires explicit delivered raw evidence")
        for ref in refs: self._allowed(ref, binding["evidence"], "Evidence")
        if ((self.config.answer_prefix and not answer.startswith(self.config.answer_prefix)) or (self.config.answer_suffix and not answer.endswith(self.config.answer_suffix))):
            raise ContractError("literal_contract", "Exact answer violates the explicitly configured prefix/suffix; no automatic rewriting")
        basis = [{k: v for k, v in self.archive.evidence(ref).items() if k != "text"} for ref in refs]
        representation = {}
        if self.answer_contract == INTEGER_ANSWER:
            representation["answer_representation"] = {"rule": INTEGER_ANSWER, "input_type": "integer" if type(args["answer"]) is int else "string",
                "operation": "decimal" if type(args["answer"]) is int else "identity", **({"input_value": args["answer"]} if type(args["answer"]) is int else {})}
        return {"terminal": self._end("submitted", answer=answer, refs=refs, basis=basis,
                                      semantic_status="not_automatically_verified", **representation)}, [], []

    def run(self, model):
        if self.model_identity is not None: raise ContractError("already_started", "An episode cannot be run twice or silently resumed")
        self.model_identity = deepcopy(model.identity); self.archive.append("model_identity", self.model_identity)
        try:
            while self.terminal is None: self._step(model)
        except ContractError as exc: self._end(exc.code, detail=str(exc)[:400])
        except Exception as exc:
            self._end("implementation_error", exception_type=type(exc).__name__); raise
        return deepcopy(self.terminal)

    def _step(self, model):
        self._time_check(); r = self.remaining()
        if r["model_calls"] <= 0: self._end("model_budget"); return
        if r["action_slots"] <= 0: self._end("action_budget"); return
        if r["output_reservation"] <= 0: self._end("output_budget"); return
        output_limit = min(self.config.max_output_tokens, r["output_reservation"])
        plan = build(self, model, self.counter, final=self.final_phase(), output_limit=output_limit)
        self.groups = plan["groups"]; final = plan["final"]; workflow_stage = (plan.get("workflow_view") or {}).get("stage", "normal")
        self.model_calls += 1; round_no = self.model_calls
        self.archive.append("model_request", {"round": round_no, "request": self.archive.save_request(plan["wire"]), "visible_evidence": plan["visible"], "visible_documents": plan["documents"],
            "final": final, "compacted": plan["compacted"], "capacity": plan["capacity"], "counter": self.counter.identity, "output_reservation": output_limit,
            "evidence_shelf": plan["shelf"], "shelf_evicted_for_capacity": plan["shelf_evicted"], **({"workflow_view": plan["workflow_view"]} if self.workflow.options.enabled else {})})
        start = self.clock()
        if "history_projection" in plan:
            self.archive.append("history_projection", {"round": round_no, **plan["history_projection"]})
        if self.search_pivot is not None:
            projection = plan["search_pivot_projection"]
            self.search_pivot.commit(projection)
            if projection["trigger"] is not None:
                self.archive.append("search_pivot", {"round": round_no, **projection["trigger"]})
        if self.once_prose is not None:
            projection = plan["once_prose_state"]
            self.once_prose.commit(projection)
            if projection["trigger"] is not None:
                self.archive.append("once_prose_reset", {"round": round_no,
                    **projection["trigger"], **plan["once_prose_audit"],
                    "wire_sha256": digest(plan["wire"])})
        if self.relation_review is not None:
            projection = plan["relation_review_state"]
            self.relation_review.commit(projection)
            if projection["trigger"] is not None:
                self.archive.append("relation_review", {"round": round_no,
                    **projection["trigger"], **plan["relation_review_audit"], "wire_sha256": digest(plan["wire"]),
                    "wire_tools_sha256": digest(plan["wire"].get("tools", []))})
        if plan.get("review_memory_delivery") is not None:
            self.archive.append("review_memory_delivery", {"round": round_no,
                **plan["review_memory_delivery"], "wire_sha256": digest(plan["wire"])})
        try: raw = model.send(deepcopy(plan["wire"]))
        except Exception as exc:
            self.output_charged += output_limit; code = exc.code if isinstance(exc, ContractError) else "model_transport"
            self.archive.append("model_failure", {"round": round_no, "code": code, "exception_type": type(exc).__name__, "output_reserved": output_limit, "elapsed_seconds": self.clock() - start}); self._end(code); return
        usage = usage_of(raw, getattr(model, "provider", "openai")); charged = usage.get("output_tokens", output_limit); self.output_charged += charged
        self.archive.append("model_response", {"round": round_no, "raw": self.archive.put_json(raw), "usage": usage, "output_charged": charged,
            "response_model": raw.get("model") if isinstance(raw, dict) else None, "elapsed_seconds": self.clock() - start})
        if charged > output_limit: self._end("provider_output_overrun"); return
        self._time_check()
        try: reply = model.parse(raw)
        except ContractError as exc:
            if exc.fatal: self._end(exc.code)
            else:
                self.workflow.complete_decision(workflow_stage); self.feedback = {"code": exc.code, "message": str(exc), "executed": False}; remember_response(self, raw, code=exc.code)
                if plan.get("workflow_final"): self._end("stalled_no_submission", detail="Malformed response in bounded recovery final decision")
            return
        self.repair = None; self.exposed.update(plan["visible"]); self.published_docs.update(plan["documents"])
        for ref in plan["visible"]:
            if ref not in self.evidence_order: self.evidence_order.append(ref)
        for ref in plan["documents"]:
            if ref not in self.doc_order: self.doc_order.append(ref)
        self.archive.append("delivery_ack", {"round": round_no, "evidence": plan["visible"], "documents": plan["documents"]})
        search_support.accept_navigation(self, plan["groups"])
        if self.workflow.options.enabled: self.workflow.ack(plan["groups"], plan["visible"])
        binding = {"documents": frozenset(self.published_docs), "evidence": frozenset(self.exposed)}
        calls = reply.message.get("tool_calls", [])
        if not calls:
            self.workflow.complete_decision(workflow_stage); self.feedback = {"code": "explicit_finish_required", "message": "Use finish with an exact answer and refs, or abstain; prose is not silently submitted"}
            remember_response(self, raw, code="explicit_finish_required", message=reply.message)
            if plan.get("workflow_final"): self._end("stalled_no_submission", detail="No explicit finish in bounded recovery final decision")
            return
        self.declared_calls += len(calls); invalid_group = "batch_limit" if len(calls) > self.config.max_batch else None
        records = []; previous_error, blocking_error, fatal = False, False, None
        for index, call in enumerate(calls):
            name, arguments = call["function"]["name"], call["function"]["arguments"]; executed, charged_slot = False, False; docs, evidence = [], []
            try:
                if invalid_group: raise ContractError(invalid_group, "Batch exceeds limit; no call in this batch is executed")
                if fatal or self.terminal is not None: raise ContractError("not_executed", "A fatal or terminal boundary stopped this suffix")
                if plan.get("relation_review_audit") is not None and name not in {"search", "read", "find"}:
                    raise ContractError("relation_review_tool_only", "This review decision permits only search/read/find; no automatic replacement")
                if final and name != "finish": raise ContractError("final_only", "Final decision accepts only finish, within the original budget")
                if name == "finish" and index != len(calls) - 1: raise ContractError("finish_order", "finish must be the last declared call")
                if name == "finish" and blocking_error: raise ContractError("not_executed", "A failed earlier action prevents a pre-generated finish")
                if self.action_slots >= self.config.max_actions: raise ContractError("action_budget", "No action slots remain")
                if self.config.reserve_finish and name != "finish" and self.config.max_actions - self.action_slots <= 1: raise ContractError("finish_slot_reserved", "One action slot is reserved for an explicit finish")
                self.action_slots += 1; charged_slot = True; args = loads(arguments)
                validate_call(self.workflow.options, name, args, feedback=self.validation_feedback, answer_contract=self.answer_contract)
                executed = True; result, docs, evidence = self._dispatch(name, args, binding); result = {"ok": True, **result}
            except ContractError as exc:
                previous_error = True
                if exc.fatal: fatal = exc.code
                blocks = (not self.config.nonblocking_notes or note_blocks_finish(name, arguments, exc, binding))
                if name == "search" and exc.code == "duplicate_query_blocked": blocks = False
                blocking_error = blocking_error or blocks; result = {"ok": False, "code": exc.code, "message": str(exc)[:500], "blocks_finish": blocks}
                self.feedback = {**result, "tool": name, "no_automatic_parameter_repair": True}
            result.update(executed=executed, action_slot_charged=charged_slot)
            records.append({"round": round_no, "tool_call_id": call["id"], "tool": name, "arguments": arguments, "executed": executed, "result": result, "documents": docs, "evidence": evidence})
            self.archive.append("action_execution", {"round": round_no, "tool_call_id": call["id"], "object": self.archive.put_json(records[-1])})
        if not previous_error: self.feedback = None
        group = make_group(reply.message, records, round_no) if fatal else fit_result_group(self, model, reply.message, records)
        for record in records: self.archive.append("action_result", {k: v for k, v in record.items() if k not in ("documents", "evidence")})
        self.groups.append(group); group_ref = self.archive.put_json(group); self.group_refs.append(group_ref)
        if self.first_complete_round is None:
            self.first_complete_round = group["round"]
        if self.search_pivot is not None:
            self.search_pivot.complete(group)
        if self.once_prose is not None:
            self.once_prose.complete(group)
        if self.relation_review is not None:
            self.relation_review.complete(group)
        if self.decision_protocol == "relation-review-memory-v1" and plan.get("relation_review_audit") is not None:
            from .review_memory import capture, identity as memory_identity
            if previous_error or fatal or not all(r["result"].get("ok") is True for r in records):
                memory_audit = {"identity": memory_identity(), "source_round": round_no,
                    "source_response_sha256": digest(raw), "source_assistant_sha256": digest(reply.message),
                    "created": False, "skip_reason": "skipped_tool_error"}
            else:
                self.review_memory, memory_audit = capture(reply.message, round_no=round_no,
                    response_hash=digest(raw), input_windows=[self.archive.evidence(ref) for ref in plan["visible"]])
            self.archive.append("review_memory_capture", memory_audit)
        self.archive.append("round_end", {"round": round_no, "group": group_ref, "notes": self.archive.put_json(sorted(self.notes.values(), key=lambda n: n["order"])), "remaining": self.remaining()})
        self.workflow.complete_decision(workflow_stage)
        if fatal: self._end(fatal)
        elif plan.get("workflow_final") and self.terminal is None: self._end("stalled_no_submission", detail="No legal finish in bounded recovery final decision")

    def close(self): self.archive.close()
