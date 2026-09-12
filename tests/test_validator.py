import pytest

from segment_builder.invalid_dataset import build_invalid_dataset
from segment_builder.validator import SegmentValidationError, SegmentValidator, ValidatedSegment


def test_valid_candidate_produces_validated_segment():
    v = SegmentValidator.validate(
        {"version": "1.0", "root": {"type": "attribute", "field": "plan_tier", "operator": "eq", "value": "pro"}}
    )
    assert isinstance(v, ValidatedSegment)


def test_non_dict_candidate_rejected():
    with pytest.raises(SegmentValidationError):
        SegmentValidator.validate("not a dict")


@pytest.mark.parametrize("case", build_invalid_dataset(), ids=lambda c: c.id)
def test_every_invalid_dataset_case_is_rejected(case):
    with pytest.raises(SegmentValidationError):
        SegmentValidator.validate(case.candidate)
