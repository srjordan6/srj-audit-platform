"""
Shared fixtures for scoring framework tests.

Design notes
------------
The four framework aggregators in `scoring/frameworks/*.py` use ATTRIBUTE
access on questions (`question.framework_mappings`, `question.id`,
`question.section`, `question.subsection`, `question.question_type`,
`question.scoring_overrides`). Production `questionnaire.question_bank.QUESTIONS`
holds plain dicts; the runtime adapter (engine.py) wraps each in
SimpleNamespace before passing through. Tests do the same wrap directly
so they exercise the aggregator's intended contract without depending
on engine.py's DB-backed loader.

`ResponseRecord` is a dataclass exported by each framework module
(identical shape across all four). Tests import it from one of them
(v1_audit) and use the same instance for all framework tests — the
fields are positional-compatible.

These fixtures intentionally produce MINIMAL synthetic questions, not
copies of production rows. The aggregator only inspects a handful of
fields; the rest are populated with sensible defaults so the fixture
factories stay short.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from scoring.frameworks.v1_audit import ResponseRecord


@pytest.fixture
def make_question():
    """Factory that returns a SimpleNamespace question matching the schema shape.

    Usage:
        q = make_question(
            'Q1',
            framework='v1_audit',
            dimension='tool_inventory',
            sub_component='inventory_exists',
        )

    Override any field via kwargs. Multiple framework_mappings can be
    supplied via the `mappings` kwarg (list of dicts); when provided it
    overrides the default single-mapping shorthand.
    """
    def _make(
        qid: str,
        *,
        framework: str = "v1_audit",
        dimension: str | None = None,
        sub_component: str | None = None,
        weight: float = 1.0,
        mappings: list[dict] | None = None,
        question_type: str = "YN",
        section: str = "B",
        subsection: str | None = None,
        sequence_number: int = 1,
        options: list[str] | None = None,
        matrix_rows: list | None = None,
        matrix_columns: list | None = None,
        role_visibility: list[str] | None = None,
        scoring_weight: Decimal = Decimal("1.00"),
        scoring_overrides: dict | None = None,
        extended_metadata: dict | None = None,
        question_text: str = "Test question",
    ) -> SimpleNamespace:
        if mappings is None:
            if dimension is None:
                raise ValueError(
                    "make_question requires either `dimension` (shorthand) "
                    "or `mappings` (list of framework_mappings dicts)"
                )
            shorthand = {
                "framework": framework,
                "weight": weight,
            }
            if framework == "v1_audit":
                shorthand["dimension"] = dimension
                if sub_component is not None:
                    shorthand["sub_component"] = sub_component
            elif framework == "v2_readiness":
                shorthand["module"] = dimension
            elif framework == "v3_governance":
                shorthand["step"] = dimension
            elif framework == "efficiency":
                shorthand["component"] = dimension
            else:
                shorthand["dimension"] = dimension
                if sub_component is not None:
                    shorthand["sub_component"] = sub_component
            mappings = [shorthand]

        return SimpleNamespace(
            id=qid,
            tier="tier_1",
            section=section,
            subsection=subsection,
            sequence_number=sequence_number,
            question_text=question_text,
            question_type=question_type,
            options=options if options is not None else ["Yes", "No", "Don't know"],
            matrix_rows=matrix_rows,
            matrix_columns=matrix_columns,
            skip_logic=None,
            role_visibility=role_visibility if role_visibility is not None else ["all"],
            required=True,
            scoring_weight=scoring_weight,
            framework_mappings=mappings,
            notes=None,
            is_active=True,
            scoring_overrides=scoring_overrides,
            extended_metadata=extended_metadata,
        )

    return _make


@pytest.fixture
def make_response():
    """Factory that returns a ResponseRecord for a given question id.

    Usage:
        r = make_response('Q1', 'Yes')
        r = make_response('Q1', "Don't know", is_dk=True)
        r = make_response('Q1', 'Yes', has_attachments=True)

    `answer_value` is passed through as-is. For SS / MS / YN questions
    that's typically a plain string matching one of the options; for
    NR it's a dict like {"value": 42}; for L5 it's an int 1-5. Tests
    that need a specific shape should pass it explicitly.
    """
    def _make(
        qid: str,
        answer_value: Any,
        *,
        is_dk: bool = False,
        has_note: bool = False,
        has_attachments: bool = False,
    ) -> ResponseRecord:
        return ResponseRecord(
            question_id=qid,
            answer_value=answer_value,
            is_dont_know=is_dk,
            has_note=has_note,
            has_attachments=has_attachments,
        )

    return _make
