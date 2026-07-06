"""CSV parser for framework mapping data.

Expected CSV format (long form, one row per mapping):
    question_id,framework,weight,dimension
    T1-A-001,iso-42001,3,governance
    T1-A-001,eu-ai-act,2,risk
    T1-B-005,nist-ai-rmf,4,ai_risk

Groups rows by question_id and returns dict compatible with
mapping_loader.apply_framework_mappings().
"""

from __future__ import annotations

import csv
from io import StringIO
from typing import IO


REQUIRED_COLUMNS = frozenset({"question_id", "framework", "weight", "dimension"})


def parse_mapping_csv(source: IO | str) -> dict[str, list[dict]]:
    """Parse CSV text or file-like into {question_id: [entry, ...]} dict.

    Raises ValueError on missing required columns or non-numeric weight.
    """
    if isinstance(source, str):
        source = StringIO(source)

    reader = csv.DictReader(source)
    if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")

    mappings: dict[str, list[dict]] = {}
    for row_num, row in enumerate(reader, start=2):
        qid = row["question_id"].strip()
        framework = row["framework"].strip()
        dimension = row["dimension"].strip()
        weight_raw = row["weight"].strip()

        if not qid or not framework:
            continue  # skip blank rows

        try:
            weight = float(weight_raw) if "." in weight_raw else int(weight_raw)
        except ValueError:
            raise ValueError(
                f"row {row_num}: weight '{weight_raw}' is not numeric"
            )

        entry = {"framework": framework, "weight": weight, "dimension": dimension}
        mappings.setdefault(qid, []).append(entry)

    return mappings
