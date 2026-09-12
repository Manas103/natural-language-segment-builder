from segment_builder.eval_dataset import TARGET_SIZE, build_eval_dataset
from segment_builder.validator import SegmentValidationError, SegmentValidator


def test_dataset_has_target_size():
    assert len(build_eval_dataset()) == TARGET_SIZE


def test_dataset_is_reproducible_for_a_fixed_seed():
    a = build_eval_dataset(seed=1)
    b = build_eval_dataset(seed=1)
    assert [c.expected for c in a] == [c.expected for c in b]
    assert [c.request_text for c in a] == [c.request_text for c in b]


def test_every_expected_definition_is_itself_schema_valid():
    """The answer key must be expressible in the typed schema; if it were not,
    a 'match' against it would be meaningless."""
    failures = []
    for case in build_eval_dataset():
        try:
            SegmentValidator.validate(case.expected)
        except SegmentValidationError as exc:
            failures.append((case.id, str(exc)))
    assert failures == []


def test_request_ids_are_unique():
    cases = build_eval_dataset()
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids))
