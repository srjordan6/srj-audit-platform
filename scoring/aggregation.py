"""Multi-respondent aggregation (Part B-3 S.2).

Combine N per-respondent framework results into one engagement-level
result per framework, and surface disagreement instead of averaging it
away.

  2.1  Role-weighted mean per dimension:
         agg(d) = sum_r score(r,d) * rw(role_r,d) * cov(r,d)
                / sum_r rw(role_r,d) * cov(r,d)
       rw from scoring.tier_2_role_weights; cov = answered/expected for
       that respondent on that dimension.
  2.2  Divergence: leadership vs workforce role-weighted means; flagged
       at |diff| >= DIVERGENCE_THRESHOLD and a one-step confidence
       penalty on the dimension.
  2.3  Minimum-contribution guard: a respondent's dimension score counts
       only if the total question weight they answered in it is
       >= MIN_DIM_WEIGHT (about one core or two standard questions).
  2.4  Item-level agreement: per-question standard deviation of raw
       scores across respondents; the most contested questions feed the
       report's "contested findings" and the reviewer.

The four framework result types have four shapes. Rather than four
aggregators, this walks each framework's item list generically (the
score field, the maturity/bracket helper, the composite formula and the
top-gap selector are the only per-framework facts, held in _FRAMEWORKS)
and rebuilds the frozen dataclasses with dataclasses.replace. The
aggregated result is the same type as a single-respondent result, so
reports and persistence need no new code path.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field, replace
from typing import Any

from scoring.frameworks import efficiency, v1_audit, v2_readiness, v3_governance
from scoring.tier_2_role_weights import LEADERSHIP, WORKFORCE, role_weight

DIVERGENCE_THRESHOLD = 20.0     # points on the 0-100 scale (B-3 S.2.2)
MIN_DIM_WEIGHT = 1.0            # summed question weight to count (B-3 S.2.3)
CONTESTED_TOP_N = 10

_CONF_ORDER = ["high", "medium", "low"]


# ----------------------------------------------------------------------------
# Output alongside the four results
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class DimensionAggregate:
    framework: str
    dimension: str
    score_0_100: float
    contributing: int              # respondents whose weight cleared the guard
    excluded: int                  # respondents present but below the guard / weight 0
    leadership_mean: float | None
    workforce_mean: float | None
    divergence: float | None       # leadership - workforce
    flagged: bool


@dataclass(frozen=True)
class ContestedQuestion:
    question_id: str
    respondents: int
    mean_0_1: float
    stdev_0_1: float


@dataclass(frozen=True)
class AggregationSummary:
    respondent_count: int
    roles: list[str]
    threshold: float
    min_dim_weight: float
    dimensions: list[DimensionAggregate] = field(default_factory=list)
    contested: list[ContestedQuestion] = field(default_factory=list)

    @property
    def flagged(self) -> list[DimensionAggregate]:
        return [d for d in self.dimensions if d.flagged]

    def as_dict(self) -> dict[str, Any]:
        return {
            "respondent_count": self.respondent_count,
            "roles": self.roles,
            "divergence_threshold": self.threshold,
            "min_dim_weight": self.min_dim_weight,
            "dimensions": [d.__dict__ for d in self.dimensions],
            "contested": [c.__dict__ for c in self.contested],
        }


# ----------------------------------------------------------------------------
# Per-framework facts
# ----------------------------------------------------------------------------

def _v1_composite(items):
    return sum(d.final_score_0_100 * v1_audit.COMPOSITE_WEIGHTS[d.name] for d in items)


def _eff_composite(items):
    return sum(c.score_0_100 * efficiency.COMPOSITE_WEIGHTS[c.name] for c in items)


_FRAMEWORKS: dict[str, dict[str, Any]] = {
    "v1_audit": {
        "items": "dimensions", "score": "final_score_0_100",
        "on_score": lambda item, s: {"final_score_0_100": s, "raw_score_0_100": s,
                                     "bracket": v1_audit.bracket_for_score(s)},
        "composite": _v1_composite,
        "on_composite": lambda s: {"composite_score_0_100": s,
                                   "composite_bracket": v1_audit.bracket_for_score(s)},
        "top_gaps": lambda items: v1_audit._identify_top_gaps(items, n=3),
    },
    "v2_readiness": {
        "items": "modules", "score": "score_0_100",
        "on_score": lambda item, s: {"score_0_100": s,
                                     "maturity_level": v2_readiness.maturity_for_score(s)[0],
                                     "maturity_label": v2_readiness.maturity_for_score(s)[1],
                                     "bracket": v2_readiness.maturity_for_score(s)[1]},
        "composite": v2_readiness._compute_cri,
        "on_composite": lambda s: {"cri_score_0_100": s,
                                   "cri_maturity_level": v2_readiness.maturity_for_score(s)[0],
                                   "cri_maturity_label": v2_readiness.maturity_for_score(s)[1],
                                   "cri_bracket": v2_readiness.maturity_for_score(s)[1]},
        "top_gaps": lambda items: v2_readiness._identify_top_gaps(items, n=3),
    },
    "v3_governance": {
        "items": "steps", "score": "score_0_100",
        "on_score": lambda item, s: {"score_0_100": s,
                                     "maturity_level": v3_governance.maturity_for_score(s)[0],
                                     "maturity_label": v3_governance.maturity_for_score(s)[1]},
        "composite": v3_governance._compute_composite,
        "on_composite": lambda s: {"composite_score_0_100": s,
                                   "composite_maturity_level": v3_governance.maturity_for_score(s)[0],
                                   "composite_maturity_label": v3_governance.maturity_for_score(s)[1]},
        "top_gaps": lambda items: v3_governance._identify_top_gaps(items, n=3),
        "extra_lists": ["cross_cutting_signals"],
    },
    "efficiency": {
        "items": "components", "score": "score_0_100",
        "on_score": lambda item, s: {"score_0_100": s, "bracket": efficiency.bracket_for_score(s)},
        "composite": _eff_composite,
        "on_composite": lambda s: {"composite_score_0_100": s,
                                   "composite_bracket": efficiency.bracket_for_score(s)},
        "top_gaps": lambda items: efficiency._identify_top_gaps(items, n=2),
    },
}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _answered(item) -> int:
    return getattr(item, "answered_count", getattr(item, "answered_question_count", 0))


def _expected(item) -> int:
    return getattr(item, "expected_count", getattr(item, "expected_question_count", 0))


def _cov(item) -> float:
    e = _expected(item)
    return min(_answered(item) / e, 1.0) if e else 0.0


def _contributions(item):
    """Every question contribution under an item. V1 dimensions keep theirs
    inside sub_components; the other frameworks keep them on the item."""
    pools = [getattr(item, "contributions", []) or []]
    for sc in getattr(item, "sub_components", []) or []:
        pools.append(sc.contributions)
    return [c for pool in pools for c in pool]


def _contrib_weight(item) -> float:
    """Total question weight the respondent actually answered in this item."""
    return sum(c.weight for c in _contributions(item)
               if not getattr(c.response_score, "excluded", False))


def _weighted_mean(pairs: list[tuple[float, float]]) -> float | None:
    den = sum(w for _, w in pairs)
    if den <= 0:
        return None
    return sum(v * w for v, w in pairs) / den


def _penalise(conf: str) -> str:
    i = _CONF_ORDER.index(conf) if conf in _CONF_ORDER else 1
    return _CONF_ORDER[min(i + 1, len(_CONF_ORDER) - 1)]


def _worst(confs: list[str]) -> str:
    known = [c for c in confs if c in _CONF_ORDER]
    return max(known, key=_CONF_ORDER.index) if known else "low"


def _merge_common(items: list, score_field: str, agg_score: float, flagged: bool) -> dict:
    """Fields every item type shares: counts, dk, confidence, contributions."""
    answered = sum(_answered(i) for i in items)
    expected = max((_expected(i) for i in items), default=0)
    dk = (sum(i.dk_ratio * _answered(i) for i in items) / answered) if answered else 0.0
    conf = _worst([i.confidence_level for i in items])
    if flagged:
        conf = _penalise(conf)
    out: dict[str, Any] = {"dk_ratio": dk, "confidence_level": conf}
    first = items[0]
    if hasattr(first, "answered_count"):
        out["answered_count"], out["expected_count"] = answered, expected
    else:
        out["answered_question_count"], out["expected_question_count"] = answered, expected
    if hasattr(first, "contributions"):
        out["contributions"] = [c for i in items for c in i.contributions]
    for f in ("attached_non_dk_count", "noted_only_non_dk_count",
              "explicit_contribution_count", "section_rule_contribution_count"):
        if hasattr(first, f):
            out[f] = sum(getattr(i, f) for i in items)
    return out


def _aggregate_items(framework: str, per_resp: list[tuple[str, list]], score_field: str,
                     on_score, key=lambda i: i.name, summary: list | None = None,
                     scale: float = 100.0) -> list:
    """per_resp: [(role, [items...]), ...]. Returns aggregated items in the
    first respondent's order."""
    by_name: dict[str, list[tuple[str, Any]]] = {}
    order: list[str] = []
    for role, items in per_resp:
        for it in items:
            k = key(it)
            if k not in by_name:
                by_name[k] = []
                order.append(k)
            by_name[k].append((role, it))

    out = []
    for k in order:
        entries = by_name[k]
        pairs, lead, work = [], [], []
        excluded = 0
        for role, it in entries:
            rw = role_weight(role, framework, k)
            w = rw * _cov(it)
            if w <= 0 or _contrib_weight(it) < MIN_DIM_WEIGHT:
                excluded += 1
                continue
            s = getattr(it, score_field)
            pairs.append((s, w))
            (lead if role in LEADERSHIP else work if role in WORKFORCE else []).append((s, w))
        agg = _weighted_mean(pairs)
        if agg is None:                      # nobody cleared the guard: plain mean of what exists
            raw = [getattr(it, score_field) for _, it in entries]
            agg = sum(raw) / len(raw) if raw else 0.0
        lm, wm = _weighted_mean(lead), _weighted_mean(work)
        div = (lm - wm) if (lm is not None and wm is not None) else None
        flagged = div is not None and abs(div) * (100.0 / scale) >= DIVERGENCE_THRESHOLD
        if summary is not None:
            summary.append(DimensionAggregate(
                framework=framework, dimension=k, score_0_100=agg * (100.0 / scale),
                contributing=len(pairs), excluded=excluded,
                leadership_mean=None if lm is None else lm * (100.0 / scale),
                workforce_mean=None if wm is None else wm * (100.0 / scale),
                divergence=None if div is None else div * (100.0 / scale), flagged=flagged))
        items = [it for _, it in entries]
        fields = _merge_common(items, score_field, agg, flagged)
        fields.update(on_score(items[0], agg))
        out.append(replace(items[0], **fields))
    return out


