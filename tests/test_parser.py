from analytics_agent import parser
from analytics_agent.query_spec import Filter, QuerySpec


def test_parses_simple_metric_question():
    spec = parser.parse("What is the total revenue?")
    assert spec == QuerySpec(metric="total_revenue")


def test_parses_group_by():
    spec = parser.parse("What is the total revenue by region?")
    assert spec == QuerySpec(metric="total_revenue", group_by=("region",))


def test_parses_two_group_by_dimensions():
    spec = parser.parse("What is the total revenue by region and channel?")
    assert spec == QuerySpec(metric="total_revenue", group_by=("region", "channel"))


def test_parses_filter_with_is():
    spec = parser.parse("What is the total revenue where channel is online?")
    assert spec == QuerySpec(metric="total_revenue", filters=(Filter("channel", "=", "online"),))


def test_parses_filter_with_equals_sign():
    spec = parser.parse("What is the total revenue where channel = online?")
    assert spec == QuerySpec(metric="total_revenue", filters=(Filter("channel", "=", "online"),))


def test_refuses_unsupported_filter_operator_word():
    assert parser.parse("What is the total revenue where channel equals online?") is None


def test_refuses_unsupported_frame():
    assert parser.parse("Please break down total revenue.") is None


def test_refuses_out_of_model_metric():
    assert parser.parse("What is the customer lifetime value?") is None


def test_refuses_out_of_model_dimension_in_group_by():
    assert parser.parse("What is the total revenue by inventory turnover?") is None


def test_accepts_whats_contraction():
    spec = parser.parse("What's the total revenue?")
    assert spec == QuerySpec(metric="total_revenue")
