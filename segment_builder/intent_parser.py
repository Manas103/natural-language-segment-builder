"""The deterministic, rule-based intent parser.

This is the component actually measured at the 200-request and 150-candidate
scale, standing in for "the LLM produced this", exactly the way
`ontology-grounded-operations-agent`'s `qa_router.py` (a regex marker-phrase
router) stands in for its own LLM client in the free, reproducible benchmark.
It has a genuinely limited vocabulary: exact comparison phrases, exact event
phrasings, digits only (not spelled-out numbers), and "have not" but not the
"haven't" contraction. Those limits are real coverage gaps, not artificially
inserted to hit a target score; `eval_dataset.py` independently decides how
often to exercise them, and the two were written without looking at each
other's pass rate.
"""
from __future__ import annotations

import re
from typing import Any

from segment_builder.fields import ATTRIBUTE_FIELDS_BY_NAME

# Canonical phrase used for each event, both by the dataset generator and here.
EVENT_PHRASES: dict[str, str] = {
    "login": "logged in",
    "purchase": "made a purchase",
    "invite_sent": "invited a teammate",
    "feature_used_export": "used the export feature",
    "feature_used_dashboard": "opened a dashboard",
    "support_ticket_opened": "opened a support ticket",
    "churned": "churned",
    "upgraded_plan": "upgraded their plan",
    "email_opened": "opened a marketing email",
    "api_call": "made an API call",
}
PHRASE_TO_EVENT: dict[str, str] = {v: k for k, v in EVENT_PHRASES.items()}

CHANNEL_DISPLAY: dict[str, str] = {
    "organic": "organic",
    "paid_search": "paid search",
    "referral": "referral",
    "partner": "partner",
    "email": "email",
}
DISPLAY_TO_CHANNEL: dict[str, str] = {v: k for k, v in CHANNEL_DISPLAY.items()}

_COMPARISON_TO_OP = {
    "at least": "count_gte",
    "more than": "count_gt",
    "fewer than": "count_lt",
    "at most": "count_lte",
    "exactly": "count_eq",
}

_EVENT_ALTERNATION = "|".join(re.escape(p) for p in sorted(PHRASE_TO_EVENT, key=len, reverse=True))
_COMPARISON_ALTERNATION = "|".join(re.escape(c) for c in _COMPARISON_TO_OP)
_CHANNEL_ALTERNATION = "|".join(re.escape(c) for c in sorted(DISPLAY_TO_CHANNEL, key=len, reverse=True))

_EVENT_COUNT_RE = re.compile(
    rf"^who (?P<phrase>{_EVENT_ALTERNATION}) (?P<cmp>{_COMPARISON_ALTERNATION}) (?P<n>\d+) times"
    rf"(?: in the last (?P<days>\d+) days)?$"
)
_EVENT_ABSENCE_RE = re.compile(
    rf"^who have not (?P<phrase>{_EVENT_ALTERNATION}) in the last (?P<days>\d+) days$"
)

