"""Operational observation ledger + sparse, explicitly fallible research state.

Only acknowledged (or prospectively present in the actual next input) receipts
advance observation counters. Rendering is pure. No online LLM/verifier is used.
"""
from __future__ import annotations

from copy import deepcopy

from .contract import ContractError, digest, loads
from .workflow_contract import WorkflowConfig


def query_key(harness, query: str, top_k: int) -> str:
    return digest([harness.retriever.identity, query, top_k])


def result_key(hits: list[dict]) -> str:
    return digest([{k: h[k] for k in ("ref", "title", "snippet")} for h in hits])


class WorkflowState:
    def __init__(self, options: WorkflowConfig):
        self.options = options
        self.groups_seen: set[int] = set()
        self.observations: dict[str, dict] = {}
        self.hit_content: set[str] = set()
        self.raw_seen: set[str] = set()
        self.last_new_navigation: int | None = None
        self.last_new_raw: int | None = None
        self.stall_rounds = 0
        self.recovery_used = 0
        self.recovery_started = False
        self.gap: dict | None = None
        self.gap_history: list[dict] = []

    def record(self, query: str, fingerprint: str) -> dict | None:
        return self.observations.get(digest([query, fingerprint]))

    def stage(self) -> str:
        o = self.options
        if o.repetition == "off":
            return "normal"
        if self.stall_rounds < o.repeat_threshold and not self.recovery_started:
            return "normal"
        if o.repetition == "observe":
            return "warning"
        return "final" if self.recovery_used >= o.recovery_rounds else "recover"

    def complete_decision(self, stage: str) -> None:
        if self.options.repetition == "bounded" and stage == "recover":
            self.recovery_started = True
            self.recovery_used += 1

    def ack(self, groups: list[dict], visible: list[str]) -> None:
        for group in groups:
            r = group["round"]
            if r in self.groups_seen:
                continue
            self.groups_seen.add(r)
            new_raw = set(group["evidence"]) & set(visible) - self.raw_seen
            self.raw_seen.update(new_raw)
            if new_raw:
                self.last_new_raw = r
            native = group["messages"][0].get("tool_calls", [])
            names = {c["id"]: c["function"]["name"] for c in native}
            all_repeats, saw_search, new_hit = True, False, False
            for message in group["messages"]:
                if message["role"] != "tool":
                    continue
                result = loads(message["content"])
                name = names.get(message.get("tool_call_id"))
                if name != "search":
                    continue
                saw_search = True
                if not result.get("ok"):
                    all_repeats &= result.get("code") == "duplicate_query_blocked"
                    continue
                for batch in result.get("results", []):
                    meta = batch.get("observation")
                    if meta is None:
                        all_repeats = False
                        continue
                    q, fp = meta["query_key"], meta["result_fingerprint"]
                    old = self.record(q, fp)
                    all_repeats &= old is not None
                    if batch.get("view") != "reuse":
                        for hit in batch["hits"]:
                            identity = digest([hit["ref"], hit["title"], hit["snippet"]])
                            if identity not in self.hit_content:
                                new_hit = True
                                self.hit_content.add(identity)
                    self.observations[digest([q, fp])] = {"query_key": q, "fingerprint": fp,
                        "count": 1 if old is None else old["count"] + 1,
                        "first_round": r if old is None else old["first_round"], "last_round": r,
                        "refs": [h["ref"] for h in batch["hits"]]}
            if new_hit:
                self.last_new_navigation = r
            if new_raw or new_hit or (saw_search and not all_repeats):
                self.stall_rounds = 0
                self.recovery_used = 0
                self.recovery_started = False
            elif saw_search and all_repeats:
                self.stall_rounds += 1
        self.raw_seen.update(visible)

    def project(self, groups: list[dict], visible: list[str]) -> "WorkflowState":
        copied = deepcopy(self)
        copied.ack(groups, visible)
        return copied

    def scope(self, harness, groups=None, visible=None) -> dict:
        refs = [] if self.gap is None else self.gap["navigation_refs"]
        latest = {h["ref"]: h for h in harness.navigation_history}
        available = set(harness.published_docs)
        available_e = set(harness.exposed) | set(visible or [])
        for group in groups or []:
            available.update(group["documents"])
            for message in group["messages"]:
                if message["role"] != "tool":
                    continue
                result = loads(message["content"])
                if not result.get("ok"):
                    continue
                for batch in result.get("results", []):
                    if batch.get("view") != "reuse":
                        for hit in batch["hits"]:
                            latest[hit["ref"]] = hit
        order = list(dict.fromkeys([*refs, *reversed(list(latest))]))[:8]
        pages = []
        for ref in order:
            if ref not in available:
                continue
            hit = latest.get(ref, {})
            ranges = [harness.archive.evidence(e) for e in sorted(available_e, key=lambda e: int(e[1:]))
                      if harness.archive.evidence(e)["document"] == ref]
            pages.append({"ref": ref, "title": harness.archive.doc(ref)["title"][:160],
                "snippet": hit.get("snippet", "")[:160], "navigation_seen": True,
                "raw_ranges_delivered": [{"ref": v["ref"], "start": v["start"], "end": v["end"]} for v in ranges[-4:]],
                "read_action": {"ref": ref}})
        return {"contract": self.options.identity(), "stage": self.stage(),
            "consecutive_repeat_rounds": self.stall_rounds, "recovery_decisions_used": self.recovery_used,
            "last_new_navigation_source_round": self.last_new_navigation,
            "last_new_raw_source_round": self.last_new_raw,
            "active_gap_not_verified": deepcopy(self.gap),
            "previous_gap_judgments_not_verified": deepcopy(self.gap_history),
            "available_pages_not_ranked_for_relevance": pages,
            "instruction": ("Only finish now: bounded recovery produced no new observation. Submit using already delivered evidence or explicitly abstain."
                if self.stage() == "final" else
                "Repeated searches returned no new observation. Read an existing candidate, change the query, recover a source, or finish. During bounded recovery identical cached queries are blocked unless replay=true explicitly restores navigation."
                if self.stage() == "recover" else
                "Use the current missing relation to choose a real next action. Page-name search is not page reading; cached is not proof of progress.")}

    def update_gap(self, harness, args: dict, binding: dict) -> dict:
        for ref in args["navigation_refs"]:
            harness._allowed(ref, binding["documents"], "Gap navigation")
        for ref in args["evidence_refs"]:
            harness._allowed(ref, binding["evidence"], "Gap evidence")
        if args["status"] != "open" and not args["evidence_refs"]:
            raise ContractError("gap_basis", "A supported/rejected/conflict judgment requires delivered evidence; keep untested hypotheses open")
        prior = None if self.gap is None else {k: self.gap[k] for k in args}
        changed = prior != args
        if changed:
            if self.gap:
                self.gap_history = [*self.gap_history, deepcopy(self.gap)][-4:]
            revision = 1 if self.gap is None else self.gap["revision"] + 1
            self.gap = {**deepcopy(args), "revision": revision, "kind_of_record": "agent_judgment_not_verified",
                        "updated_round": harness.model_calls}
            harness.archive.append("gap_update", {"round": harness.model_calls,
                "object": harness.archive.put_json(self.gap), "history": harness.archive.put_json(self.gap_history)})
        return {"changed": changed, "current": deepcopy(self.gap), "semantic_status": "not_automatically_verified"}


