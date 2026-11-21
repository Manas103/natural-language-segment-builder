from analytics_agent.query_spec import Filter, QuerySpec
from analytics_agent.sql_compiler import compile_sql


def test_compiles_simple_metric():
    sql = compile_sql(QuerySpec(metric="total_revenue"))
    assert "SUM(line_total)" in sql
    assert "FROM sales_fact" in sql
    assert "GROUP BY" not in sql


def test_compiles_group_by():
    sql = compile_sql(QuerySpec(metric="total_revenue", group_by=("region",)))
    assert "SELECT region, SUM(line_total)" in sql
    assert "GROUP BY region" in sql
    assert "ORDER BY region" in sql


def test_compiles_filter_with_escaped_quote():
    spec = QuerySpec(metric="total_revenue", filters=(Filter("region", "=", "o'brien"),))
    sql = compile_sql(spec)
    assert "region = 'o''brien'" in sql


def test_compiles_multiple_group_by_and_filters():
    spec = QuerySpec(
        metric="order_count",
        group_by=("region", "channel"),
        filters=(Filter("year", "=", "2026"), Filter("country", "=", "US")),
    )
    sql = compile_sql(spec)
    assert "GROUP BY region, channel" in sql
    assert "year = '2026'" in sql
    assert "country = 'US'" in sql
