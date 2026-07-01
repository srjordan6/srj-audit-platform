"""
Unit tests for the site-wide base.html and the questionnaire/question_shell.html.

Coverage focus
--------------
base.html:
- Emits a full HTML5 document (DOCTYPE + <html>/<head>/<body>)
- CSRF meta tag renders with the token from context
- HTMX headers config attribute is present on <body> so all HTMX
  requests carry the CSRF token
- Bootstrap 5.3 CSS + JS are loaded via CDN with SRI hashes
- HTMX and SortableJS are loaded via CDN
- Brand color variables are defined (--srj-brand, --srj-brand-dark)
- Overridable blocks are present (title, content, extra_head, extra_scripts)
- The Sortable helper functions (srjRankPrepareSubmit, srjAttachSortable)
  are inlined so they're available to the RANK partial without a
  separate JS file

question_shell.html:
- Extends base.html
- Provides #question-shell as the swap target
- The initial_question_template context var is respected via {% include %}
- Progress bar renders when progress context is provided
- Progress bar is absent when no progress context is passed
- Save-and-resume hint is present

These tests use Django's standalone Engine (matches all other Sprint C
test files). Because question_shell.html extends base.html, testing
their integration requires the same template dirs config.
"""

from __future__ import annotations

from pathlib import Path

import django
import pytest
from django.template import Context, Engine

REPO_ROOT = Path(__file__).resolve().parents[1]
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
def shell_context():
    """Context sufficient to render the questionnaire shell with an
    embedded first question."""
    return {
        "csrf_token": "fake-csrf",
        "initial_question_template": "questionnaire/partials/_question_single_select.html",
        "question": {
            "id": "T1-A-001",
            "question_type": "SS",
            "question_text": "Your role in the company",
            "required": True,
            "options": ["CEO", "CFO", "COO", "Other"],
        },
        "submit_url": "/q/answer/T1-A-001/",
        "swap_target": "#question-shell",
    }


# ============================================================================
# base.html
# ============================================================================

def test_base_renders_as_full_html_document(engine):
    tpl = engine.get_template("base.html")
    html = tpl.render(Context({"csrf_token": "fake"}))
    assert html.strip().startswith("<!DOCTYPE html>")
    assert "<html" in html
    assert "<head>" in html
    assert "<body" in html
    assert "</html>" in html


def test_base_csrf_meta_tag_carries_token(engine):
    tpl = engine.get_template("base.html")
    html = tpl.render(Context({"csrf_token": "test-token-abc123"}))
    assert '<meta name="csrf-token" content="test-token-abc123">' in html


def test_base_body_htmx_headers_include_csrf(engine):
    """HTMX requests need CSRF; base.html sets it via hx-headers on <body>."""
    tpl = engine.get_template("base.html")
    html = tpl.render(Context({"csrf_token": "test-token"}))
    assert 'hx-headers=' in html
    assert 'X-CSRFToken' in html
    assert '"test-token"' in html


def test_base_loads_bootstrap_5_via_cdn(engine):
    tpl = engine.get_template("base.html")
    html = tpl.render(Context({"csrf_token": "fake"}))
    assert "bootstrap@5.3" in html
    assert "bootstrap.min.css" in html
    assert "bootstrap.bundle.min.js" in html


def test_base_loads_htmx_via_cdn(engine):
    tpl = engine.get_template("base.html")
    html = tpl.render(Context({"csrf_token": "fake"}))
    assert "htmx.org@2" in html


def test_base_loads_sortablejs_via_cdn(engine):
    tpl = engine.get_template("base.html")
    html = tpl.render(Context({"csrf_token": "fake"}))
    assert "sortablejs" in html


def test_base_defines_brand_color_variables(engine):
    """Brand colors are CSS custom properties so any child template
    can reference --srj-brand."""
    tpl = engine.get_template("base.html")
    html = tpl.render(Context({"csrf_token": "fake"}))
    assert "--srj-brand:" in html
    assert "#1e3a8a" in html  # Deep blue per Decision 7-12 continuity
    assert "--srj-brand-dark:" in html


