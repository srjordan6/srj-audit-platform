"""Four-Page Pack render (spec S.10) against a fake cursor and the real scorer."""
from __future__ import annotations

import os
from datetime import date
from unittest import mock

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "audit_platform.settings.base")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("DATABASE_URL", "postgresql://u:p@localhost/x")
django.setup()

from questionnaire.aiitsa_question_bank import AIITSA_QUESTIONS
from reports import aiitsa_render


class _Cur:
    def __init__(self, rows_by_call):
        self.calls, self.rows_by_call = 0, rows_by_call

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None): self._last = sql
    def fetchone(self):
        return ("c1", "Pack Test Co", "Software", "26-100", "aiitsa")
    def fetchall(self):
        if "FROM responses" in self._last:
            return self.rows_by_call["responses"]
        return self.rows_by_call.get("history", [])


def _answers(mix):
    rows = []
    for i, q in enumerate(AIITSA_QUESTIONS):
        v = mix[i % len(mix)]
        rows.append((q["id"], {"selected": v}, v == "Don't know", "CISO", "r1"))
    return rows


@pytest.fixture
def ctx():
    cur = _Cur({"responses": _answers(["No", "Partially", "Don't know"]), "history": [(date(2026, 6, 1), 12.5)]})
    with mock.patch.object(aiitsa_render, "connection") as conn:
        conn.cursor.return_value = cur
        return aiitsa_render.build_aiitsa_context("e1", assessed_on=date(2026, 9, 27))


def test_context_has_four_pages_and_appendix(ctx):
    assert ctx["baseline"]["level_label"] in ("Absent", "Partial")
    assert len(ctx["areas"]) == 7 and len(ctx["visibility"]) == 6
    assert len(ctx["crosswalk"]) == 7 and len(ctx["roadmap"]) == 8
    assert len(ctx["appendix"]) == 143
    assert ctx["history"] == [{"date": date(2026, 6, 1), "score": 12.5}]
    assert "Don't know" in ctx["exposure"] and "2026-09-27" in ctx["exposure"]


def test_template_renders_without_trademark_on_instrument_names(ctx):
    from django.template.loader import render_to_string
    html = render_to_string("reports/aiitsa_pack.html", ctx)
    assert "AI IT Security Audit&trade;" in html
    for name in ("Visibility Triangle", "Four-Page Pack", "Defensible AI Security Baseline", "AI Red Button"):
        assert name in html
        assert f"{name}&trade;" not in html and f"{name}\u2122" not in html
    assert "Compared to what?" in html and "2026-06-01" in html


def test_score_payload_shape(ctx):
    p = aiitsa_render.aiitsa_score_payload(ctx)
    assert p["overall"]["assessed_on"] == "2026-09-27"
    assert p["overall"]["maturity_label"] in ("Absent", "Partial")
    assert len(p["items"]) == 7 and all("score_0_100" in i and "maturity_level" in i for i in p["items"])
    assert 1 <= len(p["gaps"]) <= 3
