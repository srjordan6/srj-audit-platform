"""
Unit tests for the TEXT question partial, plus a small set of tests
confirming that NR (Numeric Range) questions render correctly via
the shared single-select partial.

Coverage focus
--------------
TEXT partial:
- Renders question text and ID
- Emits a <textarea> with the correct maxlength drawn from
  question.extended_metadata.max_length
- Falls back to a sensible default max when extended_metadata is
  missing or has no max_length key
- Prior-answer state populates the textarea for save-and-resume
- Required marker gated on question.required
- HTMX and CSRF attrs identical to the other partials
- data-max-length attribute exposes the cap for future JS enhancement

NR-via-single-select:
- A production-shaped NR question (bracket labels) renders as a radio
  list identical to SS
- data-question-type reflects "NR" so downstream analytics / scoring
  can differentiate

Companion to test_question_partials.py — same fixtures, same standalone
Django Engine pattern, no pytest-django dependency. Uses its own copies
of the Django-configure and engine fixtures so this file can run
alone.
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
    """Idempotent standalone Django config. Skipped if already configured
    (e.g., by test_question_partials.py running earlier)."""
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
        "submit_url": "/q/answer/T1-H-006/",
        "swap_target": "#question-shell",
        "csrf_token": "fake-csrf",
    }


def _text_question(max_length: int | None = 300) -> dict:
    """Production-shaped TEXT question (T1-H-006)."""
    extended: dict = {}
    if max_length is not None:
        extended["max_length"] = max_length
    return {
        "id": "T1-H-006",
        "question_type": "TEXT",
        "question_text": (
            "Anything we should know that the questionnaire didn't ask? "
            "(optional, max 300 characters)"
        ),
        "required": False,
        "options": None,
        "extended_metadata": extended,
    }


def _nr_question() -> dict:
    """Production-shaped NR question (T1-A-007 — revenue brackets)."""
    return {
        "id": "T1-A-007",
        "question_type": "NR",
        "question_text": "Approximate annual revenue",
        "required": True,
        "options": [
            "Under $5M", "$5-25M", "$25-100M", "$100M-$1B",
            "Over $1B", "Decline to answer",
        ],
    }


# ============================================================================
# TEXT partial
# ============================================================================

def test_text_renders_question_text_and_id(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_text.html")
    ctx = {**base_context, "question": _text_question()}
    html = tpl.render(Context(ctx))

    assert "T1-H-006" in html
    assert "Anything we should know that the questionnaire didn" in html


def test_text_emits_textarea_with_correct_maxlength(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_text.html")
    ctx = {**base_context, "question": _text_question(max_length=300)}
    html = tpl.render(Context(ctx))

    assert "<textarea" in html
    assert 'maxlength="300"' in html
    assert 'data-max-length="300"' in html
    assert "Maximum 300 characters" in html


def test_text_respects_alternate_max_length(engine, base_context):
    """Any future TEXT question with a different cap must render that cap,
    not hardcode 300."""
    tpl = engine.get_template("questionnaire/parti"
                              "als/_question_text.html")
    ctx = {**base_context, "question": _text_question(max_length=1500)}
    html = tpl.render(Context(ctx))

    assert 'maxlength="1500"' in html
    assert 'data-max-length="1500"' in html
    assert "Maximum 1500 characters" in html


def test_text_falls_back_to_default_when_max_length_missing(engine, base_context):
    """A TEXT question without extended_metadata.max_length falls back to
    the default (1000) so the partial always emits a sensible cap."""
    tpl = engine.get_template("questionnaire/partials/_question_text.html")
    # Question with empty extended_metadata
    question = _text_question(max_length=None)
    assert question["extended_metadata"] == {}
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    assert 'maxlength="1000"' in html
    assert 'data-max-length="1000"' in html
    assert "Maximum 1000 characters" in html


def test_text_prior_answer_populates_textarea(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_text.html")
    ctx = {
        **base_context,
        "question": _text_question(),
        "prior_answer": {"text": "We are still figuring out AI governance."},
    }
    html = tpl.render(Context(ctx))

    # The prior response text appears inside the <textarea> element
    ta_start = html.index("<textarea")
    ta_end = html.index("</textarea>")
    textarea_content = html[ta_start:ta_end]
    assert "We are still figuring out AI governance." in textarea_content


def test_text_no_prior_answer_leaves_textarea_empty(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_text.html")
    ctx = {**base_context, "question": _text_question()}
    html = tpl.render(Context(ctx))

    # Grab textarea inner content between opening tag close and </textarea>
    ta_open_end = html.index(">", html.index("<textarea"))
    ta_close = html.index("</textarea>")
    inner = html[ta_open_end + 1:ta_close]
    # Optional-textarea prior_answer=None => empty inner
    assert inner.strip() == ""


def test_text_no_required_marker_when_optional(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_text.html")
    question = _text_question()
    assert question["required"] is False
    html = tpl.render(Context({**base_context, "question": question}))

    assert "srj-question__required" not in html
    # Also no `required` attribute on the textarea itself
    ta_start = html.index("<textarea")
    ta_end = html.index(">", ta_start)
    textarea_tag = html[ta_start:ta_end]
    assert "required" not in textarea_tag


def test_text_shows_required_marker_when_required(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_text.html")
    question = _text_question()
    question["required"] = True
    html = tpl.render(Context({**base_context, "question": question}))

    assert "srj-question__required" in html
    # And the textarea carries the required attribute
    ta_start = html.index("<textarea")
    ta_end = html.index(">", ta_start)
    textarea_tag = html[ta_start:ta_end]
    assert "required" in textarea_tag


def test_text_submit_button_label_reflects_required_state(engine, base_context):
    """Optional TEXT questions (the T1-H-006 shape — end of questionnaire)
    show 'Save & finish' instead of 'Save & continue' because in practice
    they're the closing question."""
    tpl = engine.get_template("questionnaire/partials/_question_text.html")
    # T1-H-006 is optional → 'Save & finish'
    optional_q = _text_question()
    html_opt = tpl.render(Context({**base_context, "question": optional_q}))
    assert "Save &amp; finish" in html_opt
    assert "Save &amp; continue" not in html_opt

    # Any future required TEXT question → 'Save & continue'
    req_q = _text_question()
    req_q["required"] = True
    html_req = tpl.render(Context({**base_context, "question": req_q}))
    assert "Save &amp; continue" in html_req
    assert "Save &amp; finish" not in html_req


