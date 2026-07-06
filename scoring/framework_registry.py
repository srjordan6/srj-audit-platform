"""Framework registry — external frameworks that Tier 1 questions map to.

Source of truth: `frameworks` table in the production DB. This module mirrors
the Priority 1 launch batch (5 frameworks) as immutable constants for use
in scoring, report rendering, and question_bank validation.

Additions/edits to the registry go through SRJ MCP writes against the DB,
then this module gets updated in a coordinated commit.
"""

from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# Priority 1 launch batch (matches frameworks table WHERE priority = 1)
# ---------------------------------------------------------------------------

PRIORITY_1_FRAMEWORKS: dict[str, dict] = {
    "sr-11-7": {
        "name": "SR 11-7 Guidance on Model Risk Management",
        "category": "guidance",
        "priority": 1,
    },
    "iso-42001": {
        "name": "ISO/IEC 42001 AI Management System",
        "category": "standard",
        "priority": 1,
    },
    "nist-ai-rmf": {
        "name": "NIST AI Risk Management Framework",
        "category": "standard",
        "priority": 1,
    },
    "eu-ai-act": {
        "name": "EU AI Act",
        "category": "regulation",
        "priority": 1,
    },
    "nist-csf-2": {
        "name": "NIST Cybersecurity Framework 2.0",
        "category": "standard",
        "priority": 1,
    },
}


# ---------------------------------------------------------------------------
# Internal aggregator IDs (already in questions.framework_mappings)
# ---------------------------------------------------------------------------

INTERNAL_AGGREGATOR_IDS = frozenset({
    "v1_audit",
    "v2_readiness",
    "v3_governance",
    "efficiency",
    "context",
    "lead_gen",
})


# ---------------------------------------------------------------------------
# Valid categories
# ---------------------------------------------------------------------------

VALID_CATEGORIES = frozenset({"regulation", "standard", "guidance"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def all_framework_ids() -> frozenset[str]:
    """Return every ID valid in questions.framework_mappings.framework."""
    return frozenset(PRIORITY_1_FRAMEWORKS.keys()) | INTERNAL_AGGREGATOR_IDS


def is_valid_framework_id(framework_id: str) -> bool:
    """Return True if this ID exists as external framework OR internal aggregator."""
    return framework_id in all_framework_ids()


def is_external_framework(framework_id: str) -> bool:
    """Return True if this is a regulation/standard/guidance (not internal aggregator)."""
    return framework_id in PRIORITY_1_FRAMEWORKS


def get_framework(framework_id: str) -> Optional[dict]:
    """Return {name, category, priority} or None if not in registry."""
    return PRIORITY_1_FRAMEWORKS.get(framework_id)


def get_display_name(framework_id: str) -> Optional[str]:
    """Return canonical display name for report rendering."""
    fw = get_framework(framework_id)
    return fw["name"] if fw else None


def frameworks_by_category(category: str) -> list[str]:
    """Return list of framework IDs matching this category."""
    if category not in VALID_CATEGORIES:
        return []
    return [
        fw_id for fw_id, fw in PRIORITY_1_FRAMEWORKS.items()
        if fw["category"] == category
    ]


def load_registry_from_db(cursor) -> list[dict]:
    """Read all active frameworks from the DB.

    Used by Django admin / management commands to reconcile the in-memory
    constants above with the production table.
    """
    cursor.execute(
        "SELECT id, name, description, category, priority, active "
        "FROM frameworks WHERE active = TRUE ORDER BY priority, id"
    )
    return [
        {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "category": row[3],
            "priority": row[4],
            "active": row[5],
        }
        for row in cursor.fetchall()
    ]
