"""A small deterministic forward state machine; models decide semantics, not invariants."""
from __future__ import annotations

from copy import deepcopy
import time
from typing import Any

from .audit import Auditor, status, unresolved, validate_report
from .ledger import Ledger
from .protocol import Config, HarnessError, SCHEMAS, VERSION, digest, validate
from .views import Retriever, document, hit, make_view, merge_spans


class Harness:
    def __init__(self, question: str, retriever: Retriever, auditor: Auditor | None = None,
                 *, config: Config | None = None, ledger: Ledger | None = None, manifest: dict | None = None):
        if not question.strip():
            raise ValueError("question must be nonempty")
        self.question, self.retriever, self.auditor = question.strip(), retriever, auditor
        self.config, self.ledger = config or Config(), ledger or Ledger()
        if self.config.mode == "esr" and self.config.audit_mode != "off" and auditor is None:
            raise ValueError("hard/soft modes require an auditor")
        self.ledger.initialize({"schema_version": 2, "implementation": VERSION,
                                "question": self.question, "config": self.config.to_dict(),
                                "auditor": auditor.identity if auditor else None,
                                "retriever": getattr(retriever, "identity", {"type": type(retriever).__name__}),
                                "manifest": manifest or {}})
        self.documents: dict[str, dict] = {}
        self.observations: dict[str, dict] = {}
        self.searches: dict[str, dict] = {}
        self.audit_cache: dict[str, dict] = {}
        self.state = {"research_version": 0, "target": self.question, "answer": "",
                      "answer_kind": "answer", "claims": []}
        self.last_audit: dict | None = None
        self.terminal: dict | None = None
        self.pending: set[str] = set()
        self.actions: list[dict] = []
        self.stagnant_actions = 0
        self.readonly = False
        for event in self.ledger.events():
            self._apply(event)

    def _apply(self, event: dict) -> None:
        if event["type"] == "end":
            self.terminal = event["terminal"]
        if event["type"] != "tool":
            return
        self.actions.append(event)
        delta = event["delta"]
        self.stagnant_actions = 0 if delta.get("new_chars", 0) else self.stagnant_actions + 1
        if "document" in delta:
            doc = delta["document"]
            self.documents[doc["docid"]] = doc
        if "search" in delta:
            self.searches[event["action_id"]] = delta["search"]
        if "observation" in delta:
            view = delta["observation"]
            self.observations[view["observation_id"]] = view
        self.pending.difference_update(delta.get("pending_remove", []))
        self.pending.update(delta.get("pending_add", []))
        if "state" in delta:
            self.state = delta["state"]
        if "audit" in delta:
            audit = delta["audit"]
            self.last_audit = audit
            self.audit_cache[audit["fingerprint"]] = audit
        if "terminal" in delta:
            self.terminal = delta["terminal"]

    @property
    def attempts(self) -> int:
        return len(self.actions)

    def fingerprint(self, state: dict | None = None) -> str:
        state = self.state if state is None else state
        logical = {key: value for key, value in state.items() if key != "research_version"}
        views = sorted({oid for c in state["claims"] for oid in c["observation_ids"]})
        return digest({"question": self.question, "state": logical,
                       "views": [(oid, self.observations[oid]["view_hash"]) for oid in views],
                       "auditor": self.auditor.identity if self.auditor else None})

    @property
    def current_audit(self) -> dict | None:
        return deepcopy(self.audit_cache.get(self.fingerprint()))

    def execute(self, name: str, arguments: dict | None = None) -> dict:
        """Every attempted action consumes one action unit. Invalid actions never mutate state.

        External generation/retrieval can fail; that yields a classified event, not a gap.
        Transitions are computed first, durably appended, THEN applied in memory.
        """
        if self.readonly:
            raise RuntimeError("Replay is read-only")
        arguments = {} if arguments is None else deepcopy(arguments)
        if self.terminal is not None:
            return {"ok": False, "error_code": "episode_finished", "error": "Episode is already terminal"}
        if self.attempts >= self.config.max_actions:
            self.end("budget_exhausted")
            return {"ok": False, "error_code": "budget_exhausted", "error": "Action budget exhausted"}
        aid = f"a{self.attempts + 1}"
        start = time.monotonic()
        delta: dict[str, Any] = {}
        try:
            allowed = {t["name"] for t in self.config.tools}
            if name not in allowed:
                raise HarnessError("protocol_error", f"Action is not available in {self.config.mode}: {name}")
            validate(arguments, SCHEMAS[name])
            methods = {"search": self._search, "open_page": self._open,
                       "read_evidence": self._read, "update_state": self._update,
                       "verify_answer": self._verify, "submit_answer": self._submit, "finish": self._finish}
            output, delta = methods[name](aid, **arguments)
            result = {"ok": True, "action_id": aid, **output}
        except HarnessError as exc:
            result = {"ok": False, "action_id": aid, "error_code": exc.code, "error": str(exc)}
        if self.config.mode == "baseline":
            delta["pending_remove"] = sorted(self.pending)
        event = {"type": "tool", "action_id": aid, "action": name, "arguments": arguments,
                 "result": result, "delta": delta, "elapsed_seconds": time.monotonic() - start}
        self.ledger.append(event)
        self._apply(event)
        return deepcopy(result)

    def record_protocol_error(self, message: str) -> dict:
        # Uses the same budget/accounting path as unknown tool names.
        return self.execute("invalid_model_response", {"error": message[:2000]})

    def _search(self, aid: str, query: str, top_k: int | None = None):
        query = query.strip()
        rows = self.retriever.search(query, top_k or self.config.search_top_k)
        if not isinstance(rows, list):
            raise HarnessError("retrieval_error", "Search result must be a list")
        hits = [hit(row) for row in rows[:top_k or self.config.search_top_k]]
        repeated = any(s["query"] == query for s in self.searches.values())
        search = {"query": query, "hits": hits}
        return {"results": hits, "repeated_query": repeated}, {"search": search}

    def _open(self, aid: str, docid: str, search_action_id: str, query: str | None = None,
              offset: int | None = None):
        parent = self.searches.get(search_action_id)
        if parent is None or docid not in {h["docid"] for h in parent["hits"]}:
            raise HarnessError("protocol_error", "docid must belong to the referenced successful search")
        doc = self.documents.get(docid)
        delta: dict = {}
        if doc is None:
            doc = document(self.retriever.get_document(docid), docid)
            delta["document"] = doc
        proposed = make_view(doc, self.retriever, query or parent["query"], limit=self.config.view_chars,
                             top_k=self.config.chunk_top_k, offset=offset)
        existing = next((v for v in self.observations.values() if v["view_hash"] == proposed["view_hash"]), None)
        if existing:
            view, new_chars = existing, 0
        else:
            oid = f"o{len(self.observations) + 1}"
            view = {**proposed, "observation_id": oid, "created_by_action_id": aid,
                    "search_action_id": search_action_id}
            previous = [s for v in self.observations.values() if v["document_hash"] == doc["document_hash"] for s in v["spans"]]
            old_size = sum(e - s for s, e in merge_spans(previous))
            new_size = sum(e - s for s, e in merge_spans(previous + view["spans"]))
            new_chars = new_size - old_size
            delta["observation"] = view
        referenced = {o for c in self.state["claims"] for o in c["observation_ids"]}
        delta.update({"new_chars": new_chars, "pending_add": [] if view["observation_id"] in referenced else [view["observation_id"]]})
        return {"observation": view, "duplicate_view": existing is not None, "new_observed_chars": new_chars}, delta

    def _read(self, aid: str, observation_id: str):
        if observation_id not in self.observations:
            raise HarnessError("protocol_error", "Unknown observation_id in this episode")
        # No retriever invocation, no indexing/finding prerequisite, no query-dependent reconstruction.
        referenced = {o for c in self.state["claims"] for o in c["observation_ids"]}
        return {"observation": self.observations[observation_id]}, {"pending_add": [] if observation_id in referenced else [observation_id]}

    def _update(self, aid: str, answer: str, answer_kind: str, target: str, claims: list,
                revision_reason: str = "", dismiss_observation_ids: list | None = None):
        answer, target = answer.strip(), " ".join(target.split())
        if answer_kind == "abstain" and answer:
            raise HarnessError("protocol_error", "abstain requires an empty answer; do not put refusal text in answer")
        ids = [c["claim_id"] for c in claims]
        if len(set(ids)) != len(ids) or any(i.startswith("@") for i in ids):
            raise HarnessError("protocol_error", "claim_ids must be unique and cannot start with @")
        normalized = sorted([{"claim_id": c["claim_id"], "requirement": " ".join(c["requirement"].split()),
                              "observation_ids": sorted(c["observation_ids"])} for c in claims], key=lambda c: c["claim_id"])
        referenced = {oid for c in normalized for oid in c["observation_ids"]}
        dismissed = set(dismiss_observation_ids or [])
        if not (referenced | dismissed) <= set(self.observations):
            raise HarnessError("protocol_error", "State references an observation never returned in this episode")
        if referenced & dismissed:
            raise HarnessError("protocol_error", "Cannot cite and dismiss the same observation")
        old_requirements = {c["claim_id"]: c["requirement"] for c in self.state["claims"]}
        new_requirements = {c["claim_id"]: c["requirement"] for c in normalized}
        requirements_changed = old_requirements != new_requirements or target != self.state["target"]
        if self.state["research_version"] and requirements_changed and not revision_reason.strip():
            raise HarnessError("protocol_error", "Changing target/requirements requires an explicit revision_reason")
        candidate = {"research_version": self.state["research_version"], "answer": answer,
                     "answer_kind": answer_kind, "target": target, "claims": normalized}
        changed = candidate != self.state or self.state["research_version"] == 0
        if changed or self.state["research_version"] == 0:
            candidate["research_version"] += 1
        delta = {"state": candidate, "pending_remove": sorted(referenced | dismissed),
                 "removed_claim_ids": sorted(set(old_requirements) - set(new_requirements)),
                 "requirements_revision_reason": revision_reason}
        # No-op preserves audit fingerprint and research_version; metadata-only consumption is legal.
        return {"state": candidate, "noop": not changed, "audit_invalidated": changed}, delta

    def _verify(self, aid: str):
        if self.config.audit_mode == "off":
            raise HarnessError("protocol_error", "Auditing is disabled in this experiment")
        if not self.state["answer"] or self.state["answer_kind"] != "answer" or not self.state["claims"]:
            raise HarnessError("protocol_error", "Audit needs an answer and explicit requirements")
        if self.pending:
            raise HarnessError("pending_observations", "Cite or explicitly dismiss pending observations before auditing")
        fingerprint = self.fingerprint()
        cached = self.audit_cache.get(fingerprint)
        if cached:
            return {"audit": cached, "cached": True}, {"audit": cached}
        refs = sorted({oid for c in self.state["claims"] for oid in c["observation_ids"]})
        assert self.auditor is not None
        report = deepcopy(self.auditor.audit(self.question, deepcopy(self.state), [deepcopy(self.observations[o]) for o in refs]))
        report = validate_report(report, self.state, self.observations)
        previous = self.last_audit["report"] if self.last_audit else None
        # A reworded 'unknown' never resolves a claim. Removing a claim never resolves it either.
        old_req = self.last_audit.get("requirements", {}) if self.last_audit else {}
        new_req = {c["claim_id"]: c["requirement"] for c in self.state["claims"]}
        before = {c["claim_id"] for c in previous["claims"]
                  if c["status"] != "supported" and old_req.get(c["claim_id"]) == new_req.get(c["claim_id"])} if previous else set()
        after = {c["claim_id"] for c in report["claims"] if c["status"] == "supported"}
        audit = {"fingerprint": fingerprint, "report": report, "status": status(report),
                 "unresolved_ids": unresolved(report), "research_version": self.state["research_version"],
                 "created_by_action_id": aid, "requirements": new_req}
        return {"audit": audit, "cached": False, "resolved_claim_ids": sorted(before & after)}, {"audit": audit}

    def _submit(self, aid: str):
        if not self.state["research_version"]:
            raise HarnessError("protocol_error", "No state has been written")
        if self.state["answer_kind"] == "abstain":
            terminal = {"outcome": "abstained", "answer": "", "evidence_status": "unverified"}
        else:
            if self.pending:
                raise HarnessError("pending_observations", "Cite or dismiss pending observations before submitting")
            if not self.state["answer"] or not self.state["claims"]:
                raise HarnessError("protocol_error", "Submission requires a nonempty answer and requirements")
            audit = self.current_audit
            if self.config.audit_mode != "off" and audit is None:
                raise HarnessError("audit_required", "Audit the current state before submitting")
            if self.config.audit_mode == "hard" and audit["status"] != "supported":
                raise HarnessError("not_supported", "Current audit is not supported; repair, revise candidate, or abstain")
            terminal = {"outcome": "submitted", "answer": self.state["answer"],
                        "evidence_status": audit["status"] if audit else "unverified",
                        "audit_fingerprint": audit["fingerprint"] if audit else None}
        return {"terminal": terminal}, {"terminal": terminal}

    def _finish(self, aid: str, answer: str):
        terminal = {"outcome": "submitted", "answer": answer.strip(), "evidence_status": "unverified"}
        return {"terminal": terminal}, {"terminal": terminal}

    def end(self, reason: str) -> dict:
        if self.readonly:
            raise RuntimeError("Replay is read-only")
        if reason not in {"budget_exhausted", "context_overflow", "service_error", "generation_budget_exhausted"}:
            raise ValueError("Unknown termination reason")
        if self.terminal is None:
            terminal = {"outcome": reason, "answer": "", "evidence_status": "unverified"}
            event = {"type": "end", "terminal": terminal}
            self.ledger.append(event)
            self._apply(event)
        return deepcopy(self.terminal)

    def context(self, recent_limit: int | None = None) -> dict:
        """Recent history may shrink, but pending actual observations never disappear."""
        limit = self.config.recent_actions if recent_limit is None else recent_limit
        recent = self.actions[-limit:] if limit else []
        directory = [{k: v[k] for k in ("observation_id", "docid", "spans", "view_hash")} for v in self.observations.values()]
        current = self.current_audit
        guidance = []
        if self.pending and self.config.mode == "esr":
            guidance.append("Consume useful pending views in claims or explicitly dismiss irrelevant views in update_state.")
        if self.stagnant_actions >= self.config.stagnant_after:
            guidance.append("No new raw-text spans recently. Inspect another requirement, seek counterevidence, change candidate, or finish; changing query wording alone is not progress.")
        if self.last_audit and self.last_audit["status"] != "supported":
            guidance.append("Unknown means missing evidence; contradicted means conflict. Repair by stable claim_id, not by rewording a gap.")
        return deepcopy({"question": self.question, "mode": self.config.mode, "audit_mode": self.config.audit_mode,
                         "state": self.state, "audit": current or self.last_audit,
                         "audit_stale": bool(self.last_audit and not current),
                         "observation_directory": directory,
                         "pending_observations": [self.observations[o] for o in sorted(self.pending)],
                         "recent_actions": [{"action": a["action"], "arguments": a["arguments"], "result": a["result"]} for a in recent],
                         "remaining_actions": self.config.max_actions - self.attempts,
                         "actions_since_new_spans": self.stagnant_actions, "guidance": guidance})
