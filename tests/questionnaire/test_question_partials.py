"""
Unit tests for the three question-rendering partials in
templates/questionnaire/partials/.

Coverage focus
--------------
- Each partial renders the question text and stable identifiers
- Each partial renders the correct number and shape of input controls
  for the production option lists actually present in the bank
- Prior-answer state pre-selects the matching control(s) for
  save-and-resume
- HTMX submission attrs (hx-post, hx-target, hx-swap) carry the values
  the view layer will supply
- CSRF tokens are emitted (Django requires this on all stateful POSTs)
- "Don't know" and other don't-know variants are rendered as ordinary
  options — no special UI affordance, matching the production data shape
- The required attribute / required marker is gated on question.required

These tests use Django's STANDALONE template engine
(django.template.Engine, configured with `dirs=`) rather than the full
Django settings stack. This matches Sprint B's pure-pytest convention
and means the tests run anywhere Django is installed without needing
a DJANGO_SETTINGS_MODULE or pytest-django.

Path discovery is relative to this test file so the tests work from
any cwd. The partials live two directories up at
templates/questionnaire/partials/.
"""

from __future__ import annotations

from pathlib import Path

import django
import pytest
from django.template import Context, Engine
from django.template.backends.django import DjangoTemplates

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "templates"


@pytest.fixture(scope="session", autouse=True)
def _configure_django():
    """Minimal Django configuration for standalone template rendering.

    `django.setup()` requires a configured settings module. We provide
    one with just the TEMPLATES backend dict that DjangoTemplates needs.
    No INSTALLED_APPS, no database, no middleware.
    """
    from django.conf import settings
    if not settings.configured:
        settings.configure(
            DEBUG=False,
            TEMPLATES=[{
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [str(TEMPLATES_DIR)],
                "APP_DIRS": False,
                "OPTIONS": {
                    "builtins": [],
                },
            }],
        )
        django.setup()


@pytest.fixture
def engine():
    """Django standalone Engine pointed at templates/ in the repo root."""
    return Engine(dirs=[str(TEMPLATES_DIR)])


@pytest.fixture
def base_context():
    """Default context bits shared across all partial renders."""
    return {
        "submit_url": "/q/answer/T1-B-001/",
        "swap_target": "#question-shell",
        # csrf_token is referenced via {% csrf_token %} — the standalone
        # engine emits a placeholder when no middleware is configured.
        # We don't assert against the token literal, only that the tag
        # was processed (no template syntax error).
        "csrf_token": "fake-csrf",
    }


def _ss_question() -> dict:
    """A production-shaped SS question (T1-A-001 — role question)."""
    return {
        "id": "T1-A-001",
        "question_type": "SS",
        "question_text": "Your role in the company",
        "required": True,
        "options": [
            "Board Member", "CEO or Owner", "CFO", "CIO", "CISO",
            "COO", "VP", "Director", "Line Manager",
            "Individual Contributor", "Other",
        ],
    }


def _yn_question() -> dict:
    """A YN question with non-trivial nuanced options (T1-B-013 shape)."""
    return {
        "id": "T1-B-013",
        "question_type": "YN",
        "question_text": (
            "Have you ever used a personal account, free tool, or browser "
            "extension with AI features for work tasks?"
        ),
        "required": True,
        "options": [
            "Yes — regularly", "Yes — occasionally", "No",
            "I'm not sure", "Decline to answer",
        ],
    }


def _ms_question() -> dict:
    """A production-shaped MS question (T1-B-002 — inventory contents)."""
    return {
        "id": "T1-B-002",
        "question_type": "MS",
        "question_text": "What does that inventory include? (select all that apply)",
        "required": False,
        "options": [
            "Tool name", "Owner", "Cost", "Purpose", "Data accessed",
            "Vendor", "Date adopted", "Approval status",
            "Performance metric", "Review cadence", "Contract terms",
            "Risk classification", "Vendor-enabled AI features",
            "Other (specify)", "None of these",
        ],
    }


def _l5_question() -> dict:
    """A production-shaped L5 question with anchored endpoints (T1-D-014)."""
    return {
        "id": "T1-D-014",
        "question_type": "L5",
        "question_text": "How much do you trust the AI outputs in your day-to-day workflow?",
        "required": True,
        "options": [
            "1 (not at all)", "2", "3", "4", "5 (strongly trust)",
        ],
    }


