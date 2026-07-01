"""
Unit tests for the two MATRIX question partials:
  - _question_matrix_grid.html    (Pattern A: T1-B-017, T1-D-001)
  - _question_matrix_choice.html  (Pattern B: T1-F-002)

Coverage focus
--------------
Both partials:
- Render question text and ID
- Emit a horizontally-scrollable Bootstrap table
- Row and column headers match production data
- HTMX + CSRF pattern matches other partials
- The partial is a fragment (no extends, no <html>/<head>/<body>)
- data-matrix-pattern attribute exposes the discriminator

Pattern A (matrix_grid) specifically:
- Emits a text input per row for the respondent's row name
- Uses the placeholder from matrix_rows on each row-name input
- For each (row, column) pair, emits a radio group with the cell options
  drawn from extended_metadata.matrix_cell_options
- Radio names encode (row_index, col_index) rather than labels

Pattern B (matrix_choice) specifically:
- Row headers show fixed labels from matrix_rows (no editable input)
- Each row has ONE radio group across the columns
- Radio names use "row_<index>" so all radios in a row share a name
- Column labels appear as radio values

The three production MATRIX questions exercise all these behaviors:
  T1-B-017 — 3 tool rows × 10 attribute columns × 3 cell options
  T1-D-001 — 3 use-case rows × 6 metric columns × 3 cell options
  T1-F-002 — 7 governance-item rows, 4 choice columns per row
"""

from __future__ import annotations

import html as html_lib
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
        "submit_url": "/q/answer/T1-B-017/",
        "swap_target": "#question-shell",
        "csrf_token": "fake-csrf",
    }


# Production-shaped fixtures for the three MATRIX questions

def _matrix_grid_tools_question() -> dict:
    """T1-B-017 — 3 tools × 10 attributes × Y/N/DK cells."""
    return {
        "id": "T1-B-017",
        "question_type": "MATRIX",
        "question_text": (
            "For the top 3 AI tools by spend or strategic importance in "
            "your company, indicate which of the following apply:"
        ),
        "required": True,
        "matrix_rows": ["Tool 1", "Tool 2", "Tool 3"],
        "matrix_columns": [
            "The tool has a documented business purpose",
            "The tool has a named owner accountable for outcomes",
            "The tool's cost is documented",
            "The tool's performance is measured against a defined outcome",
            "Someone can describe what data the tool accesses",
            "The vendor's data-handling terms have been reviewed in the past 12 months",
            "The tool was approved through a formal process before deployment",
            "The tool's continued use has been justified in the past 12 months",
            "An AI/Software bill of materials is documented for this tool",
            "Vendor flow-down clauses match downstream regulatory requirements (BAA, GLBA, DTSA, CMMC)",
        ],
        "extended_metadata": {
            "matrix_cell_options": ["Yes", "No", "Don't know"],
        },
    }


def _matrix_grid_usecases_question() -> dict:
    """T1-D-001 — 3 use cases × 6 metrics × Y/N/DK cells."""
    return {
        "id": "T1-D-001",
        "question_type": "MATRIX",
        "question_text": (
            "For the company's top 3 AI use cases by spend or strategic "
            "importance, indicate which apply (past 3 months):"
        ),
        "required": True,
        "matrix_rows": ["Use case 1", "Use case 2", "Use case 3"],
        "matrix_columns": [
            "Success metrics are defined",
            "Metrics are tied to specific business outcomes",
            "Baseline measurements from before AI deployment exist",
            "Performance is reviewed on a defined cadence",
            "AI artifact registry exists (model card, training data lineage, evaluation results, version history)",
            "Documented risk owner is accountable for this use case",
        ],
        "extended_metadata": {
            "matrix_cell_options": ["Yes", "No", "Don't know"],
            "matrix_row_input_type": "respondent_provides_name",
        },
    }


