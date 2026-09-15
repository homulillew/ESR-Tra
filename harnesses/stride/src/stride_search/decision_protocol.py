"""Optional, versioned inference instructions; never a semantic acceptance gate."""
from hashlib import sha256

CONSTRAINT_REVIEW = """
Check candidates against the question's requirements before committing to them.
When you first identify a plausible candidate, briefly list the requirements that
distinguish a correct candidate. Preserve dates, entity roles, and relations.
For each requirement distinguish supported by delivered source text, contradicted,
and unresolved. Search snippets locate sources; they are not citable evidence.
A true fact about a candidate supports only that fact. The question's conditions
are tests for a candidate, not evidence that your current candidate passes them.

After reading evidence that changes a candidate's status, update only the affected
requirements. For a supported or contradicted requirement, identify the delivered
evidence reference and exact source phrase. If the phrase is absent from that
window, leave the requirement unresolved. Check who the passage is actually about;
an author, photographer, relative, and article subject are different roles.
Keep source statements separate from your inferences.

Use the most discriminating unresolved requirement to choose the next search or
read action. When source evidence contradicts a required condition, set that
candidate aside and investigate another candidate or another entry point.
A missing fact alone does not reject a candidate. Do not silently relax a date
or relationship to preserve a favored candidate.

Before finish, check all identifying requirements and that each cited passage
supports the claim attributed to it. Resolve known contradictions while research
budget remains. If evidence is insufficient at FINAL, use the existing abstention
option. Keep checks brief, within the current decision; continue issuing useful
tool actions. No extra note, gap update, review call, or output field is required.
"""

SEARCH_PIVOT = """The last two search rounds delivered no new source passage. In your next search batch, use one query to investigate a different identifying clue from the question. Omit the current unverified candidate's name from that query. Use concrete names, terms, dates, or relations stated in the question; use a short lexical query rather than the full question. Keep within the existing query limit and proceed directly with tool actions."""

PROTOCOLS = {'baseline': '', 'constraint-review-v1': CONSTRAINT_REVIEW,
             'search-pivot-v1': '', 'middle-history-v1': '', 'once-prose-reset-v1': '', 'relation-review-once-v1': '', 'relation-review-memory-v1': '', 'read-only-once-v1': ''}
PIVOT_RULE = {'version': 'completed-search-no-new-source-v1',
              'consecutive_rounds': 2, 'minimum_remaining_model_calls': 3,
              'max_triggers': 2, 'reset_after_trigger': True}


def identity(name):
    if name not in PROTOCOLS:
        raise ValueError('Unknown decision protocol')
    if name == 'read-only-once-v1':
        from .read_only import identity as read_identity
        return read_identity()
    if name == 'relation-review-memory-v1':
        from .review_memory import identity as memory_identity
        return memory_identity()
    if name == 'relation-review-once-v1':
        from .relation_review import identity as review_identity
        return review_identity()
    if name == 'once-prose-reset-v1':
        from .history_projection import once_identity
        return once_identity()
    if name == 'middle-history-v1':
        from .history_projection import identity as projection_identity
        return projection_identity()
    instruction = SEARCH_PIVOT if name == 'search-pivot-v1' else PROTOCOLS[name]
    return {'version': name, 'instruction_sha256': sha256(instruction.encode()).hexdigest(),
            'kind': 'policy_instruction_not_verified_evidence',
            **({'trigger_rule': dict(PIVOT_RULE)} if name == 'search-pivot-v1' else {})}


class SearchPivotState:
    """Execution observations survive context eviction; projection never consumes them."""

    def __init__(self):
        self.completed = {}
        self.through = 0
        self.seen = set()
        self.search_rounds = []
        self.used = 0

    @staticmethod
    def observation(group):
        from .contract import loads
        names = {call['id']: call['function']['name']
                 for call in group['messages'][0].get('tool_calls', [])}
        searched = any(names.get(m.get('tool_call_id')) == 'search'
                       and loads(m['content']).get('executed', False)
                       for m in group['messages'] if m['role'] == 'tool')
        return searched, set(group['evidence'])

    def complete(self, group):
        self.completed[group['round']] = self.observation(group)

    def project(self, groups, visible, through, *, remaining, final):
        # Preflight may supply an unfinished group, only as a prospective view.
        observations = dict(self.completed)
        observations.update({g['round']: self.observation(g) for g in groups})
        seen, rounds = set(self.seen), list(self.search_rounds)
        visible = set(visible)
        for number in range(self.through + 1, through + 1):
            searched, evidence = observations.get(number, (False, set()))
            new = (evidence & visible) - seen
            seen.update(evidence & visible)
            rounds = [] if new or not searched else [*rounds, number][-PIVOT_RULE['consecutive_rounds']:]
        if visible - seen:
            rounds = []
        seen.update(visible)
        trigger = None
        if (len(rounds) == PIVOT_RULE['consecutive_rounds']
                and self.used < PIVOT_RULE['max_triggers']
                and remaining >= PIVOT_RULE['minimum_remaining_model_calls'] and not final):
            trigger = {'protocol': identity('search-pivot-v1'),
                       'source_rounds': rounds, 'trigger_number': self.used + 1,
                       'observation': 'no new source passage', 'instruction': SEARCH_PIVOT}
        return {'through': through, 'seen': seen, 'search_rounds': rounds, 'trigger': trigger}

    def commit(self, projection):
        self.through = projection['through']
        self.seen = set(projection['seen'])
        self.search_rounds = list(projection['search_rounds'])
        if projection['trigger'] is not None:
            self.used += 1
            self.search_rounds = []


class OnceProseState(SearchPivotState):
    """One attempted request; observations persist independently of rolling history."""

    @staticmethod
    def observation(group):
        from .contract import loads
        names = {c['id']: c['function']['name']
                 for c in group['messages'][0].get('tool_calls', [])}
        searched = any(names.get(m.get('tool_call_id')) == 'search'
                       and loads(m['content']).get('executed', False)
                       and loads(m['content']).get('ok', False)
                       for m in group['messages'] if m['role'] == 'tool')
        return searched, set(group['evidence'])

    def project(self, groups, visible, through, *, remaining, final):
        observations = dict(self.completed)
        observations.update({g['round']: self.observation(g) for g in groups})
        seen, rounds = set(self.seen), list(self.search_rounds)
        visible = set(visible)
        for number in range(self.through + 1, through + 1):
            searched, evidence = observations.get(number, (False, set()))
            new = (evidence & visible) - seen
            seen.update(evidence & visible)
            rounds = [] if new or not searched else [*rounds, number][-3:]
        if visible - seen:
            rounds = []
        seen.update(visible)
        trigger = None
        if len(rounds) == 3 and not self.used and remaining >= 3 and not final:
            trigger = {'source_rounds': rounds, 'trigger_number': 1,
                       'observation': 'no new source passage'}
        return {'through': through, 'seen': seen, 'search_rounds': rounds, 'trigger': trigger}


class RelationReviewState(OnceProseState):
    def project(self, groups, visible, through, *, remaining, final):
        return super().project(groups, visible, through, remaining=remaining,
                               final=final or remaining < 4)
