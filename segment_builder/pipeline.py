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
from segment_builder.vendor_writeback import VendorWriteBackClient, WriteBackReceipt


class SegmentBuildError(RuntimeError):
    pass


class WriteBackNotConfirmedError(RuntimeError):
    """Raised if write_back_approved is called on a preview a human has not
    confirmed. There is no code path from an unconfirmed preview to the
    vendor API."""


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

    def write_back_approved(
        self, preview: SegmentPreview, vendor_client: VendorWriteBackClient, segment_id: str
    ) -> WriteBackReceipt:
        """The governed write-back: only reachable after a human has called
        preview.confirm(), and only ever writes the profile ids the already-
        validated, already-counted definition actually matches (recomputed
        here rather than trusted from the preview, so a stale live_count
        can never be what gets written)."""
        if not preview.confirmed:
            raise WriteBackNotConfirmedError("cannot write back a segment that has not been confirmed")
        profile_ids = self.store.matching_ids(preview.validated)
        return vendor_client.write_back(profile_ids, segment_id)
