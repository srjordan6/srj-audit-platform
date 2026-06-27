"""
apply_od15_to_bank.py — One-shot patch script.

Synchronizes audit_platform/questionnaire/question_bank.py with the
production OD-15 changes by inserting "Other (specify)" into the options
arrays of 10 questions. Run once after the production DDL has been
applied; safe to re-run (idempotent — second run is a no-op).

USAGE
-----

    # From repo root, with the bank at the conventional path:
    python apply_od15_to_bank.py

    # Or pass an explicit path:
    python apply_od15_to_bank.py audit_platform/questionnaire/question_bank.py

    # Dry-run (print diffs without writing):
    python apply_od15_to_bank.py --dry-run

WHAT IT DOES
------------

1. Parses question_bank.py with the `ast` module
2. Locates every `Question(...)` call whose `id=` matches a target ID
3. For each, reads the existing `options=[...]` list and computes a new
   list with "Other (specify)" inserted immediately before the first
   "None of these" / "Don't know" / "Decline to answer" entry
4. Surgically rewrites those list literals in the source text, preserving
   surrounding code and indentation
5. Re-parses the result to confirm it's still valid Python
6. Writes a .bak backup, then writes the patched file

Idempotent: questions that already have "Other (specify)" are skipped.

WHY AST + TEXT REPLACEMENT
--------------------------

`ast.parse` gives us line/col offsets robust against any formatting
variation. `ast.unparse` would round-trip the entire file, losing
comments and normalizing whitespace — destructive. So we use ast to
FIND the list nodes' spans, then rewrite just those spans textually.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TARGET_QUESTION_IDS = {
    "T1-A-011", "T1-A-012", "T1-A-013",
    "T1-B-002", "T1-B-019",
    "T1-C-002", "T1-C-007",
    "T1-E-009", "T1-E-029",
    "T1-G-005",
}

OTHER_OPTION = "Other (specify)"

# Prefixes (case-insensitive) that mark "tail" options. Other (specify)
# goes before the first one of these. If none are present, it goes at
# the end of the list.
TAIL_PREFIXES = ("none", "don't know", "decline to answer")


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def find_question_calls(tree: ast.AST) -> list[ast.Call]:
    """Return every Question(...) call node in the tree."""
    out: list[ast.Call] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id == "Question":
                out.append(node)
    return out


def get_keyword(call: ast.Call, name: str) -> ast.keyword | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw
    return None


def extract_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


# ---------------------------------------------------------------------------
# Patch computation
# ---------------------------------------------------------------------------

def is_tail_option(text: str) -> bool:
    s = text.strip().lower()
    return any(s.startswith(p) for p in TAIL_PREFIXES)


def compute_new_options(existing: list[str]) -> list[str]:
    """Insert OTHER_OPTION before the first tail option. Idempotent."""
    if OTHER_OPTION in existing:
        return existing
    new_list = list(existing)
    for i, opt in enumerate(new_list):
        if is_tail_option(opt):
            new_list.insert(i, OTHER_OPTION)
            return new_list
    new_list.append(OTHER_OPTION)
    return new_list


# ---------------------------------------------------------------------------
# Source-text rewriting
# ---------------------------------------------------------------------------

def python_string(s: str) -> str:
    """Emit a Python string literal, preferring double quotes."""
    if '"' not in s:
        return f'"{s}"'
    if "'" not in s:
        return f"'{s}'"
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def line_start_offsets(src: str) -> list[int]:
    """Cumulative offsets where each line begins. line_starts[0] == 0."""
    starts = [0]
    pos = 0
    for line in src.splitlines(keepends=True):
        pos += len(line)
        starts.append(pos)
    return starts


def detect_indents(
    src: str,
    opt_node: ast.List,
    lines: list[str],
) -> tuple[str, str]:
    """Return (inner_indent, closing_indent) matching the existing list style."""
    # Inner indent: column offset of the first existing element
    if opt_node.elts:
        first = opt_node.elts[0]
        inner = " " * first.col_offset
    else:
        inner = "    "

    # Closing indent: leading whitespace of the line containing the `]`
    closing_line = lines[opt_node.end_lineno - 1]
    closing_ws_len = len(closing_line) - len(closing_line.lstrip())
    # The `]` should be at column end_col_offset - 1; if leading whitespace
    # extends up to that column, the closing indent is fine. Otherwise fall
    # back to inner indent minus 4.
    if closing_ws_len >= opt_node.end_col_offset - 1:
        closing = " " * (opt_node.end_col_offset - 1)
    else:
        closing = " " * max(0, len(inner) - 4)

    return inner, closing


def format_options_block(
    options: list[str],
    inner_indent: str,
    closing_indent: str,
) -> str:
    """Render a multi-line options list literal with trailing comma."""
    items = ",\n".join(f"{inner_indent}{python_string(o)}" for o in options)
    return f"[\n{items},\n{closing_indent}]"


# ---------------------------------------------------------------------------
# Main patch routine
# ---------------------------------------------------------------------------

def patch_file(path: Path, dry_run: bool = False) -> int:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f"ERROR: {path} does not parse: {e}", file=sys.stderr)
        return 2

    lines = src.splitlines(keepends=True)
    line_starts = line_start_offsets(src)

    def offset_of(lineno: int, col: int) -> int:
        return line_starts[lineno - 1] + col

    # Locate edits
    edits: list[tuple[str, ast.List, list[str], list[str]]] = []
    for call in find_question_calls(tree):
        id_kw = get_keyword(call, "id")
        if id_kw is None:
            continue
        q_id = extract_string(id_kw.value)
        if q_id not in TARGET_QUESTION_IDS:
            continue
        opt_kw = get_keyword(call, "options")
        if opt_kw is None or not isinstance(opt_kw.value, ast.List):
            print(f"  [skip] {q_id}: no options list literal found")
            continue
        existing = [extract_string(e) for e in opt_kw.value.elts]
        if any(o is None for o in existing):
            print(f"  [skip] {q_id}: non-string options")
            continue
        new_opts = compute_new_options(existing)  # type: ignore[arg-type]
        if new_opts == existing:
            print(f"  [skip] {q_id}: already patched")
            continue
        edits.append((q_id, opt_kw.value, existing, new_opts))  # type: ignore[arg-type]

    if not edits:
        print("question_bank.py is already in sync with production. Nothing to do.")
        return 0

    print(f"Will patch {len(edits)} questions:")
    for q_id, _, existing, new_opts in edits:
        print(f"  {q_id}: {len(existing)} → {len(new_opts)} options")

    # Apply edits in REVERSE order so earlier offsets remain valid
    edits.sort(key=lambda e: -offset_of(e[1].lineno, e[1].col_offset))
    new_src = src
    for q_id, opt_node, _existing, new_opts in edits:
        start = offset_of(opt_node.lineno, opt_node.col_offset)
        end = offset_of(opt_node.end_lineno, opt_node.end_col_offset)
        inner, closing = detect_indents(src, opt_node, lines)
        replacement = format_options_block(new_opts, inner, closing)
        new_src = new_src[:start] + replacement + new_src[end:]

    # Validate the patched source still parses
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print(f"\nERROR: patched output failed to re-parse: {e}", file=sys.stderr)
        print("Aborting; no files written.", file=sys.stderr)
        return 3

    if dry_run:
        print("\n[dry-run] All patches computed and re-parse cleanly. No files written.")
        return 0

    backup = path.with_suffix(path.suffix + ".bak")
    backup.write_text(src, encoding="utf-8")
    path.write_text(new_src, encoding="utf-8")
    print(f"\nWrote:  {path}")
    print(f"Backup: {backup}")
    print()
    print("Verify with:  python manage.py load_questions --dry-run")
    print("Expected:     0 inserts, 0 updates (production already matches)")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def find_default_path() -> Path | None:
    candidates = [
        Path("audit_platform/questionnaire/question_bank.py"),
        Path("questionnaire/question_bank.py"),
        Path("question_bank.py"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]

    if args:
        path = Path(args[0])
    else:
        path = find_default_path()
        if path is None:
            print(
                "Could not find question_bank.py in any of the standard locations.\n"
                "Pass an explicit path as the first argument.",
                file=sys.stderr,
            )
            return 1

    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    print(f"Patching: {path}")
    if dry_run:
        print("[dry-run mode]")
    return patch_file(path, dry_run=dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
