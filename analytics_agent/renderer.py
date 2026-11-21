"""Renders a QuerySpec + its result rows as the natural-language sentence a
conversational agent would actually show a user. This, not the SQL or the
result set, is all judge.py ever sees.
"""
from .semantic_model import METRIC_BY_NAME

CURRENCY_METRICS = {
    "total_revenue", "average_order_value", "gross_margin", "discount_amount",
    "total_cost", "total_profit", "max_order_value", "min_order_value", "revenue_per_customer",
}
FRACTION_PERCENT_METRICS = {"return_rate"}
ALREADY_PERCENT_METRICS = {"profit_margin_pct", "avg_discount_pct"}
COUNT_METRICS = {"order_count", "return_count", "unique_customers", "distinct_products_sold"}

_METRIC_LABEL = {m.name: m.synonyms[0] for m in METRIC_BY_NAME.values()}


def _spell_small_int(n: int) -> str:
    from .judge import _ONES
    if 0 <= n < len(_ONES):
        return _ONES[n]
    return str(n)


def render_number(metric_name: str, value, use_word_numbers: bool) -> str:
    if value is None:
        return "no data"
    value = float(value)
    if use_word_numbers and metric_name in COUNT_METRICS and value == int(value) and 0 <= value < 20:
        return _spell_small_int(int(value))
    if metric_name in CURRENCY_METRICS:
        return f"${value:,.2f}"
    if metric_name in FRACTION_PERCENT_METRICS:
        return f"{value * 100:.1f}%"
    if metric_name in ALREADY_PERCENT_METRICS:
        return f"{value:.1f}%"
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}"


def render_transcript(spec, rows, use_word_numbers: bool = False) -> str:
    metric_label = _METRIC_LABEL[spec.metric]
    if not rows:
        return f"No data found for the {metric_label}."
    if not spec.group_by:
        value = rows[0][0]
        return f"The {metric_label} is {render_number(spec.metric, value, use_word_numbers)}."
    first_row = rows[0]
    group_values = first_row[:-1]
    value = first_row[-1]
    label = ", ".join(str(v) for v in group_values)
    extra = f", plus {len(rows) - 1} more row(s)" if len(rows) > 1 else ""
    return (
        f"Broken down by {', '.join(spec.group_by)}, the top entry ({label}) has "
        f"{metric_label} {render_number(spec.metric, value, use_word_numbers)}{extra}."
    )


def refusal_transcript() -> str:
    return "I can't answer that; it isn't part of the governed semantic model."
