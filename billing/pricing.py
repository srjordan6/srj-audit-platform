"""Tier 2 pricing (Part B-1 S.2.2, DECISION LOCKED): by company size,
$1,000 per bracket, $2,500 to $7,500. Keyed on companies.size_bracket."""

from __future__ import annotations

TIER_2_PRICE_BRACKETS_CENTS: dict[str, int] = {
    "1-25": 250_000,
    "26-100": 350_000,
    "101-500": 450_000,
    "501-2000": 550_000,
    "2001-5000": 650_000,
    "5000+": 750_000,
}

# Part A Decision 7-3: Stripe Identity verification gates purchases over
# $5,000 (501+ employees). Not wired yet; the threshold lives here so the
# checkout can read it when billing/identity.py lands.
STRIPE_IDENTITY_REQUIRED_THRESHOLD_CENTS = 500_000


# OD-19 (2026-10-01): both audits at Tier 2 cost the bracket price plus the
# same bracket price less 25% for the second audit ($2,500 bracket =
# $4,375; $7,500 bracket = $13,125).
SECOND_AUDIT_DISCOUNT = 0.25


def _bracket_cents(size_bracket: str | None) -> int:
    return TIER_2_PRICE_BRACKETS_CENTS.get((size_bracket or "").strip(), 750_000)


def get_tier_2_price_cents(size_bracket: str | None, instrument: str | None = None) -> int:
    """Price for a company size bracket and what is bought. Unknown or
    missing bracket falls to the largest price, never the smallest: a
    mis-keyed bracket must not undercharge, and the buyer sees the amount
    before paying. "combined" is both audits with the second at 25% off."""
    one = _bracket_cents(size_bracket)
    if instrument == "combined":
        return one + int(round(one * (1 - SECOND_AUDIT_DISCOUNT)))
    return one


def tier_2_price_label(size_bracket: str | None, instrument: str | None = None) -> str:
    return f"${get_tier_2_price_cents(size_bracket, instrument) / 100:,.0f}"


def tier_2_price_table() -> list[dict]:
    """Rows for the start page: one audit and both audits, per bracket."""
    return [{"bracket": b, "one": f"${c / 100:,.0f}",
             "both": f"${get_tier_2_price_cents(b, 'combined') / 100:,.0f}"}
            for b, c in TIER_2_PRICE_BRACKETS_CENTS.items()]
