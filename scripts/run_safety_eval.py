"""The 150-invalid-definition safety eval.

Every one of the 150 deliberately invalid/malformed candidate segment
definitions must be rejected by SegmentValidator before it would ever reach
ProfileStore.execute_segment. Run: PYTHONPATH=. python scripts/run_safety_eval.py
"""
from __future__ import annotations

import sys

from segment_builder.invalid_dataset import build_invalid_dataset
from segment_builder.store import ProfileStore
from segment_builder.validator import SegmentValidationError, SegmentValidator


def main() -> int:
    cases = build_invalid_dataset()
    store = ProfileStore.synthetic(n=500, seed=11)

    rejected = 0
    executed: list[tuple[str, str]] = []
    by_kind: dict[str, int] = {}

    for case in cases:
        by_kind.setdefault(case.mutation_kind, 0)
        try:
            validated = SegmentValidator.validate(case.candidate)
        except SegmentValidationError:
            rejected += 1
            by_kind[case.mutation_kind] += 1
            continue
        # If validation somehow succeeded, this candidate would be executable.
        store.execute_segment(validated)
        executed.append((case.id, case.mutation_kind))

    print(f"total deliberately invalid candidates: {len(cases)}")
    print()
    print("rejections by mutation kind:")
    for kind in sorted(by_kind):
        print(f"  {kind}: {by_kind[kind]}")
    print()
    print(f"correctly rejected by the validator: {rejected} / {len(cases)}")
    print(f"INVALID DEFINITIONS THAT EXECUTED: {len(executed)}")
    for case_id, kind in executed:
        print(f"  LEAK: {case_id} ({kind})")

    if executed:
        print("SAFETY GATE: FAIL")
        return 1
    print("SAFETY GATE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
