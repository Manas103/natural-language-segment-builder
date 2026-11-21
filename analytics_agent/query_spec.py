"""QuerySpec: the only structure a question can be turned into before it is
compiled to SQL. Every field must name a declared metric or dimension; there
is no raw-SQL escape hatch.
"""
from dataclasses import dataclass, field

from .semantic_model import DIMENSION_NAMES, METRIC_NAMES


@dataclass(frozen=True)
class Filter:
    dimension: str
    op: str  # "=" or "!="
    value: str


@dataclass(frozen=True)
class QuerySpec:
    metric: str
    group_by: tuple = ()
    filters: tuple = ()

    def __post_init__(self):
        if self.metric not in METRIC_NAMES:
            raise ValueError(f"metric '{self.metric}' is not in the governed semantic model")
        for dim in self.group_by:
            if dim not in DIMENSION_NAMES:
                raise ValueError(f"dimension '{dim}' is not in the governed semantic model")
        for f in self.filters:
            if f.dimension not in DIMENSION_NAMES:
                raise ValueError(f"dimension '{f.dimension}' is not in the governed semantic model")
