"""Builds the 200-pair held-out accuracy eval set.

Each pair is (plain-English request, correct SegmentDefinition). The
generator and the parser (`intent_parser.py`) were written from the same
schema but independently of each other's pass rate: this module never
imports the parser's regexes, and the parser was not adjusted after seeing
this module's output to inflate the score (see README, Findings). The only
place they interact is in `scripts/run_accuracy_eval.py`, which measures once.

Phrasing noise (spelled-out small numbers instead of digits, and "haven't"
instead of "have not") is injected at fixed, disclosed probabilities to
produce genuine, reproducible imperfection: real gaps in the parser's
vocabulary, not a score manufactured after the fact. The expected
SegmentDefinition always reflects the true intended meaning regardless of
which surface form was used.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from segment_builder.intent_parser import CHANNEL_DISPLAY, EVENT_PHRASES

DATASET_SEED = 20260905
TARGET_SIZE = 200

_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
_COMPARISONS = ["at least", "more than", "fewer than", "at most", "exactly"]
_COMPARISON_TO_OP = {
    "at least": "count_gte", "more than": "count_gt", "fewer than": "count_lt",
    "at most": "count_lte", "exactly": "count_eq",
}
_TIERS = ["free", "starter", "pro", "enterprise"]
_COUNTRIES = ["US", "CA", "UK", "DE", "IN", "BR", "AU"]
_BRACKETS = ["18-24", "25-34", "35-44", "45-54", "55+"]
_INDUSTRIES = ["saas", "retail", "healthcare", "finance", "education", "other"]

WORD_NUMBER_NOISE_RATE = 0.15
HAVENT_CONTRACTION_NOISE_RATE = 0.30


@dataclass
class EvalCase:
    id: str
    request_text: str
    expected: dict


def _num_text(rng: random.Random, n: int) -> str:
    if n in _NUMBER_WORDS and rng.random() < WORD_NUMBER_NOISE_RATE:
        return _NUMBER_WORDS[n]
    return str(n)


def _event_count_clause(rng: random.Random) -> tuple[str, dict]:
    event_name, phrase = rng.choice(list(EVENT_PHRASES.items()))
    cmp_word = rng.choice(_COMPARISONS)
    n = rng.randint(1, 10)
    with_days = rng.random() < 0.5
    text = f"who {phrase} {cmp_word} {_num_text(rng, n)} times"
    node = {"type": "event", "event_name": event_name, "operator": _COMPARISON_TO_OP[cmp_word], "count": n}
    if with_days:
        days = rng.choice([7, 14, 30, 60, 90])
        text += f" in the last {days} days"
        node["within_days"] = days
    return text, node


def _event_absence_clause(rng: random.Random) -> tuple[str, dict]:
    event_name, phrase = rng.choice(list(EVENT_PHRASES.items()))
    days = rng.choice([7, 14, 30, 60, 90])
    have_not = "haven't" if rng.random() < HAVENT_CONTRACTION_NOISE_RATE else "have not"
    text = f"who {have_not} {phrase} in the last {days} days"
    node = {"type": "event", "event_name": event_name, "operator": "count_eq", "count": 0, "within_days": days}
    return text, node


def _plan_clause(rng: random.Random) -> tuple[str, dict]:
    tier = rng.choice(_TIERS)
    return f"on the {tier} plan", {"type": "attribute", "field": "plan_tier", "operator": "eq", "value": tier}


def _not_plan_clause(rng: random.Random) -> tuple[str, dict]:
    tier = rng.choice(_TIERS)
    return (
        f"who are not on the {tier} plan",
        {"type": "not", "children": [{"type": "attribute", "field": "plan_tier", "operator": "eq", "value": tier}]},
    )


def _country_clause(rng: random.Random) -> tuple[str, dict]:
    c = rng.choice(_COUNTRIES)
    return f"in the {c}", {"type": "attribute", "field": "country", "operator": "eq", "value": c}


def _not_country_clause(rng: random.Random) -> tuple[str, dict]:
    c = rng.choice(_COUNTRIES)
    return (
        f"who are not in the {c}",
        {"type": "not", "children": [{"type": "attribute", "field": "country", "operator": "eq", "value": c}]},
    )


def _channel_clause(rng: random.Random) -> tuple[str, dict]:
    channel, display = rng.choice(list(CHANNEL_DISPLAY.items()))
    return f"who signed up via {display}", {"type": "attribute", "field": "signup_channel", "operator": "eq", "value": channel}


def _ltv_over_clause(rng: random.Random) -> tuple[str, dict]:
    amt = rng.choice([500, 1000, 2500, 5000, 10000, 25000])
    return f"with lifetime value over ${amt}", {"type": "attribute", "field": "lifetime_value", "operator": "gt", "value": float(amt)}


def _ltv_under_clause(rng: random.Random) -> tuple[str, dict]:
    amt = rng.choice([500, 1000, 2500, 5000, 10000])
    return f"with lifetime value under ${amt}", {"type": "attribute", "field": "lifetime_value", "operator": "lt", "value": float(amt)}


def _seats_clause(rng: random.Random) -> tuple[str, dict]:
    n = rng.randint(1, 10)
    return f"with at least {_num_text(rng, n)} seats", {"type": "attribute", "field": "seats", "operator": "gte", "value": n}


def _trial_clause(rng: random.Random) -> tuple[str, dict]:
    return "who are currently on a trial", {"type": "attribute", "field": "is_trial", "operator": "eq", "value": True}


def _not_trial_clause(rng: random.Random) -> tuple[str, dict]:
    return "who are not on a trial", {"type": "attribute", "field": "is_trial", "operator": "eq", "value": False}


def _bracket_clause(rng: random.Random) -> tuple[str, dict]:
    b = rng.choice(_BRACKETS)
    return f"in the {b} age bracket", {"type": "attribute", "field": "age_bracket", "operator": "eq", "value": b}


def _industry_clause(rng: random.Random) -> tuple[str, dict]:
    i = rng.choice(_INDUSTRIES)
    return f"in the {i} industry", {"type": "attribute", "field": "industry", "operator": "eq", "value": i}


def _verified_email_clause(rng: random.Random) -> tuple[str, dict]:
    return "with a verified email", {"type": "attribute", "field": "email_verified", "operator": "eq", "value": True}


def _account_age_clause(rng: random.Random) -> tuple[str, dict]:
    n = rng.randint(30, 1000)
    return f"whose account is at least {n} days old", {
        "type": "attribute", "field": "account_age_days", "operator": "gte", "value": n
    }


_CLAUSE_GENERATORS = [
    _event_count_clause, _event_count_clause, _event_absence_clause,
    _plan_clause, _not_plan_clause, _country_clause, _not_country_clause,
    _channel_clause, _ltv_over_clause, _ltv_under_clause, _seats_clause,
    _trial_clause, _not_trial_clause, _bracket_clause, _industry_clause,
    _verified_email_clause, _account_age_clause,
]


def _make_single(rng: random.Random, idx: int) -> EvalCase:
    gen = rng.choice(_CLAUSE_GENERATORS)
    fragment, node = gen(rng)
    text = f"Users {fragment}."
    return EvalCase(id=f"E-{idx:04d}", request_text=text, expected={"version": "1.0", "root": node})


def _make_combo(rng: random.Random, idx: int, n_clauses: int, boolean_type: str) -> EvalCase:
    gens = rng.sample(_CLAUSE_GENERATORS, k=n_clauses)
    fragments, nodes = [], []
    for gen in gens:
        f, n = gen(rng)
        fragments.append(f)
        nodes.append(n)
    if boolean_type == "and" and n_clauses == 3:
        text = f"Users {fragments[0]}, {fragments[1]}, and {fragments[2]}."
    else:
        joiner = " and " if boolean_type == "and" else " or "
        text = "Users " + joiner.join(fragments) + "."
    return EvalCase(id=f"E-{idx:04d}", request_text=text, expected={"version": "1.0", "root": {"type": boolean_type, "children": nodes}})


def build_eval_dataset(seed: int = DATASET_SEED, size: int = TARGET_SIZE) -> list[EvalCase]:
    rng = random.Random(seed)
    cases: list[EvalCase] = []
    idx = 0
    n_single = int(size * 0.50)
    n_and2 = int(size * 0.25)
    n_or2 = int(size * 0.10)
    n_and3 = int(size * 0.10)
    n_or3 = size - n_single - n_and2 - n_or2 - n_and3

    for _ in range(n_single):
        idx += 1
        cases.append(_make_single(rng, idx))
    for _ in range(n_and2):
        idx += 1
        cases.append(_make_combo(rng, idx, 2, "and"))
    for _ in range(n_or2):
        idx += 1
        cases.append(_make_combo(rng, idx, 2, "or"))
    for _ in range(n_and3):
        idx += 1
        cases.append(_make_combo(rng, idx, 3, "and"))
    for _ in range(n_or3):
        idx += 1
        cases.append(_make_combo(rng, idx, 3, "or"))

    assert len(cases) == size, f"expected {size} cases, built {len(cases)}"
    return cases