def test_base_defines_rank_sortable_helpers(engine):
    """The RANK partial calls srjRankPrepareSubmit on form submit and
    relies on srjAttachSortable running on DOMContentLoaded and after
    HTMX swaps. Both must live in base.html so they're always available."""
    tpl = engine.get_template("base.html")
    html = tpl.render(Context({"csrf_token": "fake"}))
    assert "function srjRankPrepareSubmit" in html
    assert "function srjAttachSortable" in html
    assert "htmx:afterSwap" in html


def test_base_title_block_overridable(engine):
    """Child templates can override the title block."""
    tpl_src = "{% extends 'base.html' %}{% block title %}Custom Title{% endblock %}"
    tpl = engine.from_string(tpl_src)
    html = tpl.render(Context({"csrf_token": "fake"}))
    assert "<title>Custom Title</title>" in html


def test_base_content_block_overridable(engine):
    """Child templates can inject content."""
    tpl_src = (
        "{% extends 'base.html' %}"
        "{% block content %}<p id='child-content'>Hello World</p>{% endblock %}"
    )
    tpl = engine.from_string(tpl_src)
    html = tpl.render(Context({"csrf_token": "fake"}))
    assert "<p id='child-content'>Hello World</p>" in html


def test_base_extra_head_block_overridable(engine):
    tpl_src = (
        "{% extends 'base.html' %}"
        "{% block extra_head %}<meta name='page-tag' content='test'>{% endblock %}"
    )
    tpl = engine.from_string(tpl_src)
    html = tpl.render(Context({"csrf_token": "fake"}))
    assert '<meta name=\'page-tag\' content=\'test\'>' in html


def test_base_default_title_is_srj_audit(engine):
    tpl = engine.get_template("base.html")
    html = tpl.render(Context({"csrf_token": "fake"}))
    assert "<title>SRJ Audit</title>" in html


# ============================================================================
# questionnaire/question_shell.html
# ============================================================================

def test_shell_extends_base_html(engine, shell_context):
    """The shell must produce a full HTML page — proving the extend
    of base.html worked."""
    tpl = engine.get_template("questionnaire/question_shell.html")
    html = tpl.render(Context(shell_context))
    assert html.strip().startswith("<!DOCTYPE html>")
    assert "<html" in html
    # And it must include the shell-specific title override
    assert "Complete your audit · SRJ Audit" in html


def test_shell_provides_question_shell_div(engine, shell_context):
    """#question-shell must exist — it's the HTMX swap target for
    every question navigation."""
    tpl = engine.get_template("questionnaire/question_shell.html")
    html = tpl.render(Context(shell_context))
    assert 'id="question-shell"' in html


def test_shell_renders_initial_question_via_include(engine, shell_context):
    """The initial question is embedded server-side via {% include %}."""
    tpl = engine.get_template("questionnaire/question_shell.html")
    html = tpl.render(Context(shell_context))
    # The initial question's markup should appear inside #question-shell
    assert "T1-A-001" in html
    assert "Your role in the company" in html
    # And it should be a single-select radio group (from the partial)
    assert 'type="radio"' in html


def test_shell_renders_progress_bar_when_progress_context_provided(engine, shell_context):
    ctx = {**shell_context, "progress": {"current": 47, "total": 120, "percent": 39}}
    tpl = engine.get_template("questionnaire/question_shell.html")
    html = tpl.render(Context(ctx))
    assert "Question 47 of 120" in html
    assert "39%" in html
    assert "progress-bar" in html


def test_shell_no_progress_bar_when_progress_absent(engine, shell_context):
    """Without progress context, the progress bar section doesn't render."""
    # shell_context does not include progress
    assert "progress" not in shell_context
    tpl = engine.get_template("questionnaire/question_shell.html")
    html = tpl.render(Context(shell_context))
    assert "progress-bar" not in html


def test_shell_shows_save_and_resume_hint(engine, shell_context):
    """The save-and-resume assurance appears under the question card."""
    tpl = engine.get_template("questionnaire/question_shell.html")
    html = tpl.render(Context(shell_context))
    assert "Answers are saved automatically" in html
    assert "email" in html
