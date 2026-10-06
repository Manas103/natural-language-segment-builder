"""Writes an approved, human-confirmed segment's membership list back to a
vendor system of record through its REST API.

"Vendor system of record" rather than a vendor name is deliberate: see the
README's Honest framing. The REST semantics and the 100-requests-per-10-
seconds budget are the documented Quickbase ones
(https://help.quickbase.com/docs/rate-limiting-overview,
https://help.quickbase.com/docs/limits-in-quickbase), modeled against the
authored VendorAPIServer in vendor_api.py, not against a live Quickbase app.

Idempotency is the whole design: each batch's upsert payload is the final
truth for that batch (every profile_id's membership, not a delta), and its
idempotency key is a deterministic hash of (segment_id, sorted profile_ids in
the batch). Sending the same batch twice, or receiving it out of order
relative to other batches, produces the same final state, because every batch
is self-contained and the server recognizes a repeated key before reapplying
anything. That is what makes "lands exactly once under a duplicated, reordered
retry stream" a provable property instead of a hope.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from segment_builder.rate_limiter import SlidingWindowRateLimiter
from segment_builder.vendor_api import UPSERT_PATH


class WriteBackError(RuntimeError):
    pass


def batch_idempotency_key(segment_id: str, profile_ids: list[str]) -> str:
    """Deterministic: the same segment_id and the same set of profile_ids
    always produce the same key, regardless of input order, so a retried or
    reordered copy of a batch is recognized as the batch it already is."""
    payload = json.dumps({"segment_id": segment_id, "profile_ids": sorted(profile_ids)}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class BatchRequest:
    """One self-contained, idempotent upsert call: everything the server
    needs to apply or recognize-as-duplicate this batch, with no reference to
    any other batch's state."""

    idempotency_key: str
    segment_id: str
    profile_ids: tuple[str, ...]

    def to_body(self) -> dict:
        return {
            "idempotency_key": self.idempotency_key,
            "segment_id": self.segment_id,
            "records": [{"profile_id": pid, "included": True} for pid in self.profile_ids],
        }


def build_batch_requests(profile_ids: list[str], segment_id: str, batch_size: int) -> list[BatchRequest]:
    batches: list[BatchRequest] = []
    for i in range(0, len(profile_ids), batch_size):
        chunk = tuple(profile_ids[i : i + batch_size])
        batches.append(BatchRequest(batch_idempotency_key(segment_id, list(chunk)), segment_id, chunk))
    return batches


@dataclass
class WriteBackReceipt:
    segment_id: str
    profile_count: int
    batches_sent: int
    duplicates_sent: int = 0


@dataclass
class VendorWriteBackClient:
    base_url: str
    batch_size: int = 25
    max_requests_per_window: int = 100
    window_seconds: float = 10.0
    max_retries: int = 5
    _limiter: SlidingWindowRateLimiter = field(init=False)

    def __post_init__(self) -> None:
        self._limiter = SlidingWindowRateLimiter(self.max_requests_per_window, self.window_seconds)

    def write_back(self, profile_ids: list[str], segment_id: str) -> WriteBackReceipt:
        batches = build_batch_requests(profile_ids, segment_id, self.batch_size)
        for batch in batches:
            self._send_with_retry(batch)
        return WriteBackReceipt(segment_id=segment_id, profile_count=len(profile_ids), batches_sent=len(batches))

    def send_batch(self, batch: BatchRequest) -> dict:
        """Paces itself under this client's own rate limiter (self-throttling,
        independent of any 429 from the server), then sends one real HTTP
        POST. Exposed directly so a retry-stream replay can reuse the same
        wire format without going through write_back()'s batching."""
        self._limiter.acquire()
        return self._post(batch.to_body())

    def _send_with_retry(self, batch: BatchRequest) -> dict:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return self.send_batch(batch)
            except WriteBackError as exc:
                last_error = exc
        raise WriteBackError(f"batch {batch.idempotency_key} failed after {self.max_retries} attempts: {last_error}")

    def _post(self, body: dict) -> dict:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{UPSERT_PATH}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise WriteBackError("rate limited by server (429)") from exc
            raise WriteBackError(f"vendor API returned HTTP {exc.code}: {exc.read()[:300]!r}") from exc
        except urllib.error.URLError as exc:
            raise WriteBackError(f"could not reach vendor API: {exc}") from exc
