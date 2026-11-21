"""Builds the 350-question held-out in-model set and the 60-question
out-of-model set. Template-generated, not hand-typed, and disclosed as such.
Each in-model question carries its own ground-truth QuerySpec, built
directly from the template's own choices, not derived by running the
parser; the parser never sees this dict (see leakage control in grader.py).
"""
import random
from dataclasses import dataclass

from .data_gen import (
    CATEGORIES, CHANNELS, COUNTRIES, DAYS_OF_WEEK, ORDER_STATUSES,
    PAYMENT_METHODS, REGIONS, SEGMENTS, SHIPPING_METHODS,
)
from .query_spec import Filter, QuerySpec
from .semantic_model import DIMENSIONS, METRICS

DEFAULT_SEED = 20260916
N_IN_MODEL = 350
N_OUT_OF_MODEL = 60

_FILTERABLE_VALUES = {
    "region": REGIONS,
    "country": COUNTRIES,
    "category": CATEGORIES,
    "channel": CHANNELS,
    "customer_segment": SEGMENTS,
    "payment_method": PAYMENT_METHODS,
    "order_status": [s for s in set(ORDER_STATUSES)],
    "shipping_method": SHIPPING_METHODS,
    "day_of_week": DAYS_OF_WEEK,
    "year": ["2024", "2025", "2026"],
}

OUT_OF_MODEL_PHRASES = [
    "customer lifetime value", "net promoter score", "inventory turnover", "website traffic",
    "churn rate", "email open rate", "click through rate", "ad spend roas", "cost per acquisition",
    "employee headcount", "warehouse utilization", "marketing qualified leads", "social media engagement",
    "server uptime", "page load time", "cart abandonment rate", "email unsubscribe rate",
    "support ticket volume", "average response time", "first contact resolution rate",
    "shipping damage rate", "app crash rate", "api latency", "database query time",
    "loyalty points redeemed", "referral conversion rate", "trial to paid conversion",
    "feature adoption rate", "daily active users", "monthly active users", "session duration",
    "bounce rate", "organic search traffic", "paid search traffic", "impression share",
    "viewability rate", "video completion rate", "sentiment score", "survey response rate",
    "warranty claim rate", "repair turnaround time", "supplier lead time", "forecast accuracy",
    "stockout rate", "backorder rate", "carbon footprint", "energy consumption", "water usage",
    "safety incident rate", "overtime hours", "training completion rate", "absenteeism rate",
    "promotion approval rate", "vendor compliance rate", "audit finding count",
    "password reset volume", "phishing click rate", "patch compliance rate",
    "uptime sla breach count", "data entry error rate",
]
assert len(OUT_OF_MODEL_PHRASES) == N_OUT_OF_MODEL


@dataclass(frozen=True)
class EvalQuestion:
    question_id: int
    text: str
    verified_spec: QuerySpec
    use_word_numbers: bool = False


def _build_question_text(metric_phrase, groupby_phrases, filter_clauses, frame_supported, filter_op_supported):
    body = metric_phrase
    if groupby_phrases:
        body += " by " + " and ".join(groupby_phrases)
    if filter_clauses:
        op_word = "is" if filter_op_supported else "equals"
        clause_text = " and ".join(f"{dim} {op_word} {value}" for dim, value in filter_clauses)
        body += " where " + clause_text
    if frame_supported:
        return f"What is the {body}?"
    return f"Please break down {body}."


def build_in_model_questions(seed=DEFAULT_SEED, n=N_IN_MODEL):
    rng = random.Random(seed)
    dims_with_values = [d for d in DIMENSIONS if d.name in _FILTERABLE_VALUES]
    questions = []
    for qid in range(n):
        metric = rng.choice(METRICS)
        metric_phrase = rng.choice(metric.synonyms)

        n_groupby = rng.choices([0, 1, 2], weights=[20, 55, 25])[0]
        groupby_dims = rng.sample(DIMENSIONS, n_groupby)
        groupby_phrases = [rng.choice(d.synonyms) for d in groupby_dims]
        groupby_names = tuple(d.name for d in groupby_dims)

        has_filter = rng.random() < 0.5
        filters = ()
        filter_clauses = []
        filter_op_supported = True
        if has_filter:
            remaining = [d for d in dims_with_values if d.name not in groupby_names]
            filter_dim = rng.choice(remaining) if remaining else rng.choice(dims_with_values)
            value = rng.choice(_FILTERABLE_VALUES[filter_dim.name])
            filter_clauses = [(rng.choice(filter_dim.synonyms), value)]
            filters = (Filter(filter_dim.name, "=", value),)
            filter_op_supported = rng.random() < 0.80

        frame_supported = rng.random() < 0.90

        use_word_numbers = rng.random() < 0.15

        text = _build_question_text(metric_phrase, groupby_phrases, filter_clauses, frame_supported, filter_op_supported)
        spec = QuerySpec(metric=metric.name, group_by=groupby_names, filters=filters)
        questions.append(EvalQuestion(qid, text, spec, use_word_numbers))
    return questions


def build_out_of_model_questions(n=N_OUT_OF_MODEL):
    return [f"What is the {phrase}?" for phrase in OUT_OF_MODEL_PHRASES[:n]]
