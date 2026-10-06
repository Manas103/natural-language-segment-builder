import json
import random
import urllib.request

import pytest

from segment_builder.llm_client import DeterministicIntentParserClient
from segment_builder.pipeline import SegmentBuilderPipeline, WriteBackNotConfirmedError
from segment_builder.store import ProfileStore
from segment_builder.vendor_api import UPSERT_PATH, VendorAPIServer
from segment_builder.vendor_writeback import VendorWriteBackClient, build_batch_requests


def _post_raw(base_url: str, body: dict) -> dict:
    """Posts directly to the server, bypassing VendorWriteBackClient's own
    pacing and retry logic, so this test's injected duplication and
    reordering happens at the transport layer, the same way
    corporate-action-event-ledger and embedded-fleet-provisioning inject
    duplication/reordering into their own replay streams rather than into
    the client under test."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}{UPSERT_PATH}", data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_write_back_lands_exactly_once_under_a_duplicated_reordered_retry_stream():
    profile_ids = [f"P-{i:05d}" for i in range(1000)]
    segment_id = "seg-retry-stream"
    batches = build_batch_requests(profile_ids, segment_id, batch_size=20)
    assert len(batches) == 50

    rng = random.Random(20260930)
    stream = list(batches)
    n_duplicates = round(0.05 * len(batches))  # 5% duplicated
    stream.extend(rng.choice(batches) for _ in range(n_duplicates))
    rng.shuffle(stream)  # fully reordered

    with VendorAPIServer() as server:
        for batch in stream:
            _post_raw(server.base_url, batch.to_body())

        assert server.membership(segment_id) == set(profile_ids)
        assert set(server.apply_count_by_key.keys()) == {b.idempotency_key for b in batches}
        assert all(count == 1 for count in server.apply_count_by_key.values())
        assert sum(server.apply_count_by_key.values()) == len(batches)
        assert server.duplicate_rejected_count == n_duplicates
        assert server.request_count == len(stream)


def test_write_back_client_reaches_the_same_exactly_once_state_through_real_retries():
    """Same property, exercised through VendorWriteBackClient.send_batch
    rather than a raw socket post, proving the production client's own wire
    format round-trips through the server's idempotency gate correctly."""
    profile_ids = [f"P-{i:04d}" for i in range(200)]
    segment_id = "seg-client-retry"
    with VendorAPIServer() as server:
        client = VendorWriteBackClient(server.base_url, batch_size=10)
        batches = build_batch_requests(profile_ids, segment_id, batch_size=10)
        rng = random.Random(7)
        stream = list(batches)
        stream.extend(rng.sample(batches, k=1))
        rng.shuffle(stream)
        for batch in stream:
            client.send_batch(batch)

        assert server.membership(segment_id) == set(profile_ids)
        assert all(count == 1 for count in server.apply_count_by_key.values())


def test_client_safety_margin_prevents_the_boundary_race_against_a_real_server():
    """Regression test for the race documented in rate_limiter.py and the
    README Findings: a client that paces to the exact edge of its own window
    can still get a real 429 from a server whose window is anchored to
    receipt time (which lags the client's send-time by one network delay).
    Uses a small, fast window (10 requests / 0.5s) rather than production's
    100/10s so the test runs in about a second instead of twenty, but it is
    the same real HTTP client against the same real server, crossing the
    same boundary more than once."""
    with VendorAPIServer(max_requests_per_window=10, window_seconds=0.5) as server:
        client = VendorWriteBackClient(
            server.base_url, batch_size=5, max_requests_per_window=10, window_seconds=0.5
        )
        profile_ids = [f"P-{i:04d}" for i in range(120)]
        batches = build_batch_requests(profile_ids, "seg-boundary-race", batch_size=5)
        for batch in batches:
            client.send_batch(batch)  # must not raise; the margin keeps it under the server's real budget
        assert server.rate_limited_count == 0
        assert server.membership("seg-boundary-race") == set(profile_ids)


def test_pipeline_write_back_approved_writes_only_the_confirmed_segments_matches():
    store = ProfileStore.synthetic(n=500, seed=11)
    pipeline = SegmentBuilderPipeline(DeterministicIntentParserClient(), store)
    preview = pipeline.build_preview("Users on the pro plan.")
    expected_ids = set(store.matching_ids(preview.validated))

    with VendorAPIServer() as server:
        client = VendorWriteBackClient(server.base_url, batch_size=15)
        with pytest.raises(WriteBackNotConfirmedError):
            pipeline.write_back_approved(preview, client, "seg-pro-plan")

        preview.confirm()
        receipt = pipeline.write_back_approved(preview, client, "seg-pro-plan")

        assert receipt.profile_count == len(expected_ids)
        assert server.membership("seg-pro-plan") == expected_ids
