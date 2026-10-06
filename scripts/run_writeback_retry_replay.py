"""Builds a real write-back batch stream for a confirmed segment, injects a
5% duplicate rate and a full reorder, replays it directly against a real
VendorAPIServer over loopback HTTP, and reports whether every batch landed
exactly once. This is the same scenario tests/test_vendor_writeback.py checks
with assertions; this script exists so the claim has a standalone,
re-runnable command with committed raw output (docs/writeback_retry_replay_output.txt).
"""
from __future__ import annotations

import json
import random
import urllib.request

from segment_builder.llm_client import DeterministicIntentParserClient
from segment_builder.pipeline import SegmentBuilderPipeline
from segment_builder.store import ProfileStore
from segment_builder.vendor_api import UPSERT_PATH, VendorAPIServer
from segment_builder.vendor_writeback import build_batch_requests

SEED = 20260930
BATCH_SIZE = 20
DUPLICATE_RATE = 0.05


def _post_raw(base_url: str, body: dict) -> None:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}{UPSERT_PATH}", data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        resp.read()


def main() -> int:
    store = ProfileStore.synthetic(n=5000, seed=42)
    pipeline = SegmentBuilderPipeline(DeterministicIntentParserClient(), store)
    preview = pipeline.build_preview("Users on the pro plan.")
    preview.confirm()
    profile_ids = store.matching_ids(preview.validated)
    segment_id = "seg-replay-demo"

    batches = build_batch_requests(profile_ids, segment_id, batch_size=BATCH_SIZE)

    rng = random.Random(SEED)
    stream = list(batches)
    n_duplicates = round(DUPLICATE_RATE * len(batches))
    stream.extend(rng.choice(batches) for _ in range(n_duplicates))
    rng.shuffle(stream)

    with VendorAPIServer() as server:
        for batch in stream:
            _post_raw(server.base_url, batch.to_body())

        expected = set(profile_ids)
        actual = server.membership(segment_id)
        exactly_once = all(c == 1 for c in server.apply_count_by_key.values())

        print(f"confirmed segment profile count: {len(profile_ids)}")
        print(f"unique batches: {len(batches)}")
        print(f"injected duplicates: {n_duplicates} (5% of {len(batches)})")
        print(f"replay stream length (reordered): {len(stream)}")
        print(f"server requests received: {server.request_count}")
        print(f"server duplicate_rejected_count: {server.duplicate_rejected_count}")
        print(f"final membership matches expected set exactly: {actual == expected}")
        print(f"every unique batch applied exactly once: {exactly_once}")
        print(f"sum of apply counts == unique batch count: {sum(server.apply_count_by_key.values()) == len(batches)}")

        ok = (actual == expected) and exactly_once and server.duplicate_rejected_count == n_duplicates
        print(f"RESULT: {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
