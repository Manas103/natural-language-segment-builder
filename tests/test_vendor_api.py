import json
import urllib.error
import urllib.request

import pytest

from segment_builder.vendor_api import UPSERT_PATH, VendorAPIServer


def _post(base_url: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}{UPSERT_PATH}", data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_upsert_is_applied_and_membership_reflects_it():
    with VendorAPIServer() as server:
        status, payload = _post(
            server.base_url,
            {
                "idempotency_key": "k1",
                "segment_id": "seg-1",
                "records": [{"profile_id": "P-1", "included": True}, {"profile_id": "P-2", "included": True}],
            },
        )
        assert status == 200
        assert payload["applied"] is True
        assert server.membership("seg-1") == {"P-1", "P-2"}


def test_repeated_idempotency_key_is_recognized_as_duplicate_not_reapplied():
    with VendorAPIServer() as server:
        body = {
            "idempotency_key": "k1",
            "segment_id": "seg-1",
            "records": [{"profile_id": "P-1", "included": True}],
        }
        status1, payload1 = _post(server.base_url, body)
        status2, payload2 = _post(server.base_url, dict(body))
        assert status1 == 200 and payload1["applied"] is True
        assert status2 == 200 and payload2["applied"] is False
        assert payload2["status"] == "duplicate_ignored"
        assert server.apply_count_by_key["k1"] == 1
        assert server.duplicate_rejected_count == 1


def test_missing_idempotency_key_is_rejected():
    with VendorAPIServer() as server:
        status, payload = _post(server.base_url, {"segment_id": "seg-1", "records": [{"profile_id": "P-1"}]})
        assert status == 400
        assert "idempotency_key" in payload["error"]


def test_empty_records_list_is_rejected():
    with VendorAPIServer() as server:
        status, _ = _post(server.base_url, {"idempotency_key": "k1", "segment_id": "seg-1", "records": []})
        assert status == 400


def test_exceeding_the_budget_returns_429_with_retry_after():
    with VendorAPIServer(max_requests_per_window=5, window_seconds=0.3) as server:
        statuses = []
        for i in range(8):
            status, _ = _post(
                server.base_url,
                {"idempotency_key": f"k{i}", "segment_id": "seg-1", "records": [{"profile_id": f"P-{i}"}]},
            )
            statuses.append(status)
        assert statuses[:5] == [200] * 5
        assert 429 in statuses[5:]
        assert server.rate_limited_count >= 1
