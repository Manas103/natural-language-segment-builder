"""Compiles a QuerySpec to real SQL against the sales_fact table, using only
the sql_expression and column names declared in semantic_model.py. No
question text, template or model output ever reaches this function; it only
ever sees a validated QuerySpec.
"""
from .query_spec import QuerySpec
from .semantic_model import DIMENSION_BY_NAME, METRIC_BY_NAME

TABLE = "sales_fact"


def compile_sql(spec: QuerySpec) -> str:
    metric = METRIC_BY_NAME[spec.metric]
    select_parts = []
    group_cols = []
    for dim_name in spec.group_by:
        dim = DIMENSION_BY_NAME[dim_name]
        select_parts.append(dim.column)
        group_cols.append(dim.column)
    select_parts.append(f"{metric.sql_expression} AS {metric.name}")

    where_parts = []
    for f in spec.filters:
        dim = DIMENSION_BY_NAME[f.dimension]
        escaped = f.value.replace("'", "''")
        where_parts.append(f"{dim.column} {f.op} '{escaped}'")

    sql = f"SELECT {', '.join(select_parts)} FROM {TABLE}"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    if group_cols:
        sql += " GROUP BY " + ", ".join(group_cols)
        sql += " ORDER BY " + ", ".join(group_cols)
    return sql
