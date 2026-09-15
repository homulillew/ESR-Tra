"""Deterministic CPU page-local selection; returns a contiguous ORIGINAL range."""
from __future__ import annotations

import math
import re

STOP = frozenset("a an the of to in on for and or is was were be by at with from what which who when where how page document please find read".split())


def select_window(text: str, goal: str, limit: int) -> dict:
    # Tokenize ORIGINAL characters before casefolding so expansions such as İ
    # cannot invent a scored token that has no corresponding original span.
    terms = list(dict.fromkeys(w for m in re.finditer(r"\w+", goal)
                               if (w := m.group().casefold()) not in STOP))[:48]
    if not terms:
        return {"matched": False, "reason": "no_discriminating_literal_terms", "method": "paragraph-lexical-v1"}
    blocks = []
    cursor = 0
    for match in re.finditer(r"\n\s*\n", text):
        end = match.end()
        if end - cursor < 160:
            continue
        for start in range(cursor, end, 1600):
            blocks.append((start, min(end, start + 1600)))
        cursor = end
    for start in range(cursor, len(text), 1600):
        blocks.append((start, min(len(text), start + 1600)))
    if not blocks:
        return {"matched": False, "reason": "empty_document", "method": "paragraph-lexical-v1"}
    token_sets = [{m.group().casefold() for m in re.finditer(r"\w+", text[a:b])} for a, b in blocks]
    frequencies = {term: sum(term in words for words in token_sets) for term in terms}
    scores = [sum(math.log(1 + len(blocks) / (1 + frequencies[t])) for t in terms if t in words)
              for words in token_sets]
    index = max(range(len(scores)), key=lambda i: (scores[i], -i))
    if scores[index] == 0:
        return {"matched": False, "reason": "no_literal_overlap", "method": "paragraph-lexical-v1"}
    a, b = blocks[index]
    matched_terms = [t for t in terms if t in token_sets[index]]
    before = min(600, limit // 4)
    anchor = next(m for m in re.finditer(r"\w+", text[a:b]) if m.group().casefold() in matched_terms)
    anchor_start, anchor_end = a + anchor.start(), a + anchor.end()
    if anchor_end - anchor_start > limit:
        return {"matched": False, "reason": "window_too_small_for_literal_match", "method": "paragraph-lexical-v1"}
    start = max(0, a - before)
    if index and blocks[index - 1][0] >= a - before:
        start = blocks[index - 1][0]
    if start + limit < anchor_end:
        start = max(a, anchor_end - limit, anchor_start - before)
    end = min(len(text), start + limit)
    return {"matched": True, "method": "paragraph-lexical-v1", "start": start, "end": end,
            "selected_block": [a, b], "matched_terms": matched_terms, "score": round(scores[index], 6),
            "selection_is_semantic_support": False,
            "block_truncated": b > end, "instruction": "Check the subject and adjoining context; lexical overlap does not establish the requested relation."}