def test_text_emits_htmx_and_csrf(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_text.html")
    ctx = {**base_context, "question": _text_question()}
    html = tpl.render(Context(ctx))

    assert 'hx-post="/q/answer/T1-H-006/"' in html
    assert 'hx-target="#question-shell"' in html
    assert 'hx-swap="innerHTML"' in html
    assert 'data-question-id="T1-H-006"' in html
    assert 'data-question-type="TEXT"' in html
    assert 'name="csrfmiddlewaretoken"' in html


def test_text_is_a_fragment_not_a_full_page():
    """Same fragment contract as the other partials — must not extend
    base.html or emit <html>/<head>/<body>."""
    raw = (TEMPLATES_DIR / "questionnaire" / "partials" /
           "_question_text.html").read_text(encoding="utf-8")
    assert "{% extends" not in raw
    assert "<html" not in raw.lower()
    assert "<head" not in raw.lower()
    assert "<body" not in raw.lower()


# ============================================================================
# NR-via-single-select coverage
# ============================================================================
# The single-select partial's docstring claims it renders YN, SS, AND NR.
# The PR 1 tests exercise SS and YN explicitly. These two tests confirm
# the NR side of that claim against a production-shaped NR question.

def test_single_select_handles_nr_bracket_options(engine, base_context):
    """A production-shaped NR question (revenue brackets) renders as a
    radio list identical to SS. All 6 bracket options appear as
    selectable radios."""
    tpl = engine.get_template("questionnaire/partials/_question_single_select.html")
    question = _nr_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    assert html.count('type="radio"') == len(question["options"])
    for option in question["options"]:
        assert option in html
    # Currency and range punctuation must survive templating
    assert "$5-25M" in html
    assert "$100M-$1B" in html
    assert "Decline to answer" in html


def test_single_select_marks_nr_via_data_question_type(engine, base_context):
    """Even though the UI is identical to SS, downstream code (analytics,
    scoring dispatch) needs to distinguish NR — the data-question-type
    attribute carries the discriminator."""
    tpl = engine.get_template("questionnaire/partials/_question_single_select.html")
    ctx = {**base_context, "question": _nr_question()}
    html = tpl.render(Context(ctx))

    assert 'data-question-type="NR"' in html
