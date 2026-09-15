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

PROTOCOLS = {'baseline': '', 'constraint-review-v1': CONSTRAINT_REVIEW}


def identity(name):
    if name not in PROTOCOLS:
        raise ValueError('Unknown decision protocol')
    return {'version': name, 'instruction_sha256': sha256(PROTOCOLS[name].encode()).hexdigest(),
            'kind': 'policy_instruction_not_verified_evidence'}
