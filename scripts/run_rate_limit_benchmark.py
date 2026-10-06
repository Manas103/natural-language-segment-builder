"""Real wall-clock demonstration that VendorWriteBackClient stays inside the
documented 100-requests-per-10-seconds vendor budget while writing back a
segment large enough to need more than one window. Unlike
tests/test_rate_limiter.py (which proves the pacing algorithm correct with a
fake clock, fast and deterministic), this script uses the real clock end to
end against a real local VendorAPIServer, so the elapsed time it reports is a
genuine measurement, not a simulation. It takes roughly 20 to 25 seconds to
run because it is honestly paced at the real budget.
"""
from __future__ import annotations

import time

from segment_builder.vendor_api import VendorAPIServer
from segment_builder.vendor_writeback import VendorWriteBackClient, build_batch_requests

N_PROFILES = 2300
BATCH_SIZE = 10  # -> 230 batches -> 230 requests, enough to span 2 full 10s windows


def _max_requests_in_any_10s_window(timestamps: list[float], window_seconds: float = 10.0) -> int:
    return max(
        (sum(1 for other in timestamps if t - window_seconds < other <= t) for t in timestamps),
        default=0,
    )


def main() -> int:
    profile_ids = [f"P-{i:05d}" for i in range(N_PROFILES)]
    batches = build_batch_requests(profile_ids, "seg-rate-limit-demo", batch_size=BATCH_SIZE)

    with VendorAPIServer(max_requests_per_window=100, window_seconds=10.0) as server:
        client = VendorWriteBackClient(server.base_url, batch_size=BATCH_SIZE)
        send_timestamps: list[float] = []
        start = time.monotonic()
        for batch in batches:
            client.send_batch(batch)
            send_timestamps.append(time.monotonic())
        elapsed = time.monotonic() - start

        peak = _max_requests_in_any_10s_window(send_timestamps)
        print(f"batches sent: {len(batches)}")
        print(f"elapsed wall-clock time: {elapsed:.2f}s")
        print(f"peak requests observed in any real 10s window: {peak} (budget: 100)")
        print(f"server rejected_count (should be 0, client never needed a 429 to stay in budget): {server.rate_limited_count}")
        print(f"server request_count: {server.request_count}")
        ok = peak <= 100 and server.rate_limited_count == 0
        print(f"RESULT: {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