def _aggregate_v1_subcomponents(per_resp: list[tuple[str, list]]) -> list:
    """V1 dimensions carry sub_components (0-1 scale); aggregate those too so
    gap actions and report detail reflect all respondents."""
    return _aggregate_items(
        "v1_audit", per_resp, "weighted_mean_0_1",
        on_score=lambda item, s: {"weighted_mean_0_1": s},
        key=lambda sc: sc.sub_component, scale=1.0,
    )


def _contested(per_results: list[tuple[str, Any]], fw: str) -> list[ContestedQuestion]:
    """Per-question inter-respondent disagreement (B-3 S.2.4)."""
    spec = _FRAMEWORKS[fw]
    values: dict[str, list[float]] = {}
    for _, res in per_results:
        for it in getattr(res, spec["items"]):
            for c in _contributions(it):
                rs = c.response_score
                if getattr(rs, "excluded", False) or getattr(rs, "is_dont_know", False):
                    continue
                values.setdefault(c.question_id, []).append(float(rs.value))
    out = []
    for qid, vals in values.items():
        if len(vals) >= 2:
            out.append(ContestedQuestion(qid, len(vals), statistics.fmean(vals), statistics.pstdev(vals)))
    out.sort(key=lambda c: c.stdev_0_1, reverse=True)
    return out


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

