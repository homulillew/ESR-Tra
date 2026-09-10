"""Event-sourced forward state machine for the 2.1 state/action contract."""
from __future__ import annotations
from copy import copy, deepcopy
import time
from .audit import status, unresolved, validate_report
from .ledger import Ledger
from .protocol import Config, HarnessError, SCHEMA_VERSION, VERSION, digest, validate
from .state import initial_state, apply_delta, candidate_scope, edit_focus, purpose
from .views import document, hit, make_view, merge_spans, shrink_view


class Harness:
    def __init__(self, question, retriever, auditor=None, *, config=None, ledger=None, manifest=None):
        if not isinstance(question, str) or not question.strip() or len(question) > 16000:
            raise ValueError("Question must be nonempty and at most 16000 characters")
        self.question, self.retriever, self.auditor = question.strip(), retriever, auditor
        self.config, self.ledger = config or Config(), ledger or Ledger()
        if self.config.mode == "esr" and self.config.audit_mode != "off" and auditor is None:
            raise ValueError("hard/soft require an auditor")
        self.ledger.initialize({"schema_version": SCHEMA_VERSION, "implementation": VERSION,
                                "question": self.question, "config": self.config.to_dict(),
                                "retriever": getattr(retriever, "identity", {}),
                                "auditor": auditor.identity if auditor else None, "manifest": manifest or {}})
        self.state = initial_state(self.question)
        self.next_claim = 1
        self.documents, self.observations, self.searches = {}, {}, {}
        self.search_cache, self.audit_cache, self.conflicts = {}, {}, {}
        self.finding_scopes, self.cursors = {}, {}
        self.actions, self.audit_history = [], []
        self.action_sequences = {}  # Journal positions, including prospective actions in a preview.
        self.native_turns, self.native_active = {}, None
        self.pending, self.exposed = set(), set()
        self.last_audit = self.terminal = self.latest_result = None
        self.readonly = False
        self.admission = None  # Pure prospective-context predicate installed by the runner.
        for sequence, event in enumerate(self.ledger.events()):
            self._apply(event, sequence)

    @property
    def attempts(self):
        return len(self.actions)

    def _commit(self, event):
        sequence = self.ledger.append(event) - 1
        self._apply(event, sequence)

    def _apply(self, event, sequence):
        kind = event["type"]
        if kind == "native_turn":
            self.native_turns[event['decision_id']] = {**deepcopy(event), 'results': {}, 'started': [], 'complete': False, 'delivered': False}
            return
        if kind in {'native_result', 'native_call_started', 'native_turn_complete'}:
            turn = self.native_turns[event['decision_id']]
            if kind == 'native_result':
                turn['results'][str(event['index'])] = deepcopy(event['result'])
            elif kind == 'native_call_started':
                turn['started'].append(event['index'])
            else:
                if set(turn['results']) != {str(i) for i in range(len(turn['calls']))}:
                    raise ValueError('Cannot complete a native turn with missing results')
                turn['complete'] = True
            return
        if kind == "exposure":
            if event["delivery"] == "response_received":
                self.exposed.update(event["observation_ids"])
                for tid in event.get('native_turn_ids', []):
                    self.native_turns[tid]['delivered'] = True
                if self.config.mode == "baseline":
                    self.pending.difference_update(event["observation_ids"])
            return
        if kind == "end":
            self.terminal = event["terminal"]
            return
        if kind != "tool":
            return
        self.actions.append(event)
        self.action_sequences[event['action_id']] = sequence
        if 'native_call_index' in event:
            self.native_turns[event['decision_id']]['results'][str(event['native_call_index'])] = deepcopy(event['result'])
        self.latest_result = deepcopy(event["result"])
        delta = event["delta"]
        for key, store, id_key in (("document", self.documents, "docid"),
                                   ("observation", self.observations, "observation_id")):
            if key in delta:
                store[delta[key][id_key]] = delta[key]
        if "search" in delta:
            s = delta["search"]
            self.searches[event["action_id"]] = s
            if s.get("cache_key"):
                self.search_cache.setdefault(s["cache_key"], event["action_id"])
        if "state" in delta:
            self.state = delta["state"]
        self.next_claim = delta.get("next_claim", self.next_claim)
        self.finding_scopes.update(delta.get("finding_scopes", {}))
        self.pending.difference_update(delta.get("pending_remove", []))
        self.pending.update(delta.get("pending_add", []))
        self.cursors.update(delta.get("cursors", {}))
        if "audit" in delta:
            self.last_audit = delta["audit"]
            self.audit_cache[self.last_audit["fingerprint"]] = self.last_audit
            if not event["result"].get("cached"):
                self.audit_history.append(self.last_audit)
        self.conflicts.update(delta.get("conflicts", {}))
        if "terminal" in delta:
            self.terminal = delta["terminal"]

    def _preview(self, event):
        clone = copy(self)
        for key in ("state", "documents", "observations", "searches", "search_cache", "audit_cache", "conflicts",
                    "finding_scopes", "cursors", "actions", "action_sequences", "audit_history", "pending", "exposed", "native_turns"):
            setattr(clone, key, deepcopy(getattr(self, key)))
        if event.get('type') == 'tool':
            event = {'decision_id': None, **event}  # Internal open/focus probes have no decision yet.
        if self.native_active and event.get('type') == 'tool':
            event = {**event, 'decision_id': self.native_active[0], 'native_call_index': self.native_active[1]}
        sequence = max(len(self.ledger.events()), max(self.action_sequences.values(), default=-1) + 1)
        clone._apply(event, sequence)
        return clone

    def record_exposure(self, ids, decision_id, delivery="response_received", native_turn_ids=()):
        ids = sorted(set(ids))
        if not set(ids) <= set(self.observations) or delivery not in {"response_received", "unknown"}:
            raise ValueError("Invalid exposure receipt")
        if self.readonly:
            raise RuntimeError("Replay is read-only")
        if any(t not in self.native_turns or not self.native_turns[t]['complete'] for t in native_turn_ids):
            raise ValueError('Cannot deliver an incomplete tool group')
        self._commit({"type": "exposure", "decision_id": decision_id, "observation_ids": ids,
                      "view_hashes": {o: self.observations[o]["view_hash"] for o in ids}, "delivery": delivery,
                      **({'native_turn_ids': list(native_turn_ids)} if native_turn_ids else {})})

    def _purpose(self, state=None):
        return purpose(state or self.state) if self.config.mode == "esr" else None

    def audit_packet(self):
        """Only semantic inputs. Control metadata cannot invalidate an audit."""
        claims = deepcopy(self.state["claims"])
        scope = candidate_scope(self.state)
        for c in claims:
            extras = {q["observation_id"] for record in self.conflicts.values()
                      if record["scope"] == scope and record["requirement"] == c["requirement"]
                      for q in record["quotes"]}
            c["observation_ids"] = sorted(set(c["observation_ids"]) | extras)
        return {"target": self.state["target"], "answer": self.state["answer"], "claims": claims}

    def fingerprint(self):
        packet = self.audit_packet()
        ids = sorted({o for c in packet["claims"] for o in c["observation_ids"]})
        return digest({"question": self.question, "packet": packet,
                       "views": [(o, self.observations[o]["view_hash"]) for o in ids],
                       "auditor": self.auditor.identity if self.auditor else None})

    @property
    def current_audit(self):
        return deepcopy(self.audit_cache.get(self.fingerprint()))

    def execute(self, name, arguments=None, *, decision_id=None):
        if self.readonly:
            raise RuntimeError("Replay is read-only")
        if self.terminal:
            return {"ok": False, "error_code": "episode_finished", "error": "Episode is terminal"}
        if self.attempts >= self.config.max_actions:
            self.end("budget_exhausted")
            return {"ok": False, "error_code": "budget_exhausted", "error": "Action limit reached"}
        arguments = deepcopy({} if arguments is None else arguments)
        aid, start = f"a{self.attempts + 1}", time.monotonic()
        delta, output = {}, {}
        try:
            if name not in {t["name"] for t in self.config.tools}:
                if name == "invalid_model_response" and isinstance(arguments, dict):
                    raise HarnessError(arguments.get("error_code", "protocol_error"), "Invalid model output: " + str(arguments.get("error", "Malformed decision")))
                raise HarnessError("protocol_error", f"Unavailable action: {name}")
            if name == "update_state" and isinstance(arguments, dict) and arguments:
                # Semantic fields still validate atomically. Auxiliary metadata has an explicit warning path.
                core = {k:v for k,v in arguments.items() if k not in {"attempt_note", "attempt_id"}}
                schema = {**self.config.tool_schema(name), "minProperties": 0}
                validate(core, schema)
            else:
                validate(arguments, self.config.tool_schema(name))
            if getattr(self.retriever, "identity", {}) != self.ledger.header["retriever"]:
                raise HarnessError("service_error", "Declared retriever identity changed inside an episode")
            if self.auditor and self.auditor.identity != self.ledger.header["auditor"]:
                raise HarnessError("service_error", "Declared auditor identity changed inside an episode")
            if name == "search" and "focus" in arguments:
                if self.config.mode != "esr":
                    raise HarnessError("protocol_error", "Baseline has no editable focus")
                proposed = edit_focus(self.state, arguments["focus"])
                delta["state"] = proposed
                if self.admission:
                    probe = {"type": "tool", "action_id": aid, "action": name, "arguments": arguments,
                             "result": {"ok": True, "action_id": aid}, "delta": delta}
                    if not self.admission(self._preview(probe)):
                        delta = {}
                        raise HarnessError("context_capacity", "New focus does not fit; shorten the edit")
            methods = {"search": self._search, "open_page": self._open, "read_evidence": self._read,
                       "update_state": self._update, "verify_answer": self._verify,
                       "submit_answer": self._submit, "finish": self._finish}
            output, more = methods[name](aid, **arguments)
            delta.update(more)
            result = {"ok": True, "action_id": aid, **output}
        except HarnessError as exc:
            # Only a validated search-focus edit may survive an external retrieval failure.
            if name != "search" or exc.code not in {"service_error", "retrieval_error"}:
                delta = {}
            result = {"ok": False, "action_id": aid, "error_code": exc.code, "error": str(exc),
                      "error_path": str(exc).split(":", 1)[0] if str(exc).startswith(("arguments.", "state.")) else "arguments"}
            if name == "search":
                result["focus_edit_applied"] = "state" in delta
        event = {"type": "tool", "action_id": aid, "decision_id": decision_id, "action": name,
                 "arguments": arguments, "result": result, "delta": delta,
                 "elapsed_seconds": time.monotonic() - start}
        if self.native_active:
            event['native_call_index'] = self.native_active[1]
            event['native_call_id'] = self.native_turns[self.native_active[0]]['calls'][self.native_active[1]]['id']
        # Search results, updates and observations must leave an executable next prompt.
        if result["ok"] and name in {"search", "update_state", "open_page", "read_evidence"} and self.admission:
            if not self.admission(self._preview(event)):
                event['unadmitted_output'] = deepcopy(event['result'])
                event["delta"] = {}
                event["result"] = {"ok": False, "action_id": aid, "error_code": "context_capacity",
                                   "error": ("Search results do not fit; no hits were admitted. Use fewer results (smaller top_k), existing material, or finish when ready. The backend request was still counted."
                                             if name == "search" else "Required state/latest view would not fit; process pending views or shorten the edit")}
        self._commit(event)
        return deepcopy(event["result"])

    def record_protocol_error(self, message, decision_id=None, error_code="protocol_error", proposal=None):
        return self.execute("invalid_model_response", {"error": message, "error_code": error_code,
                            "parsed_proposal": proposal}, decision_id=decision_id)

    def _search(self, aid, query, top_k=None, focus=None, anchor_refs=None):
        state = edit_focus(self.state, focus) if focus is not None else self.state
        intent = self._purpose(state)
        anchors = anchor_refs or []
        valid = self.exposed | {"question"}
        if state["answer"]:
            valid.add("candidate")
        if not set(anchors) <= valid:
            raise HarnessError("unexposed_reference", "Search anchors must be question, candidate, or exposed observations")
        top_k = top_k or self.config.search_top_k
        identity = getattr(self.retriever, "identity", {})
        pinned = identity.get("corpus_hash") or identity.get("index_revision")
        can_cache = (self.config.cache_search and getattr(self.retriever, "deterministic", False)
                     and pinned not in {None, "", "unspecified"})
        key = digest([identity, query, top_k]) if can_cache else None
        cached_id = self.search_cache.get(key) if key else None
        if cached_id:
            hits = deepcopy(self.searches[cached_id]["hits"])
        else:
            rows = self.retriever.search(query, top_k)
            if not isinstance(rows, list):
                raise HarnessError("retrieval_error", "Search response must be a list")
            hits = [hit(r) for r in rows[:top_k]]
        known = {h["docid"] for s in self.searches.values() for h in s["hits"]}
        novel = sorted({h["docid"] for h in hits} - known)
        unread = [h["docid"] for h in hits if h["docid"] not in self.documents]
        search = {"query": query, "top_k": top_k, "hits": hits, "purpose": intent,
                  "anchor_refs": anchors, "cache_key": key, "cache_source": cached_id,
                  "new_hit_docids": novel}
        return {"results": hits, "cached": bool(cached_id), "cache_source": cached_id,
                "new_hit_docids": novel, "unopened_docids": unread,
                "purpose": intent, "note": "Hits navigate only; cached/unopened documents are not evidence."}, {"search": search}

    def _open(self, aid, docid, search_action_id=None, query=None, offset=None):
        if query is not None and offset is not None:
            raise HarnessError("protocol_error", "Choose query OR offset")
        if search_action_id is None:
            search_action_id = next((sid for sid, s in reversed(list(self.searches.items()))
                                     if docid in {h["docid"] for h in s["hits"]}), None)
        parent = self.searches.get(search_action_id)
        if not parent or docid not in {h["docid"] for h in parent["hits"]}:
            raise HarnessError("protocol_error", "Document must be in the referenced successful search")
        if len(self.pending) >= self.config.max_pending_views:
            raise HarnessError("context_capacity", "Pending buffer full; update or dismiss existing observations before opening more")
        intent = self._purpose()
        doc = self.documents.get(docid) or document(self.retriever.get_document(docid), docid)
        proposed = make_view(doc, self.retriever, query if query is not None else parent["query"],
                             limit=self.config.view_chars, top_k=self.config.chunk_top_k, offset=offset)
        width = sum(e - s for s, e in proposed["spans"])
        while True:
            view = shrink_view(proposed, width)
            existing = next((v for v in self.observations.values() if v["view_hash"] == view["view_hash"]), None)
            view = existing or {**view, "observation_id": f"o{len(self.observations) + 1}",
                                "created_by_action_id": aid, "search_action_id": search_action_id}
            old_spans = [s for v in self.observations.values() if v["document_hash"] == doc["document_hash"] for s in v["spans"]]
            size = lambda spans: sum(e - s for s, e in merge_spans(spans))
            new_chars = size(old_spans + view["spans"]) - size(old_spans)
            refs = {o for c in self.state["claims"] for o in c["observation_ids"]}
            delta = {"pending_add": [] if view["observation_id"] in refs else [view["observation_id"]], "new_chars": new_chars}
            if docid not in self.documents:
                delta["document"] = doc
            if not existing:
                delta["observation"] = view
            output = {"observation": view, "duplicate_view": bool(existing), "new_observed_chars": new_chars,
                      "retrieval_parent": search_action_id, "purpose": intent}
            probe = {"type": "tool", "action_id": aid, "action": "open_page", "arguments": {"docid": docid},
                     "result": {"ok": True, "action_id": aid, **output}, "delta": delta}
            if not self.admission or self.admission(self._preview(probe)):
                return output, delta
            if width <= 64:
                raise HarnessError("context_capacity", "No admissible observation window; process pending state first")
            width = max(64, width // 2)  # No further retriever call or hidden post-return truncation.

    def _read(self, aid, observation_id=None, directory_cursor=None):
        if (observation_id is None) == (directory_cursor is None):
            raise HarnessError("protocol_error", "Choose observation_id OR directory_cursor")
        if directory_cursor is not None:
            if directory_cursor == "start":
                ids = list(self.observations)
            elif directory_cursor in self.cursors:
                ids = self.cursors[directory_cursor]
            else:
                raise HarnessError("protocol_error", "Use a cursor returned in this episode")
            page, remaining = ids[:self.config.directory_page_size], ids[self.config.directory_page_size:]
            cursor = digest([self.ledger.header, remaining]) if remaining else None
            rows = [{"observation_id": o, "docid": self.observations[o]["docid"],
                     "title": self.documents[self.observations[o]["docid"]]["title"],
                     "spans": self.observations[o]["spans"]} for o in page]
            return {"directory": rows, "next_cursor": cursor}, {"cursors": {cursor: remaining}} if cursor else {}
        if observation_id not in self.observations:
            raise HarnessError("protocol_error", "Unknown observation in this episode")
        refs = {o for c in self.state["claims"] for o in c["observation_ids"]}
        if observation_id not in refs | self.pending and len(self.pending) >= self.config.max_pending_views:
            raise HarnessError("context_capacity", "Pending buffer full; process existing observations before reading an uncited view")
        return {"observation": self.observations[observation_id], "purpose": self._purpose()}, {
            "pending_add": [] if observation_id in refs else [observation_id]}

    def _update(self, aid, **patch):
        result, next_claim, changes, consumed = apply_delta(self.state, patch, next_claim=self.next_claim,
                                                           exposed_ids=self.exposed, observations=self.observations)
        attempt_id = patch.get("attempt_id")
        warnings = []
        for field in ("attempt_note", "attempt_id"):
            if field in patch:
                try:
                    validate(patch[field], self.config.tool_schema("update_state")["properties"][field], "arguments."+field)
                except HarnessError as exc:
                    warnings.append({"path":"arguments."+field, "code":"unlinked_note", "message":str(exc)+"; research delta committed, auxiliary data retained only in action arguments"})
        if warnings:
            attempt_id = None
        if "attempt_note" in patch:
            if attempt_id is None and not warnings:
                focus = self.state["focus"]
                attempt_id = next((sid for sid, s in reversed(list(self.searches.items())) if s["purpose"] and focus
                                   and s["purpose"]["claim_id"] == focus["claim_id"]
                                   and s["purpose"]["candidate_scope"] == candidate_scope(self.state)), None)
            if not warnings and attempt_id not in self.searches:
                warnings.append({"path": "arguments.attempt_id", "code": "unlinked_note",
                                 "message": "Research delta committed; note retained in action arguments but not linked to a search. Supply an existing attempt_id to link it."})
        elif attempt_id is not None:
            warnings.append({"path": "arguments.attempt_note", "code": "unlinked_note",
                             "message": "Research delta committed; attempt_id without a note has no bookkeeping effect."})
        delta = {"state": result, "next_claim": next_claim, "pending_remove": sorted(consumed),
                 "changes": changes, "revision_reason": patch.get("revision_reason", ""),
                 "finding_scopes": {cid: candidate_scope(result) for cid in changes["working_updates"]}}
        if "attempt_note" in patch and not warnings:
            delta["attempt_note"] = {"attempt_id": attempt_id, "text": patch["attempt_note"], "actor_report": True}
        return {"research_version": result["research_version"], "noop": result == self.state,
                "added_claim_ids": changes["added_claim_ids"], "changes": changes, "warnings": warnings}, delta

    def answer_blocker(self):
        """Single source for submit preconditions and policy-visible readiness."""
        if self.pending:
            return ("pending_observations", "Record or dismiss pending observations")
        if not self.state["answer"]:
            return ("protocol_error", "No candidate answer is bound; update_state must bind answer first")
        audit = self.current_audit
        if self.config.audit_mode != "off" and audit is None:
            return ("audit_required", "Audit the current semantic state")
        if self.config.audit_mode == "hard" and audit["status"] != "supported":
            return ("not_supported", "Repair or abstain; hard mode does not rewrite unknown")
        return None

    def readiness(self):
        if self.config.mode == "baseline":
            return {}
        blocker = self.answer_blocker()
        result = {"submit_answer.answer": {"ready": blocker is None, "blocked_reason": blocker},
                  "submit_answer.abstain": {"ready": True},
                  "open_page": {"ready": self.state["focus"] is not None and len(self.pending) < self.config.max_pending_views,
                                "requires": "existing search hit, active focus, pending capacity"},
                  "search": {"ready": True, "requires": "active focus or a valid focus argument"},
                  "read_evidence": {"requires": "directory cursor OR observation ID; raw read requires active focus and pending capacity"}}
        if self.config.audit_mode != "off":
            result["verify_answer"] = {"ready": not self.pending, "cached": self.current_audit is not None,
                                       "use": "Current audit already delivered; change semantic evidence before requesting a new judgment."
                                       if self.current_audit else "Audit a bound candidate or a sourced partial finding; an empty state provides no evidence to audit."}
            if self.config.max_tool_calls > 1:
                offered = not self.pending and self.current_audit is None and (self.state['answer'] is not None or any(c['observation_ids'] for c in self.state['claims']))
                result['verify_answer']['ready'] = bool(offered)
                result['verify_answer']['blocked_reason'] = None if offered else 'Pending evidence, empty state, or current audit already available'
        if self.config.ordered_tool_calls:
            result['ordered_calls'] = 'Readiness above describes current state. A prior successful update in this response can satisfy pending/answer preconditions; a prior successful verification can satisfy the current-audit precondition. Execution checks each action in order.'
        return result

    def _verify(self, aid):
        if self.pending:
            raise HarnessError("pending_observations", "Record findings or dismiss pending views before full audit")
        packet, fp = self.audit_packet(), self.fingerprint()
        if fp in self.audit_cache:
            return {"audit": self.audit_cache[fp], "cached": True}, {"audit": self.audit_cache[fp]}
        refs = sorted({o for c in packet["claims"] for o in c["observation_ids"]})
        report = self.auditor.audit(self.question, deepcopy(packet), [deepcopy(self.observations[o]) for o in refs])
        report = validate_report(report, packet, self.observations)
        scope = candidate_scope(self.state)
        previous = next((a for a in reversed(self.audit_history) if a["scope"] == scope), None)
        reqs = {c["claim_id"]: c["requirement"] for c in packet["claims"]}
        before = {c["claim_id"] for c in previous["report"]["claims"] if c["status"] != "supported"
                  and previous["requirements"].get(c["claim_id"]) == reqs.get(c["claim_id"])} if previous else set()
        repaired = sorted(before & {c["claim_id"] for c in report["claims"] if c["status"] == "supported"})
        audit = {"fingerprint": fp, "scope": scope, "report": report, "status": status(report),
                 "unresolved_ids": unresolved(report), "created_by_action_id": aid,
                 "requirements": reqs, "answer": self.state["answer"]}
        conflicts = {}
        for c in report["claims"]:
            if c["status"] == "contradicted":
                # Retain source witnesses, never trust old rationale as fresh evidence.
                record = {"scope": scope, "claim_id": c["claim_id"], "requirement": reqs[c["claim_id"]],
                          "answer": self.state["answer"], "quotes": deepcopy(c["quotes"])}
                conflicts[digest(record)] = record
        return {"audit": audit, "cached": False, "evidence_repair_ids": repaired}, {"audit": audit, "conflicts": conflicts}

    def available_tools(self):
        """Render a state-valid subset of the single contract; no evidence or verdict changes.

        Direct engine calls retain the full contract, including deterministic audit-cache reads.
        Native policy requests omit actions whose current preconditions cannot be satisfied.
        """
        pending = self.pending if self.config.mode == "esr" else set()
        focus_ok = self.config.mode == "baseline" or self.state["focus"] is not None
        cited = {o for c in self.state["claims"] for o in c["observation_ids"]}
        readable = sorted(o for o in self.observations if focus_ok and
                          (o in cited | pending or len(pending) < self.config.max_pending_views))
        result = []
        for tool in deepcopy(self.config.tools):
            name = tool["name"]
            if name == "open_page" and (not self.searches or not focus_ok or len(pending) >= self.config.max_pending_views):
                continue
            if name == "read_evidence":
                if not readable:
                    tool["parameters"]["properties"].pop("observation_id")
                    tool["parameters"]["required"] = ["directory_cursor"]
                else:
                    # ID schemas are shared in the contract; deepcopy preserves aliases.
                    # Replace this field so its enum cannot constrain unrelated IDs.
                    props=tool['parameters']['properties']
                    props['observation_id']={**props['observation_id'],'enum':readable}
            if not self.config.ordered_tool_calls and name == "verify_answer" and (pending or self.current_audit is not None or
                                              (self.state["answer"] is None and not cited)):
                continue
            if not self.config.ordered_tool_calls and name == "submit_answer" and self.answer_blocker():
                tool["parameters"]["properties"]["decision"]["enum"] = ["abstain"]
                tool["parameters"]["required"] = ["decision"]
            result.append(tool)
        return result

    def _submit(self, aid, decision="answer", reason=""):
        if decision == "abstain":
            terminal = {"outcome": "abstained", "answer": "", "final_draft": self.state["answer"],
                        "evidence_status": "unverified", "reason": reason}
        else:
            blocker = self.answer_blocker()
            if blocker:
                raise HarnessError(*blocker)
            audit = self.current_audit
            terminal = {"outcome": "submitted", "answer": self.state["answer"], "final_draft": self.state["answer"],
                        "evidence_status": audit["status"] if audit else "unverified",
                        "unresolved_ids": audit["unresolved_ids"] if audit else [],
                        "audit_fingerprint": audit["fingerprint"] if audit else None}
        return {"terminal": terminal}, {"terminal": terminal}

    def _finish(self, aid, answer):
        terminal = {"outcome": "submitted", "answer": answer.strip(), "final_draft": answer.strip(), "evidence_status": "unverified"}
        return {"terminal": terminal}, {"terminal": terminal}

    def end(self, reason):
        if self.readonly:
            raise RuntimeError("Replay is read-only")
        if reason not in {"budget_exhausted", "generation_budget_exhausted", "context_overflow", "service_error",
                          'request_budget_exhausted','execution_error_limit'}:
            raise ValueError("Unknown termination reason")
        if self.terminal is None:
            audit = self.current_audit
            terminal = {"outcome": reason, "answer": "", "final_draft": self.state["answer"],
                        "evidence_status": audit["status"] if audit else "unverified"}
            self._commit({"type": "end", "terminal": terminal})
        return deepcopy(self.terminal)

    def context(self, recent_limit=None):
        from .context import workcard
        return workcard(self, recent_limit)
