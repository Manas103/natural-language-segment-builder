import pydantic
import pytest

from segment_builder.schema import SegmentDefinition


def test_valid_event_predicate_parses():
    d = SegmentDefinition.model_validate(
        {"version": "1.0", "root": {"type": "event", "event_name": "login", "operator": "count_gte", "count": 3}}
    )
    assert d.root.event_name == "login"


def test_valid_attribute_predicate_parses():
    d = SegmentDefinition.model_validate(
        {"version": "1.0", "root": {"type": "attribute", "field": "plan_tier", "operator": "eq", "value": "pro"}}
    )
    assert d.root.value == "pro"


def test_and_composite_parses():
    d = SegmentDefinition.model_validate(
        {
            "version": "1.0",
            "root": {
                "type": "and",
                "children": [
                    {"type": "event", "event_name": "login", "operator": "count_gte", "count": 1},
                    {"type": "attribute", "field": "plan_tier", "operator": "eq", "value": "pro"},
                ],
            },
        }
    )
    assert d.root.type == "and"
    assert len(d.root.children) == 2


def test_unknown_event_name_rejected():
    with pytest.raises(pydantic.ValidationError):
        SegmentDefinition.model_validate(
            {"version": "1.0", "root": {"type": "event", "event_name": "nope", "operator": "count_gte", "count": 1}}
        )


def test_unknown_attribute_field_rejected():
    with pytest.raises(pydantic.ValidationError):
        SegmentDefinition.model_validate(
            {"version": "1.0", "root": {"type": "attribute", "field": "nope", "operator": "eq", "value": 1}}
        )


def test_operator_type_mismatch_rejected():
    with pytest.raises(pydantic.ValidationError):
        SegmentDefinition.model_validate(
            {"version": "1.0", "root": {"type": "attribute", "field": "seats", "operator": "contains", "value": 3}}
        )


def test_and_requires_at_least_two_children():
    with pytest.raises(pydantic.ValidationError):
        SegmentDefinition.model_validate(
            {"version": "1.0", "root": {"type": "and", "children": [{"type": "attribute", "field": "seats", "operator": "gte", "value": 1}]}}
        )


def test_not_requires_exactly_one_child():
    with pytest.raises(pydantic.ValidationError):
        SegmentDefinition.model_validate(
            {
                "version": "1.0",
                "root": {
                    "type": "not",
                    "children": [
                        {"type": "attribute", "field": "seats", "operator": "gte", "value": 1},
                        {"type": "attribute", "field": "seats", "operator": "lte", "value": 5},
                    ],
                },
            }
        )


def test_extra_field_rejected():
    with pytest.raises(pydantic.ValidationError):
        SegmentDefinition.model_validate(
            {
                "version": "1.0",
                "root": {"type": "attribute", "field": "plan_tier", "operator": "eq", "value": "pro", "sneaky": True},
            }
        )


def test_negative_count_rejected():
    with pytest.raises(pydantic.ValidationError):
        SegmentDefinition.model_validate(
            {"version": "1.0", "root": {"type": "event", "event_name": "login", "operator": "count_gte", "count": -1}}
        )


def test_deep_nesting_beyond_max_depth_rejected():
    node = {"type": "attribute", "field": "seats", "operator": "gte", "value": 1}
    for _ in range(10):
        node = {"type": "not", "children": [node]}
    with pytest.raises(pydantic.ValidationError):
        SegmentDefinition.model_validate({"version": "1.0", "root": node})
