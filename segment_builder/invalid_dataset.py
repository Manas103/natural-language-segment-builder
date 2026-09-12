"""Builds the 150-candidate safety eval set: deliberately invalid or malformed
SegmentDefinition candidates, standing in for what an unreliable tool-calling
model (or a hostile input) can produce. Every one of these must be rejected by
SegmentValidator before it is ever executed against the profile store.

Mirrors `ontology-grounded-operations-agent`'s `action_generator.py`: a fixed
set of mutation kinds applied to otherwise-valid seed definitions, with a
dedicated test (`tests/test_invalid_dataset.py`) proving every generated
candidate is genuinely invalid against the real validator, so the eventual
"150/150 rejected" number is not true for the meaningless reason that nothing
hard was ever thrown at it.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

DATASET_SEED = 20260906
TARGET_SIZE = 150

_VALID_EVENT = {"type": "event", "event_name": "login", "operator": "count_gte", "count": 3}
_VALID_ATTR = {"type": "attribute", "field": "plan_tier", "operator": "eq", "value": "pro"}
_VALID_AND = {"type": "and", "children": [_VALID_EVENT, dict(_VALID_ATTR)]}


@dataclass
class InvalidCase:
    id: str
    mutation_kind: str
    candidate: object


def _mk(kind: str, idx: int, candidate: object) -> InvalidCase:
    return InvalidCase(id=f"I-{idx:04d}", mutation_kind=kind, candidate=candidate)


def _unknown_event_name(rng: random.Random) -> dict:
    return {"version": "1.0", "root": {"type": "event", "event_name": "did_a_backflip", "operator": "count_gte", "count": 1}}


def _unknown_attribute_field(rng: random.Random) -> dict:
    return {"version": "1.0", "root": {"type": "attribute", "field": "shoe_size", "operator": "eq", "value": 9}}


def _wrong_type_value(rng: random.Random) -> dict:
    return {"version": "1.0", "root": {"type": "attribute", "field": "seats", "operator": "gte", "value": "many"}}


def _invalid_operator_for_type(rng: random.Random) -> dict:
    return {"version": "1.0", "root": {"type": "attribute", "field": "seats", "operator": "contains", "value": 3}}


def _negative_count(rng: random.Random) -> dict:
    return {"version": "1.0", "root": {"type": "event", "event_name": "login", "operator": "count_gte", "count": -5}}


def _zero_within_days(rng: random.Random) -> dict:
    return {"version": "1.0", "root": {"type": "event", "event_name": "login", "operator": "count_gte", "count": 1, "within_days": 0}}


def _missing_required_field(rng: random.Random) -> dict:
    return {"version": "1.0", "root": {"type": "event", "operator": "count_gte", "count": 1}}


def _extra_disallowed_field(rng: random.Random) -> dict:
    node = dict(_VALID_ATTR)
    node["override_validation"] = True
    return {"version": "1.0", "root": node}


def _unknown_node_type(rng: random.Random) -> dict:
    return {"version": "1.0", "root": {"type": "xor", "children": [_VALID_EVENT, dict(_VALID_ATTR)]}}


def _and_with_zero_children(rng: random.Random) -> dict:
    return {"version": "1.0", "root": {"type": "and", "children": []}}


def _and_with_one_child(rng: random.Random) -> dict:
    return {"version": "1.0", "root": {"type": "and", "children": [_VALID_EVENT]}}


def _not_with_two_children(rng: random.Random) -> dict:
    return {"version": "1.0", "root": {"type": "not", "children": [_VALID_EVENT, dict(_VALID_ATTR)]}}


def _non_dict_root_int(rng: random.Random) -> dict:
    return {"version": "1.0", "root": 42}


def _non_dict_root_string(rng: random.Random) -> dict:
    return {"version": "1.0", "root": "logged in at least 3 times"}


def _non_dict_root_list(rng: random.Random) -> dict:
    return {"version": "1.0", "root": [_VALID_EVENT]}


def _non_dict_root_none(rng: random.Random) -> dict:
    return {"version": "1.0", "root": None}


def _candidate_not_a_dict_at_all(rng: random.Random) -> object:
    return rng.choice([None, 42, "just a string", [_VALID_AND], True])


def _malformed_nested_child(rng: random.Random) -> dict:
    return {
        "version": "1.0",
        "root": {"type": "and", "children": [_VALID_EVENT, {"type": "attribute", "field": "not_a_field", "operator": "eq", "value": 1}]},
    }


def _enum_value_not_in_allowed_set(rng: random.Random) -> dict:
    return {"version": "1.0", "root": {"type": "attribute", "field": "plan_tier", "operator": "eq", "value": "ultra_platinum"}}


def _in_operator_without_list(rng: random.Random) -> dict:
    return {"version": "1.0", "root": {"type": "attribute", "field": "country", "operator": "in", "value": "US"}}


_MUTATIONS = {
    "unknown_event_name": _unknown_event_name,
    "unknown_attribute_field": _unknown_attribute_field,
    "wrong_type_value": _wrong_type_value,
    "invalid_operator_for_type": _invalid_operator_for_type,
    "negative_count": _negative_count,
    "zero_within_days": _zero_within_days,
    "missing_required_field": _missing_required_field,
    "extra_disallowed_field": _extra_disallowed_field,
    "unknown_node_type": _unknown_node_type,
    "and_with_zero_children": _and_with_zero_children,
    "and_with_one_child": _and_with_one_child,
    "not_with_two_children": _not_with_two_children,
    "non_dict_root_int": _non_dict_root_int,
    "non_dict_root_string": _non_dict_root_string,
    "non_dict_root_list": _non_dict_root_list,
    "non_dict_root_none": _non_dict_root_none,
    "candidate_not_a_dict_at_all": _candidate_not_a_dict_at_all,
    "malformed_nested_child": _malformed_nested_child,
    "enum_value_not_in_allowed_set": _enum_value_not_in_allowed_set,
    "in_operator_without_list": _in_operator_without_list,
}


def build_invalid_dataset(seed: int = DATASET_SEED, size: int = TARGET_SIZE) -> list[InvalidCase]:
    rng = random.Random(seed)
    kinds = list(_MUTATIONS.keys())
    base_count, remainder = divmod(size, len(kinds))
    cases: list[InvalidCase] = []
    idx = 0
    for i, kind in enumerate(kinds):
        n = base_count + (1 if i < remainder else 0)
        for _ in range(n):
            idx += 1
            cases.append(_mk(kind, idx, _MUTATIONS[kind](rng)))
    assert len(cases) == size, f"expected {size} cases, built {len(cases)}"
    rng.shuffle(cases)
    return cases