# ============================================================================
# Single-select partial (covers YN / SS / NR)
# ============================================================================

def test_single_select_renders_question_text_and_id(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_single_select.html")
    ctx = {**base_context, "question": _ss_question()}
    html = tpl.render(Context(ctx))

    assert "Your role in the company" in html
    assert "T1-A-001" in html


def test_single_select_renders_one_radio_per_option(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_single_select.html")
    question = _ss_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    # Exactly len(options) radio inputs, all with name="answer"
    assert html.count('type="radio"') == len(question["options"])
    assert html.count('name="answer"') == len(question["options"])

    # Each option label appears in the rendered HTML
    for option in question["options"]:
        assert option in html


def test_single_select_handles_yn_with_nuanced_options(engine, base_context):
    """YN type with semantic variants (Yes — regularly, etc.) renders
    the same way as SS — five radio inputs, one per option."""
    tpl = engine.get_template("questionnaire/partials/_question_single_select.html")
    question = _yn_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    assert html.count('type="radio"') == 5
    assert "Yes — regularly" in html
    assert "Yes — occasionally" in html
    assert "Decline to answer" in html
    # Note that I'm not handled specially — same affordance as the others
    assert "I&#x27;m not sure" in html or "I'm not sure" in html


def test_single_select_prior_answer_preselects_radio(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_single_select.html")
    question = _ss_question()
    ctx = {
        **base_context,
        "question": question,
        "prior_answer": {"selected": "CFO"},
    }
    html = tpl.render(Context(ctx))

    # The CFO radio should carry the checked attribute and no others
    cfo_idx = html.index('value="CFO"')
    cfo_input_start = html.rfind("<input", 0, cfo_idx)
    cfo_input_end = html.index(">", cfo_idx)
    cfo_input = html[cfo_input_start:cfo_input_end]
    assert "checked" in cfo_input

    # Exactly one checked radio in the rendered output
    assert html.count("checked") == 1


def test_single_select_no_prior_answer_no_checked(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_single_select.html")
    ctx = {**base_context, "question": _ss_question()}
    html = tpl.render(Context(ctx))
    assert "checked" not in html


def test_single_select_required_marker_when_required(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_single_select.html")
    question = _ss_question()
    assert question["required"] is True
    html = tpl.render(Context({**base_context, "question": question}))

    # The visible required asterisk is in the legend
    assert "srj-question__required" in html
    # Each radio carries the required HTML attribute (for native validation)
    assert html.count(" required") >= 1


def test_single_select_no_required_marker_when_optional(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_single_select.html")
    question = _ss_question()
    question["required"] = False
    html = tpl.render(Context({**base_context, "question": question}))
    assert "srj-question__required" not in html


def test_single_select_emits_htmx_form_attrs(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_single_select.html")
    ctx = {**base_context, "question": _ss_question()}
    html = tpl.render(Context(ctx))

    assert 'hx-post="/q/answer/T1-B-001/"' in html
    assert 'hx-target="#question-shell"' in html
    assert 'hx-swap="innerHTML"' in html
    assert 'data-question-id="T1-A-001"' in html
    assert 'data-question-type="SS"' in html


def test_single_select_emits_csrf_tag(engine, base_context):
    """The {% csrf_token %} tag must be processed without error.
    Standalone Engine emits a hidden input even without middleware."""
    tpl = engine.get_template("questionnaire/partials/_question_single_select.html")
    ctx = {**base_context, "question": _ss_question()}
    html = tpl.render(Context(ctx))
    # csrf_token tag emits a hidden input named csrfmiddlewaretoken
    assert 'name="csrfmiddlewaretoken"' in html


# ============================================================================
# Multi-select partial
# ============================================================================

def test_multi_select_renders_one_checkbox_per_option(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_multi_select.html")
    question = _ms_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    assert html.count('type="checkbox"') == len(question["options"])
    assert html.count('name="answer"') == len(question["options"])
    for option in question["options"]:
        assert option in html


def test_multi_select_prior_answer_prechecks_selected_options(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_multi_select.html")
    question = _ms_question()
    ctx = {
        **base_context,
        "question": question,
        "prior_answer": {
            "selected": ["Tool name", "Owner", "Cost"],
        },
    }
    html = tpl.render(Context(ctx))

    # Exactly 3 checked checkboxes
    assert html.count("checked") == 3
    # Each pre-selected option's input should have `checked`
    for option in ["Tool name", "Owner", "Cost"]:
        idx = html.index(f'value="{option}"')
        input_start = html.rfind("<input", 0, idx)
        input_end = html.index(">", idx)
        assert "checked" in html[input_start:input_end]


def test_multi_select_no_prior_answer_no_checked(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_multi_select.html")
    ctx = {**base_context, "question": _ms_question()}
    html = tpl.render(Context(ctx))
    assert "checked" not in html


def test_multi_select_shows_select_all_that_apply_hint(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_multi_select.html")
    ctx = {**base_context, "question": _ms_question()}
    html = tpl.render(Context(ctx))
    assert "Select all that apply" in html


def test_multi_select_emits_htmx_and_csrf(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_multi_select.html")
    question = _ms_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    assert 'hx-post="/q/answer/T1-B-001/"' in html
    assert 'hx-target="#question-shell"' in html
    assert 'data-question-type="MS"' in html
    assert 'name="csrfmiddlewaretoken"' in html


# ============================================================================
# Likert partial
# ============================================================================

def test_likert_renders_five_radio_inputs(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_likert.html")
    question = _l5_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    assert html.count('type="radio"') == 5
    assert html.count('name="answer"') == 5


def test_likert_renders_anchored_endpoint_labels(engine, base_context):
    """Production data has L5 questions with anchored endpoints like
    "1 (not at all)" and "5 (strongly trust)". The partial renders the
    full labels straight from question.options."""
    tpl = engine.get_template("questionnaire/partials/_question_likert.html")
    question = _l5_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    assert "1 (not at all)" in html
    assert "5 (strongly trust)" in html
    # Middle three are numeric only
    for v in ("2", "3", "4"):
        assert f'value="{v}"' in html


def test_likert_renders_numeric_only_labels(engine, base_context):
    """T1-G-010/G-011/G-012 use plain numeric labels."""
    tpl = engine.get_template("questionnaire/partials/_question_likert.html")
    question = {
        **_l5_question(),
        "id": "T1-G-010",
        "options": ["1", "2", "3", "4", "5"],
    }
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    assert html.count('type="radio"') == 5
    for v in ("1", "2", "3", "4", "5"):
        assert f'value="{v}"' in html


def test_likert_prior_answer_preselects_radio(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_likert.html")
    question = _l5_question()
    ctx = {
        **base_context,
        "question": question,
        "prior_answer": {"selected": "3"},
    }
    html = tpl.render(Context(ctx))

    assert html.count("checked") == 1
    # The "3" radio is checked
    three_idx = html.index('value="3"')
    input_start = html.rfind("<input", 0, three_idx)
    input_end = html.index(">", three_idx)
    assert "checked" in html[input_start:input_end]


def test_likert_uses_horizontal_layout_class(engine, base_context):
    """The Likert partial visually distinguishes itself from vertical
    single-select via a flex layout class. This is a structural assert
    to lock the visual contract."""
    tpl = engine.get_template("questionnaire/partials/_question_likert.html")
    ctx = {**base_context, "question": _l5_question()}
    html = tpl.render(Context(ctx))

    # The .srj-question--likert root class is the visual hook
    assert "srj-question--likert" in html
    # Flex layout for horizontal scale
    assert "srj-question__likert" in html


def test_likert_emits_htmx_and_csrf(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_likert.html")
    question = _l5_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    assert 'hx-post="/q/answer/T1-B-001/"' in html
    assert 'data-question-type="L5"' in html
    assert 'name="csrfmiddlewaretoken"' in html


# ============================================================================
# Shared contract — fragment must NOT extend base.html
# ============================================================================

@pytest.mark.parametrize("partial", [
    "_question_single_select.html",
    "_question_multi_select.html",
    "_question_likert.html",
])
def test_partial_is_a_fragment_not_a_full_page(partial):
    """The partials are HTMX swap targets — they must render as
    fragments, NOT as full HTML documents. A {% extends %} tag would
    break the swap pattern."""
    path = TEMPLATES_DIR / "questionnaire" / "partials" / partial
    raw = path.read_text(encoding="utf-8")
    assert "{% extends" not in raw
    assert "<html" not in raw.lower()
    assert "<head" not in raw.lower()
    assert "<body" not in raw.lower()
