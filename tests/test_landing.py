"""Tests for marketing/landing.html. Standalone Engine — no Django settings."""

from __future__ import annotations

from pathlib import Path

from django.template import Context, Engine


TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _render():
    engine = Engine(dirs=[str(TEMPLATES_DIR)])
    return engine.get_template("marketing/landing.html").render(Context({}))


def test_landing_hero_670k():
    """The $670K hook — proven positioning per Part A."""
    assert "670" in _render()


def test_landing_cta_to_start():
    html = _render()
    assert 'href="/q/start/"' in html


def test_landing_has_two_ctas():
    """Hero CTA + bottom CTA."""
    assert _render().count('href="/q/start/"') >= 2


def test_landing_says_free():
    assert "free" in _render().lower()


def test_landing_states_price():
    assert "$399" in _render()


def test_landing_states_free_vs_paid_split():
    """Clear separation of what's free vs $399."""
    html = _render()
    assert "Headline Scores" in html
    assert "Four Framework PDFs" in html


def test_landing_extends_base():
    html = _render()
    # base.html emits DOCTYPE + CSRF meta
    assert html.strip().startswith("<!DOCTYPE html>") or html.strip().startswith("<html")


def test_landing_lists_priority_1_frameworks():
    """Priority 1 launch batch per Sprint E memory."""
    html = _render()
    for fw in ["SR 11-7", "ISO 42001", "NIST AI RMF", "EU AI Act", "NIST CSF 2.0"]:
        assert fw in html, f"Missing framework: {fw}"


def test_landing_references_srj_consulting_footer():
    assert "SRJ Consulting" in _render()


def test_landing_trademark_forms_correct():
    """Per locked trademark master list — V1 with 'The', V2/V4 with 'The', V3 without."""
    html = _render()
    assert "The AI Business Enablement Audit" in html
    assert "AI Readiness &amp; Performance Assessment" in html
    assert "AI Risk &amp; Governance Review" in html
    # V3 must NOT have leading "The"
    assert "The AI Risk" not in html


def test_landing_trademark_symbols_present():
    """All four canonical marks carry the ™ symbol."""
    html = _render()
    assert html.count("™") >= 4


def test_landing_no_forbidden_marks():
    """Descriptive instrument names — no invented marks."""
    html = _render()
    # These are not in the 79-mark portfolio
    assert "Visibility Triangle" not in html
    assert "Four-Page Pack" not in html


def test_landing_uses_brand_color_var():
    """base.html defines --srj-brand; landing must reference it, not hex-hardcode."""
    html = _render()
    assert "var(--srj-brand)" in html
