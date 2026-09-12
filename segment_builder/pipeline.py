"""Wires the request -> tool calls -> typed definition -> validation -> live
count preview -> human confirmation path together. This module is the
executable description of the design claims: plain-English in, schema-
validated definition out, previewed as a live count before anything commits.
"""
from __future__ import annotations

from dataclasses import dataclass

from segment_builder.llm_client import LLMClient
from segment_builder.store import ProfileStore
from segment_builder.validator import SegmentValidationError, SegmentValidator, ValidatedSegment


class SegmentBuildError(RuntimeError):
    pass


@dataclass
class SegmentPreview:
    request_text: str
    validated: ValidatedSegment
    live_count: int
    confirmed: bool = False

    def confirm(self) -> ValidatedSegment:
        """A human confirms the preview. Nothing downstream of this call
        re-runs the model or re-validates; confirmation only flips a flag on
        an already-validated, already-counted segment."""
        self.confirmed = True
        return self.validated


class SegmentBuilderPipeline:
    """request_text -> LLMClient.build_segment (tool calls) -> raw candidate
    dict -> SegmentValidator.validate (schema gate) -> ProfileStore.execute_segment
    (live count) -> SegmentPreview, awaiting a human's confirm()."""

    def __init__(self, llm_client: LLMClient, store: ProfileStore) -> None:
        self.llm_client = llm_client
        self.store = store

    def build_preview(self, request_text: str) -> SegmentPreview:
        candidate = self.llm_client.build_segment(request_text)
        try:
            validated = SegmentValidator.validate(candidate)
        except SegmentValidationError as exc:
            raise SegmentBuildError(f"request could not be validated: {exc}") from exc
        live_count = self.store.execute_segment(validated)
        return SegmentPreview(request_text=request_text, validated=validated, live_count=live_count)
