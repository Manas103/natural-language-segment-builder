"""A synthetic profile store, seeded and reproducible.

No real user data. `execute_segment` is the only place a validated segment
definition is actually run; it is what "the live count" and "executed" mean
throughout this repository.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from segment_builder.fields import ATTRIBUTE_FIELDS, EVENTS
from segment_builder.schema import AttributePredicate, Composite, EventPredicate, SegmentDefinition
from segment_builder.validator import ValidatedSegment

DEFAULT_SEED = 20260901
DEFAULT_PROFILE_COUNT = 5000
_NOW = datetime(2026, 9, 12)


@dataclass
class Event:
    name: str
    days_ago: int


@dataclass
class Profile:
    profile_id: str
    attributes: dict = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)


def generate_synthetic_profiles(
    n: int = DEFAULT_PROFILE_COUNT, seed: int = DEFAULT_SEED
) -> list[Profile]:
    rng = random.Random(seed)
    profiles: list[Profile] = []
    for i in range(n):
        attrs: dict = {}
        for f in ATTRIBUTE_FIELDS:
            if f.type == "enum":
                attrs[f.name] = rng.choice(f.enum_values)
            elif f.type == "int":
                attrs[f.name] = rng.randint(0, 2000) if f.name == "account_age_days" else rng.randint(0, 50)
            elif f.type == "float":
                attrs[f.name] = round(rng.uniform(0, 50000), 2)
            elif f.type == "bool":
                attrs[f.name] = rng.random() < 0.3
        n_events = rng.randint(0, 40)
        events = [
            Event(name=rng.choice([e.name for e in EVENTS]), days_ago=rng.randint(0, 400))
            for _ in range(n_events)
        ]
        profiles.append(Profile(profile_id=f"P-{i:06d}", attributes=attrs, events=events))
    return profiles


class ProfileStore:
    def __init__(self, profiles: list[Profile]) -> None:
        self.profiles = profiles

    @classmethod
    def synthetic(cls, n: int = DEFAULT_PROFILE_COUNT, seed: int = DEFAULT_SEED) -> "ProfileStore":
        return cls(generate_synthetic_profiles(n, seed))

    def execute_segment(self, validated: ValidatedSegment) -> int:
        """Run a validated segment definition against every profile and return
        the live count of matches. This is the only function in the repository
        that reads `Profile` content; nothing upstream of validation ever sees it."""
        return sum(1 for p in self.profiles if _matches(validated.definition.root, p))

    def matching_ids(self, validated: ValidatedSegment) -> list[str]:
        return [p.profile_id for p in self.profiles if _matches(validated.definition.root, p)]


def _matches(node, profile: Profile) -> bool:
    if isinstance(node, EventPredicate):
        matching_events = [e for e in profile.events if e.name == node.event_name]
        if node.within_days is not None:
            matching_events = [e for e in matching_events if e.days_ago <= node.within_days]
        count = len(matching_events)
        return {
            "count_gte": count >= node.count,
            "count_gt": count > node.count,
            "count_lte": count <= node.count,
            "count_lt": count < node.count,
            "count_eq": count == node.count,
        }[node.operator]
    if isinstance(node, AttributePredicate):
        actual = profile.attributes.get(node.field)
        if node.operator == "eq":
            return actual == node.value
        if node.operator == "neq":
            return actual != node.value
        if node.operator == "gt":
            return actual is not None and actual > node.value
        if node.operator == "gte":
            return actual is not None and actual >= node.value
        if node.operator == "lt":
            return actual is not None and actual < node.value
        if node.operator == "lte":
            return actual is not None and actual <= node.value
        if node.operator == "in":
            return actual in node.value
        if node.operator == "contains":
            return isinstance(actual, str) and node.value in actual
        raise AssertionError(f"unhandled operator {node.operator!r}")
    if isinstance(node, Composite):
        if node.type == "and":
            return all(_matches(c, profile) for c in node.children)
        if node.type == "or":
            return any(_matches(c, profile) for c in node.children)
        if node.type == "not":
            return not _matches(node.children[0], profile)
    raise AssertionError(f"unhandled node type {type(node)!r}")
