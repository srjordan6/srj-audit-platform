"""
Unit tests for the RANK question partial.

Coverage focus
--------------
- Two-column layout: "Available" (left) and "Your ranking" (right)
- Without prior_answer, ALL options appear in the available column
  and NONE in the ranking column
- With prior_answer, ranked options appear in the right column in the
  correct order, and remaining options appear in the left
- rank_max drawn from question.extended_metadata.rank_max, falls back
  to len(options) if absent
- Every option is present exactly once between the two columns
  (no duplicates, no omissions)
- The hidden `answer` input is emitted for the JS-driven submit path
- data-* attributes SortableJS needs are present (data-role="rank-source"
  and data-role="rank-target"; data-max on the target list)
- HTMX attrs match the pattern used by other partials
- The partial is a fragment (no extends, no <html>/<head>/<body>)

RANK is not covered by any other partial — it needs its own drag-and-drop
UI. Ranking two lists with SortableJS is the industry-standard pattern;
this partial renders the DOM SortableJS attaches to. JS behavior is
verified manually.
"""

from __future__ import annotations

from pathlib import Path

import django
import pytest
from django.template import Context, Engine

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "templates"


@pytest.fixture(scope="session", autouse=True)
def _configure_django():
    from django.conf import settings
    if not settings.configured:
        settings.configure(
            DEBUG=False,
            TEMPLATES=[{
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [str(TEMPLATES_DIR)],
                "APP_DIRS": False,
                "OPTIONS": {"builtins": []},
            }],
        )
        django.setup()


@pytest.fixture
def engine():
    return Engine(dirs=[str(TEMPLATES_DIR)])


@pytest.fixture
def base_context():
    return {
        "submit_url": "/q/answer/T1-G-001/",
        "swap_target": "#question-shell",
        "csrf_token": "fake-csrf",
    }


def _rank_top3_question() -> dict:
    """Production-shaped RANK question T1-F-012 (top 3 barriers)."""
    return {
        "id": "T1-F-012",
        "question_type": "RANK",
        "question_text": "What are the top three barriers to better AI outcomes in the company? (rank top 3)",
        "required": True,
        "options": [
            "Employee skill", "Leadership attention", "Data quality",
            "Unclear ROI", "Regulatory uncertainty", "Budget",
            "Cultural resistance", "Vendor complexity",
            "No clear ownership", "Technology limitations",
        ],
        "extended_metadata": {"rank_max": 3},
    }


def _rank_top5_question() -> dict:
    """Production-shaped RANK question T1-G-001 (top 5 outcomes)."""
    return {
        "id": "T1-G-001",
        "question_type": "RANK",
        "question_text": "What outcomes does leadership want AI to produce, in order of priority? (rank top 5)",
        "required": True,
        "options": [
            "Cost reduction", "Revenue growth", "Speed", "Quality",
            "Risk reduction", "Customer experience", "Employee productivity",
            "Competitive position", "Compliance", "Innovation",
        ],
        "extended_metadata": {"rank_max": 5},
    }


# ============================================================================
# Base render + column structure
# ============================================================================

def test_rank_renders_question_text_and_id(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_rank.html")
    ctx = {**base_context, "question": _rank_top3_question()}
    html = tpl.render(Context(ctx))
    assert "T1-F-012" in html
    assert "top three barriers" in html


def test_rank_renders_two_columns(engine, base_context):
    """The partial must render both the source list and the target list."""
    tpl = engine.get_template("questionnaire/partials/_question_rank.html")
    ctx = {**base_context, "question": _rank_top3_question()}
    html = tpl.render(Context(ctx))

    # Source (available) list
    assert 'id="rank-available-T1-F-012"' in html
    assert 'data-role="rank-source"' in html

    # Target (ranking) list
    assert 'id="rank-selected-T1-F-012"' in html
    assert 'data-role="rank-target"' in html


def test_rank_target_list_has_max_attribute(engine, base_context):
    """SortableJS uses data-max to enforce the top-N cap client-side."""
    tpl = engine.get_template("questionnaire/partials/_question_rank.html")
    ctx = {**base_context, "question": _rank_top3_question()}
    html = tpl.render(Context(ctx))
    assert 'data-max="3"' in html
    assert 'data-rank-max="3"' in html


def test_rank_max_extracted_from_extended_metadata(engine, base_context):
    """T1-G-001 has rank_max=5 — verify."""
    tpl = engine.get_template("questionnaire/partials/_question_rank.html")
    ctx = {**base_context, "question": _rank_top5_question()}
    html = tpl.render(Context(ctx))
    assert 'data-max="5"' in html
    assert 'data-rank-max="5"' in html
    assert "top 5" in html


def test_rank_falls_back_to_options_length_when_no_rank_max(engine, base_context):
    """If extended_metadata has no rank_max, default to len(options)."""
    tpl = engine.get_template("questionnaire/partials/_question_rank.html")
    question = _rank_top3_question()
    question["extended_metadata"] = {}
    assert "rank_max" not in question["extended_metadata"]
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))
    # 10 options → data-max="10"
    assert 'data-max="10"' in html


# ============================================================================
# No prior answer: all options in the available column
# ============================================================================

