"""The governed semantic model: every metric and dimension this agent is allowed
to reference. Nothing outside this module's DIMENSIONS and METRICS dicts can
ever appear in a generated query; sql_compiler.py and parser.py both import
from here rather than hardcoding column names, so the whitelist is the only
place a new field could be added.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Dimension:
    name: str
    column: str
    synonyms: tuple


@dataclass(frozen=True)
class Metric:
    name: str
    sql_expression: str
    synonyms: tuple


DIMENSIONS = [
    Dimension("region", "region", ("region", "regions")),
    Dimension("country", "country", ("country", "countries")),
    Dimension("category", "category", ("category", "categories", "product category")),
    Dimension("subcategory", "subcategory", ("subcategory", "sub-category", "subcategories")),
    Dimension("channel", "channel", ("channel", "sales channel")),
    Dimension("customer_segment", "customer_segment", ("customer segment", "segment")),
    Dimension("sales_rep", "sales_rep", ("sales rep", "sales representative", "rep")),
    Dimension("store_id", "store_id", ("store", "store id")),
    Dimension("payment_method", "payment_method", ("payment method", "payment type")),
    Dimension("order_status", "order_status", ("order status", "status")),
    Dimension("shipping_method", "shipping_method", ("shipping method", "shipping")),
    Dimension("product_id", "product_id", ("product", "product id")),
    Dimension("customer_id", "customer_id", ("customer", "customer id")),
    Dimension("year", "year", ("year",)),
    Dimension("quarter", "quarter", ("quarter",)),
    Dimension("month", "month", ("month",)),
    Dimension("day_of_week", "day_of_week", ("day of week", "weekday")),
    Dimension("is_weekend", "is_weekend", ("weekend",)),
]

METRICS = [
    Metric("total_revenue", "SUM(line_total)", ("total revenue", "revenue", "sales")),
    Metric("total_quantity", "SUM(quantity)", ("total quantity", "units sold", "quantity")),
    Metric("order_count", "COUNT(DISTINCT order_id)", ("order count", "number of orders", "orders")),
    Metric("unique_customers", "COUNT(DISTINCT customer_id)", ("unique customers", "distinct customers")),
    Metric("average_order_value", "SUM(line_total) / NULLIF(COUNT(DISTINCT order_id), 0)", ("average order value", "aov")),
    Metric("gross_margin", "SUM(line_total - cost)", ("gross margin", "margin")),
    Metric("discount_amount", "SUM(discount)", ("discount amount", "total discount", "discounts")),
    Metric("return_count", "COUNT(*) FILTER (WHERE order_status = 'returned')", ("return count", "number of returns", "returns")),
    Metric("return_rate", "COUNT(*) FILTER (WHERE order_status = 'returned')::float / NULLIF(COUNT(*), 0)", ("return rate",)),
    Metric("avg_unit_price", "AVG(unit_price)", ("average unit price", "avg unit price")),
    Metric("avg_quantity_per_order", "SUM(quantity)::float / NULLIF(COUNT(DISTINCT order_id), 0)", ("average quantity per order", "avg quantity per order")),
    Metric("total_cost", "SUM(cost)", ("total cost", "cost")),
    Metric("total_profit", "SUM(line_total - cost)", ("total profit", "profit")),
    Metric("profit_margin_pct", "100.0 * SUM(line_total - cost) / NULLIF(SUM(line_total), 0)", ("profit margin", "profit margin percent")),
    Metric("max_order_value", "MAX(line_total)", ("maximum order value", "max order value", "largest order")),
    Metric("min_order_value", "MIN(line_total)", ("minimum order value", "min order value", "smallest order")),
    Metric("revenue_per_customer", "SUM(line_total) / NULLIF(COUNT(DISTINCT customer_id), 0)", ("revenue per customer",)),
    Metric("items_per_order", "SUM(quantity)::float / NULLIF(COUNT(DISTINCT order_id), 0)", ("items per order",)),
    Metric("avg_discount_pct", "100.0 * AVG(discount / NULLIF(line_total, 0))", ("average discount percent", "avg discount pct")),
    Metric("distinct_products_sold", "COUNT(DISTINCT product_id)", ("distinct products sold", "number of products sold")),
]

DIMENSION_NAMES = {d.name for d in DIMENSIONS}
METRIC_NAMES = {m.name for m in METRICS}
DIMENSION_BY_NAME = {d.name: d for d in DIMENSIONS}
METRIC_BY_NAME = {m.name: m for m in METRICS}


def field_count() -> int:
    return len(DIMENSIONS) + len(METRICS)
