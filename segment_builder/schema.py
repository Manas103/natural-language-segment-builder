"""The typed SegmentDefinition schema.

Every segment a request can produce is one of three node shapes: an event
predicate, an attribute predicate, or a boolean composite (AND / OR / NOT) over
child nodes. `extra="forbid"` on every model means an unexpected key is a schema
violation, not a silently-ignored field, the same defense
`ontology-grounded-operations-agent`'s action schemas use `additionalProperties:
false` for.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from segment_builder.fields import (
    ATTRIBUTE_FIELDS_BY_NAME,
    EVENT_COUNT_OPERATORS,
    EVENT_NAMES,
    OPERATORS_BY_TYPE,
)

MAX_TREE_DEPTH = 8


class SegmentValidationError(ValueError):
    """Raised for any candidate that cannot be expressed in the typed schema."""


class EventPredicate(BaseModel, extra="forbid"):
    type: Literal["event"]
    event_name: str
    operator: Literal[
        "count_gte", "count_gt", "count_lte", "count_lt", "count_eq"
    ]
    count: int = Field(ge=0)
    within_days: int | None = Field(default=None, gt=0)

    @field_validator("event_name")
    @classmethod
    def _known_event(cls, v: str) -> str:
        if v not in EVENT_NAMES:
            raise SegmentValidationError(f"unknown event name: {v!r}")
        return v

    @field_validator("operator")
    @classmethod
    def _known_operator(cls, v: str) -> str:
        if v not in EVENT_COUNT_OPERATORS:
            raise SegmentValidationError(f"unknown event operator: {v!r}")
        return v


class AttributePredicate(BaseModel, extra="forbid"):
    type: Literal["attribute"]
    field: str
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "contains"]
    value: str | int | float | bool | list[str]

    @model_validator(mode="after")
    def _field_operator_and_value_are_consistent(self) -> "AttributePredicate":
        spec = ATTRIBUTE_FIELDS_BY_NAME.get(self.field)
        if spec is None:
            raise SegmentValidationError(f"unknown attribute field: {self.field!r}")
        allowed_ops = OPERATORS_BY_TYPE[spec.type]
        if self.operator not in allowed_ops:
            raise SegmentValidationError(
                f"operator {self.operator!r} is not valid for field "
                f"{self.field!r} of type {spec.type!r} (allowed: {allowed_ops})"
            )
        if self.operator == "in":
            if not isinstance(self.value, list):
                raise SegmentValidationError("operator 'in' requires a list value")
            if spec.type == "enum" and spec.enum_values:
                bad = [v for v in self.value if v not in spec.enum_values]
                if bad:
                    raise SegmentValidationError(
                        f"value(s) {bad} not in allowed enum values {spec.enum_values} "
                        f"for field {self.field!r}"
                    )
        else:
            if isinstance(self.value, list):
                raise SegmentValidationError(
                    f"operator {self.operator!r} does not accept a list value"
                )
            type_ok = {
                "string": isinstance(self.value, str),
                "int": isinstance(self.value, int) and not isinstance(self.value, bool),
                "float": isinstance(self.value, (int, float)) and not isinstance(self.value, bool),
                "bool": isinstance(self.value, bool),
                "enum": isinstance(self.value, str),
            }[spec.type]
            if not type_ok:
                raise SegmentValidationError(
                    f"value {self.value!r} has the wrong type for field "
                    f"{self.field!r} ({spec.type!r})"
                )
            if spec.type == "enum" and spec.enum_values and self.value not in spec.enum_values:
                raise SegmentValidationError(
                    f"value {self.value!r} not in allowed enum values "
                    f"{spec.enum_values} for field {self.field!r}"
                )
        return self


PredicateNode = Annotated[
    Union[EventPredicate, AttributePredicate, "Composite"],
    Field(discriminator="type"),
]


class Composite(BaseModel, extra="forbid"):
    type: Literal["and", "or", "not"]
    children: list[PredicateNode]

    @model_validator(mode="after")
    def _child_count_matches_operator(self) -> "Composite":
        n = len(self.children)
        if self.type == "not" and n != 1:
            raise SegmentValidationError(f"'not' requires exactly 1 child, got {n}")
        if self.type in ("and", "or") and n < 2:
            raise SegmentValidationError(f"'{self.type}' requires at least 2 children, got {n}")
        return self


Composite.model_rebuild()


class SegmentDefinition(BaseModel, extra="forbid"):
    version: Literal["1.0"] = "1.0"
    root: PredicateNode

    @model_validator(mode="after")
    def _depth_is_bounded(self) -> "SegmentDefinition":
        if _depth(self.root) > MAX_TREE_DEPTH:
            raise SegmentValidationError(f"predicate tree exceeds max depth {MAX_TREE_DEPTH}")
        return self


def _depth(node: EventPredicate | AttributePredicate | Composite) -> int:
    if isinstance(node, Composite):
        return 1 + max((_depth(c) for c in node.children), default=0)
    return 1


SegmentDefinition.model_rebuild()