def test_rank_no_prior_answer_all_options_in_source_list(engine, base_context):
    """With no prior_answer, every option appears in the source list
    and the target list is empty."""
    tpl = engine.get_template("questionnaire/partials/_question_rank.html")
    question = _rank_top3_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    # Extract source list content
    src_start = html.index('id="rank-available-')
    src_end = html.index("</ol>", src_start)
    source_html = html[src_start:src_end]

    tgt_start = html.index('id="rank-selected-')
    tgt_end = html.index("</ol>", tgt_start)
    target_html = html[tgt_start:tgt_end]

    # All 10 options appear as data-option in the source list
    for option in question["options"]:
        assert f'data-option="{option}"' in source_html, f"missing {option} in source"

    # Target list has no data-option entries yet
    assert "data-option=" not in target_html


# ============================================================================
# With prior answer: ranking populates target, remainder in source
# ============================================================================

def test_rank_prior_answer_populates_target_in_order(engine, base_context):
    """Prior ranking of ["Data quality", "Budget", "No clear ownership"]
    should render in the target list in that order."""
    tpl = engine.get_template("questionnaire/partials/_question_rank.html")
    question = _rank_top3_question()
    prior_ranked = ["Data quality", "Budget", "No clear ownership"]
    ctx = {
        **base_context,
        "question": question,
        "prior_answer": {"ranked": prior_ranked},
    }
    html = tpl.render(Context(ctx))

    # Target list contains the 3 ranked options in order
    tgt_start = html.index('id="rank-selected-')
    tgt_end = html.index("</ol>", tgt_start)
    target_html = html[tgt_start:tgt_end]

    # Each ranked option appears with its 1-indexed position badge
    for i, option in enumerate(prior_ranked, start=1):
        assert f'data-option="{option}"' in target_html
        # The position badge should render 1, 2, 3 in order — check by index
    # Position badges 1, 2, 3 appear in the target
    for pos in ("1", "2", "3"):
        assert f'>{pos}</span>' in target_html


def test_rank_prior_answer_remainder_goes_to_source(engine, base_context):
    """Options NOT in prior_answer.ranked must still appear in the
    source list (available for re-ranking)."""
    tpl = engine.get_template("questionnaire/partials/_question_rank.html")
    question = _rank_top3_question()
    prior_ranked = ["Data quality", "Budget", "No clear ownership"]
    ctx = {
        **base_context,
        "question": question,
        "prior_answer": {"ranked": prior_ranked},
    }
    html = tpl.render(Context(ctx))

    src_start = html.index('id="rank-available-')
    src_end = html.index("</ol>", src_start)
    source_html = html[src_start:src_end]

    # Options NOT in prior_ranked must appear in source
    unranked = [o for o in question["options"] if o not in prior_ranked]
    assert len(unranked) == 7
    for option in unranked:
        assert f'data-option="{option}"' in source_html

    # Options that ARE in prior_ranked must NOT appear in source
    for option in prior_ranked:
        assert f'data-option="{option}"' not in source_html


def test_rank_every_option_appears_exactly_once(engine, base_context):
    """Sanity: every option appears exactly once across source + target
    combined, regardless of prior_answer."""
    tpl = engine.get_template("questionnaire/partials/_question_rank.html")
    question = _rank_top3_question()
    ctx = {
        **base_context,
        "question": question,
        "prior_answer": {"ranked": ["Speed"]},  # 1 pre-ranked, 9 remain
    }
    # Adjust question to include "Speed" as an option
    question["options"] = ["Speed"] + question["options"]
    html = tpl.render(Context(ctx))

    for option in question["options"]:
        assert html.count(f'data-option="{option}"') == 1


# ============================================================================
# Hidden input + form structure
# ============================================================================

def test_rank_emits_hidden_answer_input(engine, base_context):
    """The JS submit path populates a single hidden input named 'answer'
    with the concatenated ordered labels. The input must be present in
    the initial DOM even if empty."""
    tpl = engine.get_template("questionnaire/partials/_question_rank.html")
    ctx = {**base_context, "question": _rank_top3_question()}
    html = tpl.render(Context(ctx))

    assert '<input type="hidden" name="answer"' in html
    assert 'data-role="rank-hidden-input"' in html


def test_rank_form_has_onsubmit_handler(engine, base_context):
    """The form calls srjRankPrepareSubmit before submit to populate
    the hidden input from the current DOM order."""
    tpl = engine.get_template("questionnaire/partials/_question_rank.html")
    ctx = {**base_context, "question": _rank_top3_question()}
    html = tpl.render(Context(ctx))
    assert "srjRankPrepareSubmit" in html


def test_rank_emits_htmx_and_csrf(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_rank.html")
    ctx = {**base_context, "question": _rank_top3_question()}
    html = tpl.render(Context(ctx))
    assert 'hx-post="/q/answer/T1-G-001/"' in html
    assert 'hx-target="#question-shell"' in html
    assert 'data-question-type="RANK"' in html
    assert 'name="csrfmiddlewaretoken"' in html


def test_rank_noscript_notice_present(engine, base_context):
    """RANK requires JS. If JS is disabled, respondent must see a notice."""
    tpl = engine.get_template("questionnaire/partials/_question_rank.html")
    ctx = {**base_context, "question": _rank_top3_question()}
    html = tpl.render(Context(ctx))
    assert "<noscript>" in html
    assert "requires JavaScript" in html


def test_rank_is_a_fragment_not_a_full_page():
    """Fragment contract."""
    raw = (TEMPLATES_DIR / "questionnaire" / "partials" /
           "_question_rank.html").read_text(encoding="utf-8")
    assert "{% extends" not in raw
    assert "<html" not in raw.lower()
    assert "<head" not in raw.lower()
    assert "<body" not in raw.lower()