def aggregate(per_respondent: list[tuple[str, tuple]]) -> tuple[tuple, AggregationSummary]:
    """per_respondent: [(role, (v1, v2, v3, eff)), ...] with N >= 2.

    Returns ((v1, v2, v3, eff), AggregationSummary) where each result is
    the same dataclass type as a single-respondent result.
    """
    if not per_respondent:
        raise ValueError("no respondent results to aggregate")
    roles = [r for r, _ in per_respondent]
    summary_dims: list[DimensionAggregate] = []
    contested: list[ContestedQuestion] = []
    aggregated = []

    for idx, fw in enumerate(("v1_audit", "v2_readiness", "v3_governance", "efficiency")):
        spec = _FRAMEWORKS[fw]
        per = [(role, results[idx]) for role, results in per_respondent]
        items = _aggregate_items(fw, [(r, getattr(res, spec["items"])) for r, res in per],
                                 spec["score"], spec["on_score"], summary=summary_dims)
        if fw == "v1_audit":
            # sub_components inside each dimension, matched by dimension name
            rebuilt = []
            for dim in items:
                subs_per = [(r, next(d for d in res.dimensions if d.name == dim.name).sub_components)
                            for r, res in per]
                rebuilt.append(replace(dim, sub_components=_aggregate_v1_subcomponents(subs_per)))
            items = rebuilt
        composite = spec["composite"](items)
        fields: dict[str, Any] = {spec["items"]: items, "top_gaps": spec["top_gaps"](items)}
        fields.update(spec["on_composite"](composite))
        answered = sum(_answered(i) for i in items)
        fields["overall_dk_ratio"] = (sum(i.dk_ratio * _answered(i) for i in items) / answered) if answered else 0.0
        fields["overall_confidence_level"] = _worst([i.confidence_level for i in items])
        for extra in spec.get("extra_lists", []):
            fields[extra] = _aggregate_items(
                fw, [(r, getattr(res, extra)) for r, res in per], "score_0_100",
                on_score=lambda item, s: {"score_0_100": s})
        base = per[0][1]
        aggregated.append(replace(base, **fields))
        contested.extend(_contested(per, fw))

    contested.sort(key=lambda c: c.stdev_0_1, reverse=True)
    summary = AggregationSummary(
        respondent_count=len(per_respondent), roles=roles,
        threshold=DIVERGENCE_THRESHOLD, min_dim_weight=MIN_DIM_WEIGHT,
        dimensions=summary_dims, contested=contested[:CONTESTED_TOP_N],
    )
    return tuple(aggregated), summary