def _matrix_choice_governance_question() -> dict:
    """T1-F-002 — 7 governance items × 4 choice columns."""
    return {
        "id": "T1-F-002",
        "question_type": "MATRIX",
        "question_text": (
            "For each of the following governance structures, indicate "
            "the current state (past 3 months):"
        ),
        "required": True,
        "matrix_rows": [
            "Named executive accountable for AI outcomes",
            "AI as a standing topic at executive meetings",
            "Board has received AI reporting",
            "AI steering committee or governance body",
            "Board minutes from last 12 months document AI risk discussion",
            "Audit committee has reviewed AI-specific risks in the last 12 months",
            "Board AI competency disclosed in proxy or board-skills matrix",
        ],
        "matrix_columns": [
            "Yes — formal", "Yes — informal", "No", "Don't know",
        ],
        "extended_metadata": {
            "matrix_cell_options": ["selected", "not_selected"],
            "matrix_input_pattern": "single_selection_per_row",
        },
    }


# ============================================================================
# Pattern A — matrix_grid
# ============================================================================

def test_grid_renders_question_text_and_id(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_matrix_grid.html")
    ctx = {**base_context, "question": _matrix_grid_tools_question()}
    html = tpl.render(Context(ctx))
    assert "T1-B-017" in html
    assert "top 3 AI tools by spend" in html


def test_grid_uses_table_responsive_wrapper(engine, base_context):
    """Matrix layouts are horizontally scrollable on mobile."""
    tpl = engine.get_template("questionnaire/partials/_question_matrix_grid.html")
    ctx = {**base_context, "question": _matrix_grid_tools_question()}
    html = tpl.render(Context(ctx))
    assert "table-responsive" in html
    assert "<table" in html


def test_grid_column_headers_are_all_attributes(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_matrix_grid.html")
    question = _matrix_grid_tools_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))
    # Django autoescapes apostrophes and other special chars — escape
    # the expected string the same way before comparing
    for column in question["matrix_columns"]:
        assert html_lib.escape(column) in html


def test_grid_emits_row_name_input_per_row(engine, base_context):
    """Pattern A: respondent-provides-name rows get a text input each."""
    tpl = engine.get_template("questionnaire/partials/_question_matrix_grid.html")
    question = _matrix_grid_tools_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    assert html.count('name="row_name_0"') == 1
    assert html.count('name="row_name_1"') == 1
    assert html.count('name="row_name_2"') == 1
    # Placeholders match the matrix_rows values
    assert 'placeholder="Tool 1"' in html
    assert 'placeholder="Tool 2"' in html
    assert 'placeholder="Tool 3"' in html


def test_grid_cell_options_from_extended_metadata(engine, base_context):
    """Each cell renders a radio group with the cell_options from
    extended_metadata.matrix_cell_options."""
    tpl = engine.get_template("questionnaire/partials/_question_matrix_grid.html")
    question = _matrix_grid_tools_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    # 3 rows × 10 columns × 3 cell options = 90 radio inputs
    assert html.count('type="radio"') == 3 * 10 * 3


def test_grid_cell_radio_names_encode_row_and_col_index(engine, base_context):
    """Cell radios use name="cell_<row_index>_<col_index>" so all 3
    radio options for a single cell share a name (mutually exclusive)."""
    tpl = engine.get_template("questionnaire/partials/_question_matrix_grid.html")
    ctx = {**base_context, "question": _matrix_grid_tools_question()}
    html = tpl.render(Context(ctx))

    # For row 0, column 0: exactly 3 radios (one per cell option)
    assert html.count('name="cell_0_0"') == 3
    # For row 2, column 9 (last cell): exactly 3 radios
    assert html.count('name="cell_2_9"') == 3


