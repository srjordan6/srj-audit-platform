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


def get_tier_2_price_cents(size_bracket: str | None) -> int:
    """Price for a company size bracket. Unknown or missing bracket falls
    to the largest price, never the smallest: a mis-keyed bracket must not
    undercharge, and the buyer sees the amount before paying."""
    return TIER_2_PRICE_BRACKETS_CENTS.get((size_bracket or "").strip(), 750_000)


def tier_2_price_label(size_bracket: str | None) -> str:
    return f"${get_tier_2_price_cents(size_bracket) / 100:,.0f}"
