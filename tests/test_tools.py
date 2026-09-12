import pytest

from segment_builder.tools import BuilderError, SegmentBuilderSession
from segment_builder.validator import SegmentValidator


def test_incremental_build_produces_valid_definition():
    s = SegmentBuilderSession()
    a = s.add_event_predicate("login", "count_gte", 3, within_days=30)
    b = s.add_attribute_predicate("plan_tier", "eq", "pro")
    c = s.combine("and", [a, b])
    definition = s.finalize_segment(c)
    validated = SegmentValidator.validate(definition)
    assert validated.definition.root.type == "and"


def test_negate_wraps_in_not():
    s = SegmentBuilderSession()
    a = s.add_attribute_predicate("is_trial", "eq", True)
    n = s.negate(a)
    definition = s.finalize_segment(n)
    assert definition["root"]["type"] == "not"


def test_combine_with_unknown_child_id_raises():
    s = SegmentBuilderSession()
    a = s.add_attribute_predicate("is_trial", "eq", True)
    with pytest.raises(BuilderError):
        s.combine("and", [a, 999])


def test_finalize_with_unknown_root_raises():
    s = SegmentBuilderSession()
    with pytest.raises(BuilderError):
        s.finalize_segment(0)


def test_cannot_add_after_finalize():
    s = SegmentBuilderSession()
    a = s.add_attribute_predicate("is_trial", "eq", True)
    s.finalize_segment(a)
    with pytest.raises(BuilderError):
        s.add_attribute_predicate("is_trial", "eq", False)