def test_grid_pattern_discriminator_attr(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_matrix_grid.html")
    ctx = {**base_context, "question": _matrix_grid_tools_question()}
    html = tpl.render(Context(ctx))
    assert 'data-matrix-pattern="grid"' in html


def test_grid_handles_use_case_variant(engine, base_context):
    """T1-D-001 has different rows/columns but the same Grid pattern.
    The partial must not hardcode 'Tool 1' or column counts."""
    tpl = engine.get_template("questionnaire/partials/_question_matrix_grid.html")
    question = _matrix_grid_usecases_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    assert 'placeholder="Use case 1"' in html
    assert 'placeholder="Use case 2"' in html
    assert 'placeholder="Use case 3"' in html

    # T1-D-001 has 6 columns → 3 rows × 6 columns × 3 cell options = 54 radios
    assert html.count('type="radio"') == 3 * 6 * 3


def test_grid_emits_htmx_and_csrf(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_matrix_grid.html")
    ctx = {**base_context, "question": _matrix_grid_tools_question()}
    html = tpl.render(Context(ctx))
    assert 'hx-post="/q/answer/T1-B-017/"' in html
    assert 'data-question-type="MATRIX"' in html
    assert 'name="csrfmiddlewaretoken"' in html


# ============================================================================
# Pattern B — matrix_choice
# ============================================================================

def test_choice_renders_question_text_and_id(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_matrix_choice.html")
    ctx = {**base_context, "question": _matrix_choice_governance_question()}
    html = tpl.render(Context(ctx))
    assert "T1-F-002" in html
    assert "governance structures" in html


def test_choice_row_labels_are_fixed_not_editable(engine, base_context):
    """Pattern B: row labels are static text, not text inputs."""
    tpl = engine.get_template("questionnaire/partials/_question_matrix_choice.html")
    question = _matrix_choice_governance_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    # No row_name text inputs
    assert 'name="row_name_' not in html
    # Row labels appear as text
    for row in question["matrix_rows"]:
        assert row in html


def test_choice_one_radio_group_per_row(engine, base_context):
    """Pattern B: each row has ONE radio group (mutually exclusive
    across columns). Radios in a row share name="row_<index>"."""
    tpl = engine.get_template("questionnaire/partials/_question_matrix_choice.html")
    question = _matrix_choice_governance_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    # 7 rows × 4 columns = 28 radios total
    assert html.count('type="radio"') == 7 * 4
    # Each row has 4 radios sharing a single name
    for i in range(7):
        assert html.count(f'name="row_{i}"') == 4


def test_choice_radio_values_are_column_labels(engine, base_context):
    """Radio value = the column label posted back as the row's answer."""
    tpl = engine.get_template("questionnaire/partials/_question_matrix_choice.html")
    question = _matrix_choice_governance_question()
    ctx = {**base_context, "question": question}
    html = tpl.render(Context(ctx))

    for column in question["matrix_columns"]:
        # Django autoescapes special chars in attribute values
        assert f'value="{html_lib.escape(column)}"' in html


def test_choice_pattern_discriminator_attr(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_matrix_choice.html")
    ctx = {**base_context, "question": _matrix_choice_governance_question()}
    html = tpl.render(Context(ctx))
    assert 'data-matrix-pattern="choice"' in html


def test_choice_emits_htmx_and_csrf(engine, base_context):
    tpl = engine.get_template("questionnaire/partials/_question_matrix_choice.html")
    ctx = {**base_context, "question": _matrix_choice_governance_question()}
    html = tpl.render(Context(ctx))
    assert 'hx-post="/q/answer/T1-B-017/"' in html
    assert 'data-question-type="MATRIX"' in html
    assert 'name="csrfmiddlewaretoken"' in html


# ============================================================================
# Shared fragment contract
# ============================================================================

@pytest.mark.parametrize("partial", [
    "_question_matrix_grid.html",
    "_question_matrix_choice.html",
])
def test_matrix_partial_is_a_fragment(partial):
    """Both matrix partials are fragments — no extends, no full-page tags."""
    raw = (TEMPLATES_DIR / "questionnaire" / "partials" / partial).read_text(encoding="utf-8")
    assert "{% extends" not in raw
    assert "<html" not in raw.lower()
    assert "<head" not in raw.lower()
    assert "<body" not in raw.lower()
