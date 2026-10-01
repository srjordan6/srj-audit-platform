"""Questions asked once when a company buys both audits (OD-19, 2026-10-01).

On a combined engagement the governance questionnaire (Pillar I) comes
first. Where a security question asks the same thing a governance
question already asked, a respondent who saw the governance question is
not asked again: the governance answer is translated onto the security
question's Yes / Partially / No / Don't know scale and scored there.

The rule for a pair is strict: the two questions must ask the same fact
at the same depth, and every governance option must translate to one
security answer without guessing. Pairs that are merely related (a
governance question about an AI tool list next to a security question
about a dated four-layer inventory, for instance) are NOT here; both are
asked, because the security audit has to stand on its own.

Removal is per respondent: a security question is skipped only when that
respondent's role sees the governance counterpart. A role that does not
(a CISO never sees the board insurance question) is still asked it.
"""

from __future__ import annotations

from typing import Any

# security question -> (governance question, [(option prefix, security answer)])
# Prefixes match the governance option labels case-insensitively; the first
# match wins. "Don't know" always maps to Don't know.
OVERLAP: dict[str, tuple[str, list[tuple[str, str]]]] = {
    # "Does your risk register contain a specific entry for algorithmic/AI
    # model risk?" <- "Are AI risks on the corporate risk register?"
    "AIITSA-GOV-001": ("T1-F-010", [
        ("yes — listed but without owners", "Partially"),
        ("yes", "Yes"),
        ("no", "No"),
    ]),
    # "Does your cyber insurance cover AI-specific incidents, and has the
    # carrier been asked?" <- "Does any insurance policy specifically
    # address AI-related liability?"
    "AIITSA-GOV-018": ("T1-E-021", [
        ("yes — named coverage", "Yes"),
        ("possibly included", "Partially"),
        ("no", "No"),
    ]),
    # "Is AI incident response integrated into your existing IR plan?" <-
    # "Is there a documented incident response process for AI-related
    # failures?"
    "AIITSA-SOC-009": ("T1-F-008", [
        ("yes — tested", "Yes"),
        ("yes — written only", "Yes"),
        ("no", "No"),
    ]),
    # "Do you have a data flow map tracing every category of sensitive data
    # through every AI system that touches it?" <- "For AI systems handling
    # regulated, customer, or proprietary data, is data lineage documented?"
    "AIITSA-DAT-001": ("T1-F-023", [
        ("yes — for all", "Yes"),
        ("yes — for some", "Partially"),
        ("no", "No"),
    ]),
    # "Do you know where regulated personal data enters your AI systems?" <-
    # "Have you mapped which AI tools touch regulated data?"
    "AIITSA-DAT-004": ("T1-E-006", [
        ("yes — complete", "Yes"),
        ("partial", "Partially"),
        ("no", "No"),
    ]),
}

SOURCE_IDS = {src for src, _ in OVERLAP.values()}


def _selected(value: Any) -> str | None:
    v = value
    if isinstance(v, dict):
        v = v.get("selected", v.get("value"))
    if isinstance(v, list):
        v = v[0] if v else None
    return None if v is None else str(v)


def translate(aiitsa_id: str, t1_value: Any, t1_dont_know: bool = False) -> dict | None:
    """The security answer a governance answer stands for, as the response
    dict the AIITSA scorer reads, or None when it cannot be translated."""
    pair = OVERLAP.get(aiitsa_id)
    if pair is None:
        return None
    src, table = pair
    sel = _selected(t1_value)
    if t1_dont_know or (sel or "").lower().startswith(("don't know", "don’t know", "i'm not sure")):
        return {"value": {"selected": "Don't know"}, "dont_know": True, "derived_from": src}
    if not sel:
        return None
    low = sel.lower()
    for prefix, answer in table:
        if low.startswith(prefix):
            return {"value": {"selected": answer}, "dont_know": False, "derived_from": src}
    return None


def skipped_for(visible_ids: set[str]) -> set[str]:
    """Security question ids to drop for a respondent whose visible
    question set is visible_ids (governance counterparts included)."""
    return {aid for aid, (src, _) in OVERLAP.items() if src in visible_ids}


def derive_for_respondent(t1_answers: dict[str, dict], have: set[str]) -> dict[str, dict]:
    """{aiitsa_id: response} for every overlapping security question this
    respondent was not asked but answered through its governance pair."""
    out = {}
    for aid, (src, _) in OVERLAP.items():
        if aid in have or src not in t1_answers:
            continue
        resp = t1_answers[src]
        d = translate(aid, resp.get("value"), resp.get("dont_know", False))
        if d is not None:
            out[aid] = d
    return out
