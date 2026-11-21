"""Real PostgreSQL connection and sales_fact loading.

PostgreSQL is not installed as a service on the Windows side of this
machine; it runs inside WSL2 (`sudo service postgresql start`) and is
reached from Windows over the WSL2 localhost-forwarding loopback on
127.0.0.1:5432. Connection parameters are read from environment variables so
CI or another machine can point this at a different instance; `connect()`
raises `psycopg2.OperationalError` if nothing is listening, and every test
and script here catches that and skips cleanly rather than failing the
build when Postgres is not running.
"""
import os

import psycopg2

from .data_gen import COLUMNS, generate_rows

DEFAULT_DSN = dict(
    host=os.environ.get("ANALYTICS_PGHOST", "127.0.0.1"),
    port=int(os.environ.get("ANALYTICS_PGPORT", "5432")),
    user=os.environ.get("ANALYTICS_PGUSER", "postgres"),
    password=os.environ.get("ANALYTICS_PGPASSWORD", "analytics_dev"),
    dbname=os.environ.get("ANALYTICS_PGDATABASE", "analytics_agent_db"),
    connect_timeout=3,
)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sales_fact (
    line_item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    product_id TEXT NOT NULL,
    region TEXT NOT NULL,
    country TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    channel TEXT NOT NULL,
    customer_segment TEXT NOT NULL,
    sales_rep TEXT NOT NULL,
    store_id TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    order_status TEXT NOT NULL,
    shipping_method TEXT NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day_of_week TEXT NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC NOT NULL,
    line_total NUMERIC NOT NULL,
    cost NUMERIC NOT NULL,
    discount NUMERIC NOT NULL
);
"""


def connect():
    return psycopg2.connect(**DEFAULT_DSN)


def load_sales_fact(con, n_line_items=None, seed=None):
    cur = con.cursor()
    cur.execute(CREATE_TABLE_SQL)
    cur.execute("TRUNCATE sales_fact")
    kwargs = {}
    if n_line_items is not None:
        kwargs["n_line_items"] = n_line_items
    if seed is not None:
        kwargs["seed"] = seed
    rows = generate_rows(**kwargs)
    placeholders = ", ".join(["%s"] * len(COLUMNS))
    insert_sql = f"INSERT INTO sales_fact ({', '.join(COLUMNS)}) VALUES ({placeholders})"
    cur.executemany(insert_sql, [tuple(row[c] for c in COLUMNS) for row in rows])
    con.commit()
    return len(rows)


def is_reachable() -> bool:
    try:
        con = connect()
        con.close()
        return True
    except psycopg2.OperationalError:
        return False
