"""Preparation checklists, one per respondent role and instrument, built
from the question bank so they can never drift from what is asked.

/prepare/                             index: pick instrument and role
/prepare/<instrument>/<role>.pdf      the checklist as a PDF

Glenn Holman's review (2026-09-29): the questions deserve preparation; a
small client team needs to be assembled; instructions should go out before
the link. This is that instruction set. The PDF lists every question the
role will see, by section, with what to have at hand, and says plainly that
the questionnaire can be left and resumed.
"""

from __future__ import annotations

import threading

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from questionnaire import flow

ROLES = [
    ("BOARD", "Board member"), ("CEO", "CEO or owner"), ("CFO", "CFO or finance lead"),
    ("CIO", "CIO or IT lead"), ("CISO", "CISO or security lead"), ("COO", "COO or operations lead"),
    ("VP", "Vice president"), ("DIR", "Director"), ("MGR", "Manager"),
    ("IC", "Individual contributor"), ("HR", "HR lead"),
]
INSTRUMENTS = {
    "tier_1": {"title": "AI Audit Snapshot", "slug": "ai-audit-snapshot"},
    "aiitsa": {"title": "AI IT Security Audit\u2122", "slug": "ai-it-security-audit"},
    "combined": {"title": "AI Audit Snapshot + AI IT Security Audit\u2122", "slug": "both-audits"},
}
_SLUG_TO_INSTRUMENT = {v["slug"]: k for k, v in INSTRUMENTS.items()}

# What to have at hand, by section. Written once, true for every role.
SECTION_PREP = {
    "A": ("Context and identity", "Your industry code, headcount, revenue band, where you operate, which laws and standards you work under, and who owns AI decisions today."),
    "B": ("AI tool inventory and discovery", "A list of every AI tool in use, sanctioned or not: name, who uses it, what data it touches, who pays for it. Ask around; the unsanctioned ones matter most."),
    "C": ("Cost mapping", "Last 12 months of AI spend: subscriptions, API bills, vendor contracts, staff time. Your finance system or card statements are the source."),
    "D": ("Performance measurement", "Any targets set for AI tools, any measurement of results, any tool retired for missing its target."),
    "E": ("Risk exposure", "Vendor contracts and data-handling terms, where customer or regulated data goes, any incident or near miss, cyber insurance terms, counsel's involvement."),
    "F": ("Governance gaps", "Board or executive minutes mentioning AI, any AI policy, the committee or person accountable, training records, how exceptions are handled."),
    "G": ("Outcomes, workflow and confidence", "Which business outcomes AI was meant to move, where it changed a workflow, and how confident you are in each answer."),
    "H": ("Follow-up", "Anything the questionnaire did not ask that you think the auditor should know. Write it down; it is read."),
}
DOMAIN_PREP = {
    "Screening: The Opening Seven": "The six Visibility Triangle questions. Answer from what you know today; \"Don't know\" is a real answer and is reported as exposure, not as a gap in your effort.",
    "Security Governance & Risk Management": "AI risk register, policies, accountable owner, approval path for new AI use.",
    "Security Operations": "Monitoring, logging, alerting and incident response as they apply to AI systems and agents.",
    "Architecture & Engineering": "Where AI systems sit in your environment, network boundaries, agent permissions, non-human identities.",
    "Application & Product Security": "Testing of AI features and agents, prompt injection defences, change control.",
    "Third-Party & Supply Chain Risk": "AI vendor inventory, contracts, data rights, model training rights, subprocessors.",
    "Data Protection & Privacy": "Which sensitive data reaches which AI system, retention, cross-border inference, deletion.",
    "Inventory Feeder": "The feeder questions that build your four-layer AI inventory.",
}

_CACHE: dict[tuple[str, str], bytes] = {}
_LOCK = threading.Lock()


def _groups(instrument: str, role: str) -> list[dict]:
    insts = ["tier_1", "aiitsa"] if instrument == "combined" else [instrument]
    groups: list[dict] = []
    for inst in insts:
        qs = flow.questions_visible_to_role(role, {}, instrument=inst)
        by_key: dict[str, list] = {}
        for q in qs:
            if inst == "aiitsa":
                ext = getattr(q, "extended_metadata", None) or {}
                key = ext.get("domain_label") or getattr(q, "domain_label", None) or q.section
            else:
                key = q.section
            by_key.setdefault(key, []).append(q)
        for key, items in by_key.items():
            if inst == "aiitsa":
                title, prep = key, DOMAIN_PREP.get(key, "")
            else:
                title, prep = SECTION_PREP.get(key, (key, ""))
            groups.append({
                "instrument": INSTRUMENTS[inst]["title"], "title": title, "prep": prep,
                "questions": [{"text": q.question_text, "rows": list(getattr(q, "matrix_rows", None) or [])}
                              for q in items],
            })
    return groups


def _context(instrument: str, role: str) -> dict:
    role_label = dict(ROLES)[role]
    groups = _groups(instrument, role)
    total = sum(len(g["questions"]) for g in groups)
    return {
        "instrument_title": INSTRUMENTS[instrument]["title"], "role": role, "role_label": role_label,
        "groups": groups, "total": total,
        "minutes": (total * 50) // 60,   # about 50 seconds a question with answers at hand
    }


def index(request):
    return render(request, "questionnaire/prepare_index.html",
                  {"instruments": [(v["slug"], v["title"]) for v in INSTRUMENTS.values()], "roles": ROLES,
                   "current": (request.GET.get("instrument") or "ai-audit-snapshot")})


def checklist_pdf(request, instrument_slug: str, role: str):
    instrument = _SLUG_TO_INSTRUMENT.get(instrument_slug)
    role = (role or "").upper()
    if not instrument or role not in dict(ROLES):
        raise Http404
    key = (instrument, role)
    pdf = _CACHE.get(key)
    if pdf is None:
        with _LOCK:
            pdf = _CACHE.get(key)
            if pdf is None:
                from reports.generator import html_to_pdf_bytes
                html = render_to_string("questionnaire/prepare_checklist.html", _context(instrument, role))
                pdf = html_to_pdf_bytes(html)
                _CACHE[key] = pdf
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="Preparation_Checklist_{instrument_slug}_{role}.pdf"'
    resp["Cache-Control"] = "public, max-age=86400"
    return resp
