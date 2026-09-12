"""Proves, by construction, that no profile data is ever sent to a model.

Both clients are handed only request_text plus (for the real client)
fields.schema_metadata_for_prompt(). This test builds a real synthetic
ProfileStore, samples several genuine profile_ids and attribute values out of
it, drives both clients on a batch of requests, and asserts none of those
sampled values appear anywhere in the deterministic client's recorded input
or the real client's exact prompt string.
"""
import json

from segment_builder.eval_dataset import build_eval_dataset
from segment_builder.fields import schema_metadata_for_prompt
from segment_builder.llm_client import ClaudeCLIClient, DeterministicIntentParserClient
from segment_builder.store import ProfileStore


def _sample_profile_values(store: ProfileStore) -> list[str]:
    """Values that identify a specific profile *row*, as opposed to schema
    vocabulary. Enum labels such as 'pro' or 'US' are deliberately excluded:
    those are field-domain metadata (part of the schema every client is meant
    to receive), not row content. profile_ids and per-profile numeric
    measurements are the things that must never leak."""
    needles: list[str] = []
    for p in store.profiles[:25]:
        needles.append(p.profile_id)
        for e in p.events:
            needles.append(f"{e.name}@{e.days_ago}d")
    return needles


def test_deterministic_client_input_never_contains_profile_data():
    store = ProfileStore.synthetic(n=500, seed=42)
    needles = _sample_profile_values(store)
    client = DeterministicIntentParserClient()
    for case in build_eval_dataset()[:20]:
        try:
            client.build_segment(case.request_text)
        except Exception:
            pass
        assert client.last_request_text == case.request_text
        for needle in needles:
            assert needle not in client.last_request_text, f"profile value {needle!r} leaked into request text"


def test_claude_cli_client_prompt_never_contains_profile_data(monkeypatch):
    store = ProfileStore.synthetic(n=500, seed=42)
    needles = [n for n in _sample_profile_values(store) if isinstance(n, str)]

    def fake_run(*args, **kwargs):
        class R:
            returncode = 0
            stdout = json.dumps(
                [{"tool": "add_attribute_predicate", "args": {"field_name": "plan_tier", "operator": "eq", "value": "pro"}},
                 {"tool": "finalize_segment", "args": {"root_id": 0}}]
            )
            stderr = ""
        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    client = ClaudeCLIClient()
    for case in build_eval_dataset()[:20]:
        client.build_segment(case.request_text)
        assert client.last_prompt is not None
        for needle in needles:
            assert needle not in client.last_prompt, f"profile value {needle!r} leaked into prompt"


def test_schema_metadata_contains_no_profile_shaped_content():
    store = ProfileStore.synthetic(n=200, seed=1)
    real_ids = {p.profile_id for p in store.profiles}
    metadata_str = json.dumps(schema_metadata_for_prompt())
    assert not any(pid in metadata_str for pid in real_ids)
    # the metadata is names/types only: no numeric profile attribute values
    # (lifetime_value, account_age_days, seats) ever appear as literals in it
    for p in store.profiles[:10]:
        assert str(p.attributes["lifetime_value"]) not in metadata_str
