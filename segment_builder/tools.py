"""The tool calls a model (or the deterministic stand-in) uses to build up a
SegmentDefinition incrementally, node by node, instead of emitting the whole
JSON tree in one shot. This is the plain-English-to-typed-segment path: every
LLM client in llm_client.py drives a request through exactly this API.

Each tool call takes only field names, operators, and literal values that
appear in the model's own plain-English input, or that were echoed back to it
from a previous tool call's returned node id. No SegmentBuilderSession method
ever reads or accepts profile data; there is no argument shape through which a
profile row could flow into a tool call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class BuilderError(ValueError):
    """A tool call was invoked in an invalid order or with a bad reference."""


@dataclass
class SegmentBuilderSession:
    """Holds the in-progress node graph for one request. Node ids are small
    integers assigned in call order so a model can refer back to earlier
    tool-call results ("combine node 0 and node 1 with AND")."""

    nodes: dict[int, dict] = field(default_factory=dict)
    _next_id: int = 0
    root_id: int | None = None
    finalized: bool = False

    def _alloc(self, node: dict) -> int:
        node_id = self._next_id
        self.nodes[node_id] = node
        self._next_id += 1
        return node_id

    def add_event_predicate(
        self, event_name: str, operator: str, count: int, within_days: int | None = None
    ) -> int:
        if self.finalized:
            raise BuilderError("session already finalized")
        node: dict[str, Any] = {
            "type": "event",
            "event_name": event_name,
            "operator": operator,
            "count": count,
        }
        if within_days is not None:
            node["within_days"] = within_days
        return self._alloc(node)

    def add_attribute_predicate(self, field_name: str, operator: str, value: Any) -> int:
        if self.finalized:
            raise BuilderError("session already finalized")
        return self._alloc({"type": "attribute", "field": field_name, "operator": operator, "value": value})

    def combine(self, boolean_type: str, child_ids: list[int]) -> int:
        if self.finalized:
            raise BuilderError("session already finalized")
        if boolean_type not in ("and", "or"):
            raise BuilderError(f"combine() boolean_type must be 'and' or 'or', got {boolean_type!r}")
        missing = [i for i in child_ids if i not in self.nodes]
        if missing:
            raise BuilderError(f"combine() referenced unknown node ids: {missing}")
        return self._alloc({"type": boolean_type, "children": [self.nodes[i] for i in child_ids]})

    def negate(self, child_id: int) -> int:
        if self.finalized:
            raise BuilderError("session already finalized")
        if child_id not in self.nodes:
            raise BuilderError(f"negate() referenced unknown node id: {child_id}")
        return self._alloc({"type": "not", "children": [self.nodes[child_id]]})

    def finalize_segment(self, root_id: int) -> dict:
        if root_id not in self.nodes:
            raise BuilderError(f"finalize_segment() referenced unknown node id: {root_id}")
        self.root_id = root_id
        self.finalized = True
        return {"version": "1.0", "root": self.nodes[root_id]}


# JSON-serializable tool definitions, in the shape an LLM tool-calling API (and
# the `claude -p` prompt in llm_client.ClaudeCLIClient) expects. Kept alongside
# SegmentBuilderSession so the two can never drift out of sync.
TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "add_event_predicate",
        "description": "Add a predicate on how many times a named event happened, optionally within a recency window.",
        "parameters": {
            "event_name": "string, one of the provided event names",
            "operator": "one of count_gte, count_gt, count_lte, count_lt, count_eq",
            "count": "non-negative integer",
            "within_days": "optional positive integer, recency window in days",
        },
        "returns": "integer node id",
    },
    {
        "name": "add_attribute_predicate",
        "description": "Add a predicate on a profile attribute field, by name and type only, never a value drawn from real data.",
        "parameters": {
            "field_name": "string, one of the provided attribute field names",
            "operator": "one of eq, neq, gt, gte, lt, lte, in, contains, valid for the field's type",
            "value": "literal matching the field's type",
        },
        "returns": "integer node id",
    },
    {
        "name": "combine",
        "description": "Combine two or more existing nodes with AND or OR.",
        "parameters": {"boolean_type": "'and' or 'or'", "child_ids": "list of at least 2 existing node ids"},
        "returns": "integer node id",
    },
    {
        "name": "negate",
        "description": "Wrap one existing node in NOT.",
        "parameters": {"child_id": "existing node id"},
        "returns": "integer node id",
    },
    {
        "name": "finalize_segment",
        "description": "Declare which node id is the root of the finished segment definition.",
        "parameters": {"root_id": "existing node id"},
        "returns": "the finished SegmentDefinition dict",
    },
]