def navigation_result(harness, query: str, top_k: int, hits: list[dict], *, replay: bool) -> dict:
    w = harness.workflow
    key, fingerprint = query_key(harness, query, top_k), result_key(hits)
    old = w.record(key, fingerprint)
    compact = bool(w.options.reuse_results and old and not replay)
    rows = deepcopy(hits)
    for hit in rows:
        ref = hit["ref"]
        ranges = [harness.archive.evidence(e) for e in harness.evidence_order
                  if harness.archive.evidence(e)["document"] == ref]
        hit.update(navigation_seen=ref in harness.published_docs,
                   raw_ranges_delivered=[{"ref": v["ref"], "start": v["start"], "end": v["end"]} for v in ranges[-4:]],
                   read_action={"ref": ref})
        if compact:
            hit["snippet"] = ""
    return {"hits": rows, "view": "reuse" if compact else "full",
            "observation": {"query_key": key, "result_fingerprint": fingerprint,
                "prior_deliveries": 0 if old is None else old["count"],
                "first_delivered_source_round": None if old is None else old["first_round"],
                "replay_requested": replay, "semantic_progress": "not_measured"},
            "next_step": "Open a received ref with read; use replay=true to restore full cached navigation."
                         if compact else "Inspect navigation; read a relevant page or change the locating clue."}


def check_search_recovery(harness, args: dict) -> None:
    w = harness.workflow
    if w.stage() != "recover" or args.get("replay", False):
        return
    keys = [query_key(harness, q, args.get("top_k", 5)) for q in args["queries"]]
    known = {v["query_key"] for v in w.observations.values()}
    if keys and all(k in known for k in keys):
        raise ContractError("duplicate_query_blocked", "Repeated received queries in bounded recovery: read a candidate, change the query, or explicitly replay the cached view. No backend call executed.")
