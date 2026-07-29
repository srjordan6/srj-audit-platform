"""AI Exposure Score — the short, no-form-wall entry funnel.

Why this exists
---------------
The full Tier 1 audit asks for eight identifying fields before question one.
Cold traffic from paid social will not pay that price: campaigns v1 and v2
both delivered clicks that converted to ~zero starts.

This module backs a 5-question screener that asks for NOTHING identifying,
scores instantly, shows the visitor a real result, and only then invites the
full audit. Email capture is optional and happens AFTER the score is shown.

Single source of truth for the questions and the scoring weights. The view
renders QUESTIONS into the template as JSON so the browser can score
instantly with no round trip, and `score_answers` re-computes server-side
when the result is logged so the stored score can be trusted.
"""

from __future__ import annotations

# Each question: id, prompt, and options as (value, label, points).
# Points are additive. MAX_SCORE is the sum of each question's highest option.
QUESTIONS = [
    {
        "id": "usage",
        "prompt": "How widely does your company use AI today?",
        "help": "Include general tools like ChatGPT, Copilot and Gemini — "
                "not just systems you built.",
        "options": [
            ("none", "Not at all, as far as I know", 0),
            ("few", "A few people, informally", 10),
            ("wide", "Widely across teams", 20),
            ("product", "It's built into what we sell", 25),
        ],
    },
    {
        "id": "consequential",
        "prompt": "Does AI touch decisions about people?",
        "help": "Hiring, promotion, pay, lending, insurance, housing, "
                "healthcare or education decisions.",
        "options": [
            ("no", "No", 0),
            ("unsure", "I'm not certain", 15),
            ("yes", "Yes", 30),
        ],
    },
    {
        "id": "policy",
        "prompt": "Do you have a written AI policy approved by leadership?",
        "help": "Approved and current — not a draft someone started.",
        "options": [
            ("yes", "Yes, approved and current", 0),
            ("progress", "In progress", 8),
            ("no", "No", 18),
        ],
    },
    {
        "id": "nexus",
        "prompt": "Do you operate in, or sell into, the EU, UK or California?",
        "help": "Customers or users there count, even with no entity there.",
        "options": [
            ("no", "No", 0),
            ("unsure", "I'm not certain", 8),
            ("yes", "Yes", 15),
        ],
    },
    {
        "id": "known_laws",
        "prompt": "Could you name which AI laws apply to you right now?",
        "help": "The question a board member or an enterprise customer asks.",
        "options": [
            ("confident", "Yes, confidently", 0),
            ("roughly", "Roughly", 6),
            ("no", "No", 12),
        ],
    },
]

MAX_SCORE = sum(max(p for _, _, p in q["options"]) for q in QUESTIONS)  # 100

BANDS = [
    (0, 24, "Contained", "Your exposure looks limited today — but AI use "
                         "spreads faster than governance does. The value now "
                         "is a baseline you can point to later."),
    (25, 49, "Emerging", "You have real exposure forming and little "
                         "documented control around it. This is the cheapest "
                         "point at which to fix it."),
    (50, 74, "Elevated", "You have obligations that are probably already "
                         "live and largely unmapped. A regulator or an "
                         "enterprise customer would find gaps here."),
    (75, 100, "Urgent", "You are operating high-exposure AI with little "
                        "documented governance. This is the profile that "
                        "turns an enforcement inquiry into a bad quarter."),
]

# Answer-specific callouts. Each entry: (question_id, value, message).
FLAGS = [
    ("consequential", "yes",
     "AI in decisions about people is the highest-obligation category there "
     "is — the strictest tier under the EU AI Act, and Title VII plus state "
     "AI hiring laws in the US."),
    ("consequential", "unsure",
     "Not being certain whether AI touches decisions about people is itself "
     "the finding. That answer has to become a yes or a no before you can "
     "classify anything."),
    ("product", "product",
     "If AI is built into what you sell, you may be a provider rather than "
     "just a deployer — a materially heavier set of obligations."),
    ("policy", "no",
     "With no approved AI policy you have no documented control to show a "
     "regulator, an auditor, or an enterprise customer's security review."),
    ("nexus", "yes",
     "EU, UK and California rules can reach you through your customers "
     "alone. No local entity is required for the obligations to attach."),
    ("known_laws", "no",
     "You cannot self-assess a classification you have not mapped. This is "
     "where a wrong call sits unchallenged until enforcement finds it."),
]


def band_for(score: int) -> tuple[str, str]:
    """Return (band_name, band_message) for a 0-100 score."""
    for low, high, name, message in BANDS:
        if low <= score <= high:
            return name, message
    return BANDS[-1][2], BANDS[-1][3]


def score_answers(answers: dict) -> dict:
    """Score a {question_id: option_value} mapping.

    Unknown question ids and unknown option values contribute zero rather
    than raising — this is fed by a public endpoint and must not 500 on
    junk input.
    """
    total = 0
    answered = 0
    for question in QUESTIONS:
        value = answers.get(question["id"])
        for option_value, _label, points in question["options"]:
            if option_value == value:
                total += points
                answered += 1
                break

    flags = []
    for question_id, value, message in FLAGS:
        # The "product" flag keys off the usage question's product option.
        target = "usage" if question_id == "product" else question_id
        if answers.get(target) == value:
            flags.append(message)

    name, message = band_for(total)
    return {
        "score": total,
        "max_score": MAX_SCORE,
        "band": name,
        "band_message": message,
        "flags": flags,
        "answered": answered,
        "complete": answered == len(QUESTIONS),
    }
