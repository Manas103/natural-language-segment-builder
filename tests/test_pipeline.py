import pytest

from segment_builder.llm_client import DeterministicIntentParserClient
from segment_builder.pipeline import SegmentBuildError, SegmentBuilderPipeline
from segment_builder.store import ProfileStore


def test_pipeline_builds_preview_with_live_count():
    store = ProfileStore.synthetic(n=1000, seed=3)
    pipeline = SegmentBuilderPipeline(DeterministicIntentParserClient(), store)
    preview = pipeline.build_preview("Users on the pro plan.")
    assert isinstance(preview.live_count, int)
    assert preview.live_count >= 0
    assert preview.confirmed is False


def test_confirm_does_not_change_the_count():
    store = ProfileStore.synthetic(n=1000, seed=3)
    pipeline = SegmentBuilderPipeline(DeterministicIntentParserClient(), store)
    preview = pipeline.build_preview("Users on the pro plan.")
    count_before = preview.live_count
    preview.confirm()
    assert preview.confirmed is True
    assert preview.live_count == count_before


def test_unparseable_request_raises_before_execution():
    store = ProfileStore.synthetic(n=1000, seed=3)
    pipeline = SegmentBuilderPipeline(DeterministicIntentParserClient(), store)
    with pytest.raises(Exception):
        pipeline.build_preview("Users who are secretly plotting something.")
