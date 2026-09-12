"""The 200-request accuracy eval, deterministic client.

Run: PYTHONPATH=. python scripts/run_accuracy_eval.py [--threshold N]

Exit code is non-zero if matched < threshold, so this script doubles as the
thing .github/workflows/eval-gate.yml invokes to gate a prompt/parser change.
"""
from __future__ import annotations

import argparse
import sys

from segment_builder.eval_dataset import build_eval_dataset
from segment_builder.llm_client import DeterministicIntentParserClient
from segment_builder.validator import SegmentValidator


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=int, default=184, help="minimum matches required to pass")
    args = parser.parse_args()

    cases = build_eval_dataset()
    client = DeterministicIntentParserClient()
    matched = 0
    mismatches: list[tuple[str, str, str]] = []

    for case in cases:
        try:
            candidate = client.build_segment(case.request_text)
            SegmentValidator.validate(candidate)
        except Exception as exc:
            mismatches.append((case.id, case.request_text, f"PARSE/VALIDATION ERROR: {exc}"))
            continue
        if candidate == case.expected:
            matched += 1
        else:
            mismatches.append((case.id, case.request_text, f"MISMATCH: got {candidate} expected {case.expected}"))

    print(f"total held-out requests: {len(cases)}")
    print(f"matched hand-written definitions: {matched} / {len(cases)}")
    print(f"ACCURACY: {matched / len(cases) * 100:.4f}%")
    print()
    print(f"--- {len(mismatches)} disclosed mismatches ---")
    for case_id, text, reason in mismatches:
        print(f"[{case_id}] {text!r}\n    {reason}")

    print()
    print(f"threshold: {args.threshold} / {len(cases)}")
    if matched < args.threshold:
        print("EVAL GATE: FAIL (accuracy below threshold)")
        return 1
    print("EVAL GATE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
