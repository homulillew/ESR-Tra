#!/usr/bin/env python
"""Stage-0 long-chain: Lanz (Anthropic Messages, :18080) as BOTH policy AND verifier.

The refactor `run`/`episode` ducks-type on a policy object with `fits(messages)`+`complete(messages,purpose)`
and an Auditor with `identity`+`audit(question,state,views)`. Lanz has no OpenAI /chat/completions, so we
bypass the CLI and drive `run()` with Lanz-backed policy and auditor. Each qid/arm gets a unique shared
UsageBudget + fresh ledger (schema 3). Auditor keeps a fresh context per call (stateless via lanz.raw).
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
import hashlib
import importlib.util

RUN = "/data1/ESR-Tra/traces/experiments/refactor_v21_forward"
REFACTOR = "/data1/ESR-Tra/ESR-Tra-refactor-esr-state-2.1"
sys.path.insert(0, os.path.join(REFACTOR, "src"))

# /api is a plain dir (no package); load lanz_client.py as a module directly.
_lanz_spec = importlib.util.spec_from_file_location(
    "lanz_client", os.path.join(REFACTOR, "api", "lanz_client.py"))
lanz_client_mod = importlib.util.module_from_spec(_lanz_spec)
_lanz_spec.loader.exec_module(lanz_client_mod)
LanzClient = lanz_client_mod.LanzClient

from esr_harness.engine import Harness  # noqa: E402
from esr_harness.ledger import Ledger  # noqa: E402
from esr_harness.protocol import Config, HarnessError, canonical, digest, parse_object  # noqa: E402
from esr_harness.prompts import POLICY_PROMPT_VERSION, policy_system, AUDIT_SYSTEM, AUDIT_PROMPT_VERSION  # noqa: E402
from esr_harness.audit import validate_report, AUDIT_SCHEMA  # noqa: E402
from esr_harness.views import EchoRetriever  # noqa: E402
from esr_harness.runner import run, summary  # noqa: E402
from esr_harness.context import visible_ids  # noqa: E402

# Exact allowed fields per tool (2.1 delta contract), so Lanz stops emitting v2-style full-state
# rewrites (claims/answer_kind) or invalid extras. Rendered into the policy prompt.
_TOOL_SCHEMA_HINT = canonical(Config(mode="esr", audit_mode="off").tools)


class _LanzBudget:
    """Duck-typed budget so run() can call budget.summary(). We don't chase exact completion accounting;
    we record usage as unknown (charged conservatively) and never block policy."""

    def __init__(self, limit=24000):
        self.limit = limit
        self.charged_tokens = 0
        self.unknown_usage_requests = 0

    @property
    def remaining(self):
        return max(0, self.limit - self.charged_tokens)

    def summary(self):
        return {"completion_budget": self.limit, "charged_completion_tokens": self.charged_tokens,
                "remaining_completion_tokens": self.remaining,
                "unknown_usage_requests": self.unknown_usage_requests, "usage_complete": False}


class LanzPolicy:
    """Policy role: search/analysis via Lanz; returns the JSON tool-action string."""

    def __init__(self, lanz: LanzClient, budget):
        self.lanz, self.budget = lanz, budget
        self.identity = {"kind": "lanz_strong_policy", "model": lanz.model, "base_url": lanz.base_url}

    def fits(self, messages):
        return True  # Strong remote agent reads full context; no local truncation decision.

    @staticmethod
    def _extract_action(text):
        """Lenient recovery: if strict parse_object fails, pull the first balanced JSON object
        out of prose/fenced output. Returns the bare JSON object STRING (runner calls parse_object
        on it). Mirrors the earlier Strong-bridge fix; validation beyond parsing stays strict."""
        text = str(text).strip()
        try:
            parse_object(text)
            return text  # already a bare JSON object string
        except HarnessError:
            pass
        # Strip common code fences.
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```") and lines[-1].strip() == "```":
                text = "\n".join(lines[1:-1])
        start = text.find("{")
        if start < 0:
            raise HarnessError("protocol_error", "Expected one strict JSON object")
        depth, in_str, escape = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        obj = text[start:i + 1]
                        parse_object(obj)  # raises if the extracted candidate is not strict JSON
                        return obj
        raise HarnessError("protocol_error", "Expected one strict JSON object")

    def complete(self, messages, purpose="policy"):
        # messages = [system, user(workcard)]. Send full text to Lanz (fresh).
        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        user = next((m["content"] for m in messages if m.get("role") == "user"), "")
        # Give Lanz the exact 2.1 tool schemas so it stops using v2-style full-state rewrites
        # (claims/answer_kind) and invalid fields. This is the delta contract.
        tool_schema = _TOOL_SCHEMA_HINT
        prompt = (
            f"System instructions:\n{system}\n\nCurrent state/workcard:\n{user}\n\n"
            f"TOOL CONTRACTS (exact allowed fields; do not invent fields like 'claims', 'answer_kind', "
            f"'revision_reason', 'attempt_id' outside the note pair, or extra keys):\n{tool_schema}\n\n"
            f"Return exactly one JSON object: {{\"action\": \"tool_name\", \"arguments\": {{...}}}}. "
            f"Do NOT wrap it in prose or code fences; output only the JSON. "
            f"For update_state, use ONLY these fields: target, answer, claim_updates, retire_claim_ids, "
            f"focus, dismiss_observation_ids, attempt_note. To bind a finding, put your finding text and its "
            f"observation_ids in claim_updates=[{{\"claim_id\":\"c0\",\"finding\":\"...\",\"observation_ids\":[\"oN\"]}}]."
            f"Do NOT emit a bare 'claims' rewrite."
        )
        reply = self.lanz.raw_text([self.lanz.user(prompt)])
        self.budget.unknown_usage_requests += 1
        self.budget.charged_tokens += 400
        return self._extract_action(reply)  # bare JSON object string; runner parses it strictly


class LanzAuditor:
    """Verifier role: fresh-context full-question audit via Lanz; returns validated report."""

    def __init__(self, lanz: LanzClient, budget, attempts=2):
        self.lanz, self.budget, self.attempts = lanz, budget, attempts
        self.identity = {"client": {"kind": "lanz_strong_auditor", "model": lanz.model, "base_url": lanz.base_url},
                         "prompt": AUDIT_PROMPT_VERSION, "system_hash": None}

    def audit(self, question, state, views):
        payload = {"question": question, **state,
                   "observations": [{"observation_id": v["observation_id"], "docid": v["docid"], "text": v["text"]}
                                    for v in views]}
        messages = [{"role": "system", "content": AUDIT_SYSTEM + "\nSchema:\n" + canonical(AUDIT_SCHEMA)},
                    {"role": "user", "content": canonical(payload)}]
        prompt = f"{messages[0]['content']}\n\nUser request:\n{messages[1]['content']}\n\nReturn the audit JSON exactly matching the schema."
        last = ""
        for attempt in range(self.attempts):
            reply = self.lanz.raw_text([self.lanz.user(prompt)])
            self.budget.unknown_usage_requests += 1
            self.budget.charged_tokens += 400
            try:
                obj = parse_object(LanzPolicy._extract_action(reply))  # lenient prose/fence recovery
                return validate_report(obj, state, {v["observation_id"]: v for v in views})
            except HarnessError as exc:
                last = str(exc)
                if attempt + 1 < self.attempts:
                    prompt += f"\n\n[Repair protocol only; keep all original evidence] {last}"
        raise HarnessError("audit_protocol_error", last)


def load_question(path, qid):
    matches = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            identity = str(r.get("query_id", r.get("qid", r.get("id"))))
            if identity == qid:
                q = r.get("query", r.get("question"))
                if isinstance(q, str) and q.strip():
                    matches.append(q.strip())
    if len(matches) != 1:
        raise ValueError(f"qid={qid} matched {len(matches)}")
    return matches[0]


def main():
    qid = sys.argv[1]
    arm = sys.argv[2]  # esr/off | esr/hard | esr/soft   (baseline needs ChatClient-finish, skip here)
    mode, audit_mode = "esr", arm.split("/")[1]
    run_dir = Path(RUN)
    out_dir = run_dir / arm
    out_dir.mkdir(parents=True, exist_ok=True)
    store = out_dir / f"{qid}.sqlite"
    if store.exists():
        print(f"skip existing {arm}/{qid}")
        return 0

    question = load_question(run_dir / "questions_only.jsonl", qid)
    lanz = LanzClient(timeout=180.0, max_tokens=2048)
    budget = _LanzBudget(24000)
    policy = LanzPolicy(lanz, budget)
    auditor = LanzAuditor(lanz, budget) if audit_mode != "off" else None

    ledger = Ledger(store)
    config = Config(mode=mode, audit_mode=audit_mode, max_actions=64, search_top_k=5,
                    view_chars=8000, recent_actions=4, max_pending_views=4)
    retriever = EchoRetriever("http://127.0.0.1:8000")
    retriever.identity["index_revision"] = "operator_declared"
    retriever.deterministic = True
    retriever.identity["deterministic"] = True

    manifest = {"qid": qid, "policy": policy.identity, "code_revision": "refactor-esr-state-2.1-stage0-lanz",
                "policy_prompt": {"version": POLICY_PROMPT_VERSION,
                                  "system_hash": digest(policy_system(config) + "\nTools:\n" + canonical(config.tools))},
                "auditor": auditor.identity if auditor else None,
                "generation_budget": 24000,
                "dataset_sha256": hashlib.sha256((run_dir / "questions_only.jsonl").read_bytes()).hexdigest(),
                "note": "Stage0: Lanz (Anthropic Messages) as policy AND verifier; shared UsageBudget; fresh audit context.",
                "schema_version": 3, "implementation": "2.1.0", "model": lanz.model,
                "thinking": True, "temperature": 0.6}

    harness = Harness(question, retriever, auditor, config=config, ledger=ledger, manifest=manifest)
    # install admission so capacity is enforced (mirror runner), then run
    def admissible(preview):
        try:
            from esr_harness.runner import messages_for as mf
            mf(preview, policy)
            return True
        except HarnessError as exc:
            if exc.code == "context_overflow":
                return False
            raise
    harness.admission = admissible
    result = run(harness, policy)
    ledger.verify()
    (out_dir / f"{qid}.summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    ledger.close()
    print("DONE", arm, qid, result["terminal"]["outcome"])
    return 0


if __name__ == "__main__":
    sys.exit(main())