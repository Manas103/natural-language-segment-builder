import pytest

from segment_builder.intent_parser import IntentParseError, parse_request


def test_simple_event_count():
    d = parse_request("Users who logged in at least 3 times.")
    assert d["root"] == {"type": "event", "event_name": "login", "operator": "count_gte", "count": 3}


def test_event_count_with_recency():
    d = parse_request("Users who made a purchase more than 2 times in the last 30 days.")
    assert d["root"] == {"type": "event", "event_name": "purchase", "operator": "count_gt", "count": 2, "within_days": 30}


def test_event_absence():
    d = parse_request("Users who have not logged in in the last 14 days.")
    assert d["root"] == {"type": "event", "event_name": "login", "operator": "count_eq", "count": 0, "within_days": 14}


def test_attribute_plan_tier():
    d = parse_request("Users on the pro plan.")
    assert d["root"] == {"type": "attribute", "field": "plan_tier", "operator": "eq", "value": "pro"}


def test_negated_attribute():
    d = parse_request("Users who are not on the free plan.")
    assert d["root"] == {"type": "not", "children": [{"type": "attribute", "field": "plan_tier", "operator": "eq", "value": "free"}]}


def test_and_composite():
    d = parse_request("Users on the pro plan and with a verified email.")
    assert d["root"]["type"] == "and"
    assert len(d["root"]["children"]) == 2


def test_or_composite():
    d = parse_request("Users in the US or in the CA.")
    assert d["root"]["type"] == "or"


def test_three_clause_and_with_oxford_comma():
    d = parse_request("Users on the pro plan, in the US, and with a verified email.")
    assert d["root"]["type"] == "and"
    assert len(d["root"]["children"]) == 3


def test_unrecognized_clause_raises():
    with pytest.raises(IntentParseError):
        parse_request("Users who are secretly plotting something.")


def test_spelled_out_number_is_a_known_coverage_gap():
    with pytest.raises(IntentParseError):
        parse_request("Users who logged in at least three times.")


def test_havent_contraction_is_a_known_coverage_gap():
    with pytest.raises(IntentParseError):
        parse_request("Users who haven't logged in in the last 30 days.")


def test_mixed_and_or_is_rejected_rather_than_guessed():
    with pytest.raises(IntentParseError):
        parse_request("Users on the pro plan and in the US or with a verified email.")
