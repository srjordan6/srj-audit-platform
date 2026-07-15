"""Response aggregate statistics for the operator dashboard analytics view.

Pure Python — takes a list of {"question_id", "answer_value", "is_dont_know"}
dicts (from responses table) and returns per-question stats:

    {
        "question_id": "T1-A-001",
        "question_text": "Your role in the company",
        "question_type": "SS",
        "section": "A",
        "n_answered": 42,
        "n_dont_know": 3,
        "options": [
            {"label": "CEO or Owner", "count": 18, "pct": 42.9},
            ...
        ],
        "mode":   "CEO or Owner",
        "mean":   None,     # only for numeric-mappable types
        "median": None,
        "stdev":  None,
    }

Numeric extraction: L5 answers ("1", "5 (high confidence)") map to 1-5.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from typing import Any, Iterable, Optional


_LEADING_DIGIT_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)")


def _extract_selected(raw: Any) -> list[str]:
    """Pull a list of option-strings out of a response's answer_value.

    JSONB may arrive as dict or JSON string (psycopg version dependent).
    Normalizes SS/MS shapes ({"selected": str|list}), RANK ({"ranked":[]}),
    TOOL_INVENTORY / LAW_INVENTORY ({"selected":[], "other":""}), and
    the odd TEXT ({"text":...}).
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return [raw]
    if not isinstance(raw, dict):
        return [str(raw)]
    sel = raw.get("selected")
    if isinstance(sel, list):
        out = [str(s) for s in sel]
    elif isinstance(sel, str):
        out = [sel]
    else:
        out = []
    if raw.get("other"):
        # Split comma-separated custom values into individual entries.
        for chunk in str(raw.get("other")).split(","):
            chunk = chunk.strip()
            if chunk:
                out.append(f"Other: {chunk}")
    if raw.get("ranked"):
        out.extend(str(r) for r in raw["ranked"])
    if raw.get("text"):
        out.append(f"[text response, {len(str(raw['text']))} chars]")
    return out


def _numeric_value(option: str) -> Optional[float]:
    """Try to pull a leading number out of an option string.

    Handles: '1', '5 (high confidence)', '$5-25M' -> 5, '26-100' -> 26.
    Returns None for options with no leading number.
    """
    m = _LEADING_DIGIT_RE.match(option)
    if m:
        try:
            return float(m.group(1))
        except (ValueError, TypeError):
            pass
    return None


def question_stats(
    question: dict,
    responses: Iterable[dict],
) -> dict:
    """Return stats for one question given the rows from responses table."""
    qid = question["id"]
    qtype = question["question_type"]
    all_option_labels = list(question.get("options") or [])

    counter: Counter = Counter()
    numerics: list[float] = []
    n_answered = 0
    n_dont_know = 0

    for row in responses:
        if row.get("question_id") != qid:
            continue
        n_answered += 1
        if row.get("is_dont_know"):
            n_dont_know += 1
        selected = _extract_selected(row.get("answer_value"))
        for s in selected:
            counter[s] += 1
            n = _numeric_value(s)
            if n is not None:
                numerics.append(n)

    total_picks = sum(counter.values())
    options_out = []
    for label, cnt in counter.most_common():
        pct = (cnt / total_picks * 100.0) if total_picks else 0.0
        options_out.append({"label": label, "count": cnt, "pct": round(pct, 1)})

    mode = counter.most_common(1)[0][0] if counter else None

    mean = median = stdev = None
    if len(numerics) >= 1:
        mean = round(statistics.fmean(numerics), 2)
        median = round(statistics.median(numerics), 2)
        if len(numerics) >= 2:
            stdev = round(statistics.stdev(numerics), 2)

    return {
        "question_id": qid,
        "question_text": question.get("question_text", ""),
        "question_type": qtype,
        "section": question.get("section", ""),
        "n_answered": n_answered,
        "n_dont_know": n_dont_know,
        "options": options_out,
        "mode": mode,
        "mean": mean,
        "median": median,
        "stdev": stdev,
        "n_all_options_in_bank": len(all_option_labels),
    }
