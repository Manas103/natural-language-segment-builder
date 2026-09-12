"""Schema metadata: the only thing about the data model an LLM ever sees.

This module defines the vocabulary of event names and attribute fields the segment
builder understands. It is deliberately data-free: names and types only, never a
single real (or synthetic) profile row. `schema_metadata_for_prompt()` is the exact
payload handed to any LLM client (deterministic or real); it is asserted, in
tests/test_llm_client.py, to be the only "data-shaped" thing that ever leaves the
process toward a model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FieldType = Literal["string", "int", "float", "bool", "enum"]

# Operators legal for each field type. An attribute predicate whose operator is not
# in this list for its field's type is rejected by the validator before execution.
OPERATORS_BY_TYPE: dict[FieldType, tuple[str, ...]] = {
    "string": ("eq", "neq", "contains"),
    "int": ("eq", "neq", "gt", "gte", "lt", "lte"),
    "float": ("eq", "neq", "gt", "gte", "lt", "lte"),
    "bool": ("eq", "neq"),
    "enum": ("eq", "neq", "in"),
}

EVENT_COUNT_OPERATORS: tuple[str, ...] = (
    "count_gte",
    "count_gt",
    "count_lte",
    "count_lt",
    "count_eq",
)


@dataclass(frozen=True)
class AttributeFieldSpec:
    name: str
    type: FieldType
    enum_values: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class EventSpec:
    name: str
    description: str = ""


# The full attribute vocabulary. Values here are metadata (name/type/allowed enum
# labels) only, never a value drawn from an actual profile.
ATTRIBUTE_FIELDS: tuple[AttributeFieldSpec, ...] = (
    AttributeFieldSpec("plan_tier", "enum", ("free", "starter", "pro", "enterprise"), "subscription tier"),
    AttributeFieldSpec("country", "enum", ("US", "CA", "UK", "DE", "IN", "BR", "AU"), "billing country"),
    AttributeFieldSpec("signup_channel", "enum", ("organic", "paid_search", "referral", "partner", "email"), "acquisition channel"),
    AttributeFieldSpec("lifetime_value", "float", (), "total revenue in USD to date"),
    AttributeFieldSpec("is_trial", "bool", (), "currently in a trial period"),
    AttributeFieldSpec("seats", "int", (), "number of licensed seats"),
    AttributeFieldSpec("account_age_days", "int", (), "days since account creation"),
    AttributeFieldSpec("age_bracket", "enum", ("18-24", "25-34", "35-44", "45-54", "55+"), "self-reported age bracket"),
    AttributeFieldSpec("industry", "enum", ("saas", "retail", "healthcare", "finance", "education", "other"), "declared industry"),
    AttributeFieldSpec("email_verified", "bool", (), "email ownership verified"),
)

EVENTS: tuple[EventSpec, ...] = (
    EventSpec("login", "user authenticated into the product"),
    EventSpec("purchase", "user completed a checkout"),
    EventSpec("invite_sent", "user invited a teammate"),
    EventSpec("feature_used_export", "user used the export feature"),
    EventSpec("feature_used_dashboard", "user opened a dashboard"),
    EventSpec("support_ticket_opened", "user opened a support ticket"),
    EventSpec("churned", "user's subscription was cancelled"),
    EventSpec("upgraded_plan", "user moved to a higher plan tier"),
    EventSpec("email_opened", "user opened a marketing email"),
    EventSpec("api_call", "user's integration made an API call"),
)

ATTRIBUTE_FIELDS_BY_NAME: dict[str, AttributeFieldSpec] = {f.name: f for f in ATTRIBUTE_FIELDS}
EVENT_NAMES: set[str] = {e.name for e in EVENTS}


def schema_metadata_for_prompt() -> dict:
    """The exact, data-free payload sent to an LLM client. Field names and types
    only; no profile ids, no profile attribute values, no event timestamps."""
    return {
        "events": [{"name": e.name, "description": e.description} for e in EVENTS],
        "attribute_fields": [
            {
                "name": f.name,
                "type": f.type,
                "allowed_operators": list(OPERATORS_BY_TYPE[f.type]),
                "enum_values": list(f.enum_values),
                "description": f.description,
            }
            for f in ATTRIBUTE_FIELDS
        ],
        "event_operators": list(EVENT_COUNT_OPERATORS),
    }
