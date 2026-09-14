"""Frozen, question-only paired experiments; no built-in answer oracle or reward model."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path
import random
from typing import Callable

from .archive import Archive
from .contract import PROTOCOL, Config, ContractError, canonical, digest, loads
from .engine import Harness

ALLOWED_ABLATIONS = {"notes_enabled", "reserve_finish", "context_mode", "max_batch", "max_queries_per_search",
                     "nonblocking_notes", "repair_context", "delivery_preflight"}
INFRASTRUCTURE_FAILURES = {
    "http_error", "transport_error", "model_transport", "backend_failure", "retrieval_protocol",
    "incomplete_response", "response_envelope", "model_identity_changed", "implementation_error",
    "network_not_authorized", "archive_integrity", "redirect_refused", "provider_output_overrun",
    "response_size", "document_size", "counter_error",
}


def source_hashes() -> dict:
    root = Path(__file__).parent
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob("*.py"))}


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as f:
        f.write(canonical(value) + "\n")


def read_cases(path) -> list[dict]:
    rows = [loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    validate_cases(rows)
    return rows


def validate_cases(cases):
    if not cases:
        raise ValueError("A nonempty question-only case list is required")
    ids = set()
    for c in cases:
        if (not isinstance(c, dict) or set(c) != {"id", "question"}
                or not all(isinstance(v, str) and v.strip() for v in c.values()) or c["id"] in ids):
            raise ValueError("Each case must contain exactly unique id and question; labels/gold are forbidden")
        ids.add(c["id"])


def make_plan(cases: list[dict], config: Config, arms: dict, *, model_identity: dict,
              retriever_identity: dict, counter_identity: dict, seed: int = 0, repeats: int = 1) -> dict:
    validate_cases(cases)
    if type(repeats) is not int or not 1 <= repeats <= 10 or type(seed) is not int:
        raise ValueError("Bounded repeats and integer seed required")
    if not isinstance(arms, dict) or not 2 <= len(arms) <= 4:
        raise ValueError("Specify two to four named arms")
    configs = {}
    for name, delta in arms.items():
        if (not isinstance(name, str) or not name or len(name) > 80
                or not isinstance(delta, dict) or not set(delta) <= ALLOWED_ABLATIONS):
            raise ValueError("Only predeclared harness ablations may differ between arms")
        configs[name] = replace(config, **delta).to_dict()
    rng, schedule = random.Random(seed), []
    for case in cases:
        for rep in range(repeats):
            order = list(arms)
            rng.shuffle(order)
            for arm in order:
                schedule.append({"slot": f"{len(schedule):04d}", "case_id": case["id"],
                                 "question_sha256": digest(case["question"]), "repeat": rep, "arm": arm})
    plan = {"protocol": PROTOCOL, "cases": deepcopy(cases), "configs": configs, "schedule": schedule,
            "seed": seed, "repeats": repeats, "model": deepcopy(model_identity),
            "retriever": deepcopy(retriever_identity), "counter": deepcopy(counter_identity),
            "source_hashes": source_hashes(), "judge": "external_post_run_only",
            "maximum_model_attempts": sum(configs[s["arm"]]["max_model_calls"] for s in schedule),
            "scope": "Pairing is by case/repeat; identical corpus, model, counter and non-ablation budgets",
            "stop_rule": "First infrastructure/integrity failure stops the queue; task budget failures do not"}
    return {"sha256": digest(plan), "plan": plan}


def checked_plan(wrapper):
    if not isinstance(wrapper, dict) or set(wrapper) != {"sha256", "plan"} or digest(wrapper["plan"]) != wrapper["sha256"]:
        raise ContractError("plan_integrity", "Frozen plan hash mismatch")
    plan = wrapper["plan"]
    if plan["protocol"] != PROTOCOL:
        raise ContractError("plan_protocol", "Plan protocol mismatch")
    validate_cases(plan["cases"])
    return plan


def run_plan(wrapper, output, model_factory: Callable, retriever_factory: Callable,
             counter_factory: Callable, *, max_total_model_calls: int):
    plan = checked_plan(wrapper)
    if type(max_total_model_calls) is not int or max_total_model_calls < plan["maximum_model_attempts"]:
        raise ValueError("Explicit total authorization must cover the entire frozen worst-case schedule")
    if source_hashes() != plan["source_hashes"]:
        raise ContractError("source_changed", "Source changed after freezing; create a new experiment, not a silent patch")
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    write_new(root / "plan.json", wrapper)
    cases = {c["id"]: c["question"] for c in plan["cases"]}
    total = 0
    for slot in plan["schedule"]:
        if source_hashes() != plan["source_hashes"]:
            write_new(root / "queue_stop.json", {"slot": slot["slot"], "reason": "source_changed"})
            break
        model, retriever, counter = model_factory(), retriever_factory(), counter_factory()
        if model.identity != plan["model"] or retriever.identity != plan["retriever"] or counter.identity != plan["counter"]:
            write_new(root / "queue_stop.json", {"slot": slot["slot"], "reason": "identity_mismatch"})
            break
        config = Config(**plan["configs"][slot["arm"]])
        if total + config.max_model_calls > max_total_model_calls:
            raise ContractError("global_budget", "Insufficient reserved global budget")
        h = Harness(cases[slot["case_id"]], retriever, path=root / f"{slot['slot']}.sqlite", config=config, counter=counter)
        try:
            try:
                h.run(model)
            except Exception as exc:
                # Harness has recorded implementation_error; persist the full roster before stopping.
                if h.terminal is None:
                    h._end("implementation_error", exception_type=type(exc).__name__)
            report = h.archive.report()
            total += report["model_attempts"]
            write_new(root / f"{slot['slot']}.result.json", {"head": report["head"], "terminal": h.terminal})
        finally:
            h.close()
        if report["terminal"]["outcome"] in INFRASTRUCTURE_FAILURES:
            write_new(root / "queue_stop.json", {"slot": slot["slot"], "reason": report["terminal"]["outcome"]})
            break
    result = summarize(root)
    write_new(root / "summary.json", result)
    return result


def summarize(output, *, judgments: list[dict] | None = None) -> dict:
    root = Path(output)
    wrapper = loads((root / "plan.json").read_text(encoding="utf-8"))
    plan = checked_plan(wrapper)
    labels = {}
    for j in judgments or []:
        if (not isinstance(j, dict) or set(j) != {"slot", "head", "correct"}
                or type(j["correct"]) is not bool or j["slot"] in labels):
            raise ValueError("External judgments require unique slot/head/correct; no answer keys enter policy")
        labels[j["slot"]] = j
    rows = []
    for slot in plan["schedule"]:
        row = {**slot, "status": "NOT_RUN", "formal_correct": None}
        path = root / f"{slot['slot']}.sqlite"
        if path.exists():
            archive = Archive(path, readonly=True)
            try:
                report = archive.report()
            finally:
                archive.close()
            header = report["header"]
            if (digest(header["question"]) != slot["question_sha256"] or header["config"] != plan["configs"][slot["arm"]]
                    or header["retriever"] != plan["retriever"] or header["counter"] != plan["counter"]
                    or report.get("model_identity") != plan["model"]):
                raise ContractError("cohort_mismatch", "Episode differs from its frozen case, arm or identity")
            status = report["terminal"]["outcome"]
            label = labels.pop(slot["slot"], None)
            if label and (label["head"] != report["head"] or status != "submitted"):
                raise ContractError("judge_mismatch", "Judgment must match a completed submitted ledger head")
            row.update(status=status, formal_correct=(label["correct"] if label else None) if status == "submitted" else False,
                ledger_head=report["head"], model_attempts=report["model_attempts"], backend_attempts=report["backend_attempts"],
                actions_recorded=report["actions_recorded"], usage_known=report["usage_known"],
                unknown_usage_calls=report["unknown_usage_calls"], elapsed_seconds=report["terminal"].get("elapsed_seconds"))
        rows.append(row)
    if labels:
        raise ContractError("judge_mismatch", "Judgments for unrun or unknown slots are not allowed")
    arms = {}
    for arm in plan["configs"]:
        group = [r for r in rows if r["arm"] == arm]
        scored = all(r["formal_correct"] is not None for r in group)
        arms[arm] = {"planned": len(group), "status_counts": dict(Counter(r["status"] for r in group)),
            "formal_accuracy": sum(r["formal_correct"] for r in group) / len(group) if scored else None,
            "model_attempts": sum(r.get("model_attempts", 0) for r in group),
            "backend_attempts": sum(r.get("backend_attempts", 0) for r in group),
            "unknown_usage_calls": sum(r.get("unknown_usage_calls", 0) for r in group)}
    return {"plan_sha256": wrapper["sha256"], "rows": rows, "arms": arms,
            "limitations": ["No built-in semantic judge", "NOT_RUN stays in the planned roster",
                            "Ablations are not automatically named non-ESR baseline", "Partial cohorts have no full-cohort accuracy"]}
