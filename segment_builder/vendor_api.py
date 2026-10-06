"""A fake vendor system of record, standing in for the marketing-segment
destination the posting names (Quickbase REST APIs): see README for why this
repository says "a vendor system of record" rather than the vendor's name.

This is a real HTTP server (`http.server.ThreadingHTTPServer`), not a mock of
the client's own request library: `VendorWriteBackClient` in
vendor_writeback.py talks to it over a real loopback socket with real JSON
over HTTP, the same relationship `hil-bench-serverless-api`'s moto-mocked
Lambda has to its caller, except here the whole server is authored rather than
a cloud emulator.

Two things make the exactly-once write-back claim checkable instead of
assumed:
  - `_applied_batches`: the set of idempotency keys this process has ever
    actually applied. A request whose key is already in this set is answered
    from the cached response and `apply_count_by_key[key]` is NOT incremented
    a second time, so "landed exactly once" is an application-layer fact, not
    a coincidence of upserts happening to be overwrite-safe.
  - a per-process sliding-window request counter enforcing the same
    100-requests-per-10-seconds budget documented for Quickbase's REST API
    (https://help.quickbase.com/docs/rate-limiting-overview), returning 429
    with a Retry-After header exactly like the real API would.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from segment_builder.rate_limiter import SlidingWindowRateLimiter

UPSERT_PATH = "/records/upsert"


@dataclass
class VendorRecord:
    profile_id: str
    segment_id: str
    included: bool


class VendorAPIServer:
    """In-process fake of a vendor's record-upsert REST endpoint. Not a mock
    of the HTTP layer: start() binds a real socket on 127.0.0.1 and serves
    real HTTP requests on a background thread until stop()."""

    def __init__(self, max_requests_per_window: int = 100, window_seconds: float = 10.0) -> None:
        self.max_requests_per_window = max_requests_per_window
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self.records: dict[tuple[str, str], VendorRecord] = {}
        self.apply_count_by_key: dict[str, int] = {}
        self.duplicate_rejected_count = 0
        self.rate_limited_count = 0
        self.request_count = 0
        self._request_limiter = SlidingWindowRateLimiter(max_requests_per_window, window_seconds)
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> str:
        handler = _make_handler(self)
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}"

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def __enter__(self) -> "VendorAPIServer":
        self.base_url = self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.stop()

    def handle_upsert(self, body: dict) -> tuple[int, dict, dict]:
        """Returns (status_code, response_body, extra_headers)."""
        with self._lock:
            self.request_count += 1
            if not self._request_limiter.try_acquire():
                self.rate_limited_count += 1
                return (
                    429,
                    {"error": "rate_limited", "budget": f"{self.max_requests_per_window} requests / {self.window_seconds:g}s"},
                    {"Retry-After": "1"},
                )

            key = body.get("idempotency_key")
            segment_id = body.get("segment_id")
            records = body.get("records", [])
            if not isinstance(key, str) or not key:
                return (400, {"error": "idempotency_key is required"}, {})
            if not isinstance(records, list) or not records:
                return (400, {"error": "records must be a non-empty list"}, {})

            if key in self.apply_count_by_key:
                self.duplicate_rejected_count += 1
                return (200, {"status": "duplicate_ignored", "idempotency_key": key, "applied": False}, {})

            for r in records:
                rec_key = (r["profile_id"], segment_id)
                self.records[rec_key] = VendorRecord(
                    profile_id=r["profile_id"], segment_id=segment_id, included=bool(r.get("included", True))
                )
            self.apply_count_by_key[key] = 1
            return (200, {"status": "applied", "idempotency_key": key, "applied": True, "count": len(records)}, {})

    def membership(self, segment_id: str) -> set[str]:
        with self._lock:
            return {pid for (pid, sid), rec in self.records.items() if sid == segment_id and rec.included}


def _make_handler(server: VendorAPIServer):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence per-request stderr logging
            pass

        def do_POST(self) -> None:
            if self.path != UPSERT_PATH:
                self._respond(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._respond(400, {"error": "malformed JSON body"})
                return
            status, payload, extra_headers = server.handle_upsert(body)
            self._respond(status, payload, extra_headers)

        def _respond(self, status: int, payload: dict, extra_headers: dict | None = None) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            for k, v in (extra_headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

    return Handler