_ATTRIBUTE_PATTERNS: list[tuple[re.Pattern, Any]] = [
    (re.compile(r"^on the (?P<tier>free|starter|pro|enterprise) plan$"),
     lambda m: _attr("plan_tier", "eq", m["tier"])),
    (re.compile(r"^who are not on the (?P<tier>free|starter|pro|enterprise) plan$"),
     lambda m: _not(_attr("plan_tier", "eq", m["tier"]))),
    (re.compile(r"^in the (?P<country>US|CA|UK|DE|IN|BR|AU)$"),
     lambda m: _attr("country", "eq", m["country"])),
    (re.compile(r"^who are not in the (?P<country>US|CA|UK|DE|IN|BR|AU)$"),
     lambda m: _not(_attr("country", "eq", m["country"]))),
    (re.compile(rf"^who signed up via (?P<channel>{_CHANNEL_ALTERNATION})$"),
     lambda m: _attr("signup_channel", "eq", DISPLAY_TO_CHANNEL[m["channel"]])),
    (re.compile(r"^with lifetime value over \$(?P<amount>\d+(?:\.\d+)?)$"),
     lambda m: _attr("lifetime_value", "gt", float(m["amount"]))),
    (re.compile(r"^with lifetime value under \$(?P<amount>\d+(?:\.\d+)?)$"),
     lambda m: _attr("lifetime_value", "lt", float(m["amount"]))),
    (re.compile(r"^with at least (?P<n>\d+) seats$"),
     lambda m: _attr("seats", "gte", int(m["n"]))),
    (re.compile(r"^who are currently on a trial$"),
     lambda m: _attr("is_trial", "eq", True)),
    (re.compile(r"^who are not on a trial$"),
     lambda m: _attr("is_trial", "eq", False)),
    (re.compile(r"^in the (?P<bracket>18-24|25-34|35-44|45-54|55\+) age bracket$"),
     lambda m: _attr("age_bracket", "eq", m["bracket"])),
    (re.compile(r"^in the (?P<industry>saas|retail|healthcare|finance|education|other) industry$"),
     lambda m: _attr("industry", "eq", m["industry"])),
    (re.compile(r"^with a verified email$"),
     lambda m: _attr("email_verified", "eq", True)),
    (re.compile(r"^whose account is at least (?P<n>\d+) days old$"),
     lambda m: _attr("account_age_days", "gte", int(m["n"]))),
]


class IntentParseError(ValueError):
    """The deterministic parser could not express this request in the typed schema."""


def _attr(field: str, operator: str, value: Any) -> dict:
    assert field in ATTRIBUTE_FIELDS_BY_NAME
    return {"type": "attribute", "field": field, "operator": operator, "value": value}


def _not(child: dict) -> dict:
    return {"type": "not", "children": [child]}


def parse_fragment(fragment: str) -> dict:
    fragment = fragment.strip()

    m = _EVENT_COUNT_RE.match(fragment)
    if m:
        event_name = PHRASE_TO_EVENT.get(m["phrase"])
        if event_name is None:
            raise IntentParseError(f"unrecognized event phrase: {m['phrase']!r}")
        node = {
            "type": "event",
            "event_name": event_name,
            "operator": _COMPARISON_TO_OP[m["cmp"]],
            "count": int(m["n"]),
        }
        if m["days"] is not None:
            node["within_days"] = int(m["days"])
        return node

    m = _EVENT_ABSENCE_RE.match(fragment)
    if m:
        event_name = PHRASE_TO_EVENT.get(m["phrase"])
        if event_name is None:
            raise IntentParseError(f"unrecognized event phrase: {m['phrase']!r}")
        return {
            "type": "event",
            "event_name": event_name,
            "operator": "count_eq",
            "count": 0,
            "within_days": int(m["days"]),
        }

    for pattern, builder in _ATTRIBUTE_PATTERNS:
        m = pattern.match(fragment)
        if m:
            return builder(m)

    raise IntentParseError(f"could not parse clause: {fragment!r}")


def parse_request(text: str) -> dict:
    """Parse a full plain-English request into a SegmentDefinition dict.
    Raises IntentParseError if the request (or any clause within it) cannot be
    expressed in the typed schema, deliberately, rather than guessing."""
    body = text.strip()
    if body.lower().startswith("users "):
        body = body[len("users "):]
    body = body.rstrip(".")

    if " or " in body:
        if " and " in body or "," in body:
            raise IntentParseError("mixed and/or composition is not supported")
        fragments = [f.strip() for f in body.split(" or ")]
        nodes = [parse_fragment(f) for f in fragments]
        if len(nodes) < 2:
            raise IntentParseError("expected at least two clauses for an 'or' request")
        return {"version": "1.0", "root": {"type": "or", "children": nodes}}

    if " and " in body or "," in body:
        normalized = body.replace(", and ", " and ").replace(",", " and ")
        fragments = [f.strip() for f in normalized.split(" and ") if f.strip()]
        nodes = [parse_fragment(f) for f in fragments]
        if len(nodes) < 2:
            raise IntentParseError("expected at least two clauses for an 'and' request")
        return {"version": "1.0", "root": {"type": "and", "children": nodes}}

    return {"version": "1.0", "root": parse_fragment(body)}
