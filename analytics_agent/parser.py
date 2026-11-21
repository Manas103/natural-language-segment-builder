"""Deterministic NL-to-QuerySpec parser. Stands in for a real model the same
way DeterministicIntentParserClient does in segment_builder/intent_parser.py:
exactly reproducible and free to run at 350/60-question scale, with the same
tool-call-shaped output a real model-driven parser would produce. Refuses
(returns None) rather than guessing whenever any extracted phrase does not
exactly match a synonym declared in the governed semantic model, or the
sentence does not match a supported frame.

Supported frame: "what is the <metric>[ by <dim>[ and <dim>]][ where <dim> is
<value>[ and <dim> is <value>]]?" (also accepts "what's" for "what is").
Deliberately unsupported, and therefore a refusal or a dropped clause rather
than a crash: any other opening frame, and "equals"/"equal to" as a filter
operator (only "is" and "=" are recognized). These are real, disclosed gaps
in this parser's coverage, not synonyms missing from the semantic model.
"""
import re

from .query_spec import Filter, QuerySpec
from .semantic_model import DIMENSIONS, METRICS

_METRIC_SYNONYM_TO_NAME = {}
for m in METRICS:
    for syn in m.synonyms:
        _METRIC_SYNONYM_TO_NAME[syn.lower()] = m.name

_DIMENSION_SYNONYM_TO_NAME = {}
for d in DIMENSIONS:
    for syn in d.synonyms:
        _DIMENSION_SYNONYM_TO_NAME[syn.lower()] = d.name

_FRAME_RE = re.compile(
    r"^(?:what is|what's) the (?P<metric>.+?)"
    r"(?: by (?P<groupby>.+?))?"
    r"(?: where (?P<filters>.+?))?"
    r"\?$"
)

_FILTER_CLAUSE_RE = re.compile(r"^(?P<dim>.+?) (?:is|=) (?P<value>.+)$")


def parse(question: str) -> QuerySpec | None:
    text = question.strip().lower()
    match = _FRAME_RE.match(text)
    if not match:
        return None

    metric_phrase = match.group("metric").strip()
    metric_name = _METRIC_SYNONYM_TO_NAME.get(metric_phrase)
    if metric_name is None:
        return None

    group_by = []
    groupby_phrase = match.group("groupby")
    if groupby_phrase:
        for dim_phrase in groupby_phrase.split(" and "):
            dim_name = _DIMENSION_SYNONYM_TO_NAME.get(dim_phrase.strip())
            if dim_name is None:
                return None
            group_by.append(dim_name)

    filters = []
    filters_phrase = match.group("filters")
    if filters_phrase:
        for clause in filters_phrase.split(" and "):
            clause_match = _FILTER_CLAUSE_RE.match(clause.strip())
            if not clause_match:
                return None
            dim_phrase = clause_match.group("dim").strip()
            value = clause_match.group("value").strip()
            dim_name = _DIMENSION_SYNONYM_TO_NAME.get(dim_phrase)
            if dim_name is None:
                return None
            filters.append(Filter(dim_name, "=", value))

    try:
        return QuerySpec(metric=metric_name, group_by=tuple(group_by), filters=tuple(filters))
    except ValueError:
        return None
