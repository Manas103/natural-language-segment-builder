import pytest

from analytics_agent.query_spec import Filter, QuerySpec


def test_valid_spec_constructs():
    spec = QuerySpec(metric="total_revenue", group_by=("region",), filters=(Filter("channel", "=", "online"),))
    assert spec.metric == "total_revenue"


def test_unknown_metric_rejected():
    with pytest.raises(ValueError):
        QuerySpec(metric="customer_lifetime_value")


def test_unknown_group_by_dimension_rejected():
    with pytest.raises(ValueError):
        QuerySpec(metric="total_revenue", group_by=("inventory_turnover",))


def test_unknown_filter_dimension_rejected():
    with pytest.raises(ValueError):
        QuerySpec(metric="total_revenue", filters=(Filter("churn_rate", "=", "x"),))
