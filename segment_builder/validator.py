"""The single gate between a candidate segment definition and execution.

Mirrors `ontology-grounded-operations-agent`'s `ActionValidator`: nothing is
executed (run against the profile store to produce a count) unless it first
survives `SegmentValidator.validate`, which can only construct a
`SegmentDefinition` by pydantic's own validators succeeding. There is no second,
looser code path that skips this gate.
"""
from __future__ import annotations

from typing import Any

import pydantic

from segment_builder.schema import SegmentDefinition, SegmentValidationError

__all__ = ["SegmentValidationError", "SegmentValidator", "ValidatedSegment"]


class ValidatedSegment:
    """A wrapper that can only be constructed by SegmentValidator.validate
    succeeding. Execution code accepts only this type, never a raw dict."""

    __slots__ = ("definition",)

    def __init__(self, definition: SegmentDefinition) -> None:
        self.definition = definition


class SegmentValidator:
    @staticmethod
    def validate(candidate: Any) -> ValidatedSegment:
        if not isinstance(candidate, dict):
            raise SegmentValidationError(
                f"candidate segment definition must be a dict, got {type(candidate).__name__}"
            )
        try:
            definition = SegmentDefinition.model_validate(candidate)
        except pydantic.ValidationError as exc:
            raise SegmentValidationError(str(exc)) from exc
        return ValidatedSegment(definition)
