from analytics_agent.query_spec import QuerySpec
from analytics_agent.renderer import refusal_transcript, render_number, render_transcript


def test_render_number_currency():
    assert render_number("total_revenue", 1234.5, False) == "$1,234.50"


def test_render_number_fraction_percent():
    assert render_number("return_rate", 0.168, False) == "16.8%"


def test_render_number_already_percent():
    assert render_number("profit_margin_pct", 38.4, False) == "38.4%"


def test_render_number_word_form_for_small_count():
    assert render_number("order_count", 3, True) == "three"


def test_render_number_digit_form_when_word_numbers_off():
    assert render_number("order_count", 3, False) == "3"


def test_render_transcript_no_group_by():
    spec = QuerySpec(metric="total_revenue")
    text = render_transcript(spec, [(1000.0,)])
    assert "$1,000.00" in text


def test_render_transcript_with_group_by_mentions_row_count():
    spec = QuerySpec(metric="total_revenue", group_by=("region",))
    text = render_transcript(spec, [("northeast", 500.0), ("west", 300.0)])
    assert "northeast" in text
    assert "1 more row" in text


def test_render_transcript_empty_rows():
    spec = QuerySpec(metric="total_revenue")
    assert "No data" in render_transcript(spec, [])


def test_refusal_transcript_mentions_semantic_model():
    assert "governed semantic model" in refusal_transcript()
