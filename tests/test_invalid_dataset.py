"""Guards the one property the safety eval stands or falls on: that every
generated 'invalid' candidate is genuinely invalid against the real
validator, exactly the discipline
ontology-grounded-operations-agent/tests/test_action_generator.py applies to
its own malformed-proposal generator."""
from segment_builder.invalid_dataset import TARGET_SIZE, _MUTATIONS, build_invalid_dataset
from segment_builder.validator import SegmentValidationError, SegmentValidator


def test_dataset_has_target_size():
    assert len(build_invalid_dataset()) == TARGET_SIZE


def test_dataset_is_reproducible_for_a_fixed_seed():
    a = build_invalid_dataset(seed=1)
    b = build_invalid_dataset(seed=1)
    assert [c.candidate for c in a] == [c.candidate for c in b]


def test_every_mutation_kind_is_represented():
    cases = build_invalid_dataset()
    kinds_seen = {c.mutation_kind for c in cases}
    assert kinds_seen == set(_MUTATIONS.keys())


def test_every_case_genuinely_fails_the_real_validator():
    failures = []
    for case in build_invalid_dataset():
        try:
            SegmentValidator.validate(case.candidate)
            failures.append(case)
        except SegmentValidationError:
            pass
    assert failures == [], f"{len(failures)} candidates were meant to be invalid but the validator accepted them"
