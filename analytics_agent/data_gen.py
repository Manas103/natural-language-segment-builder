"""Seeded, synthetic sales_fact rows. No real transaction data."""
import random

DEFAULT_SEED = 20260915
N_LINE_ITEMS = 20000
N_ORDERS = 6000
N_CUSTOMERS = 1500
N_PRODUCTS = 400
N_STORES = 40
N_REPS = 25

REGIONS = ["northeast", "southeast", "midwest", "southwest", "west"]
COUNTRIES = ["US", "CA", "MX"]
CATEGORIES = ["electronics", "apparel", "home", "sporting_goods", "toys"]
SUBCATEGORIES = {
    "electronics": ["audio", "laptops", "phones"],
    "apparel": ["mens", "womens", "kids"],
    "home": ["kitchen", "furniture", "decor"],
    "sporting_goods": ["fitness", "outdoor", "team_sports"],
    "toys": ["games", "educational", "outdoor_toys"],
}
CHANNELS = ["online", "retail", "marketplace"]
SEGMENTS = ["consumer", "small_business", "enterprise"]
PAYMENT_METHODS = ["credit_card", "debit_card", "paypal", "gift_card"]
ORDER_STATUSES = ["completed", "completed", "completed", "completed", "returned", "cancelled"]
SHIPPING_METHODS = ["standard", "expedited", "overnight"]
DAYS_OF_WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def generate_rows(seed=DEFAULT_SEED, n_line_items=N_LINE_ITEMS):
    rng = random.Random(seed)

    order_meta = {}
    for order_id in range(N_ORDERS):
        year = rng.choice([2024, 2025, 2026])
        month = rng.randrange(1, 13)
        quarter = (month - 1) // 3 + 1
        dow = rng.choice(DAYS_OF_WEEK)
        order_meta[order_id] = {
            "customer_id": rng.randrange(N_CUSTOMERS),
            "region": rng.choice(REGIONS),
            "country": rng.choice(COUNTRIES),
            "channel": rng.choice(CHANNELS),
            "customer_segment": rng.choice(SEGMENTS),
            "sales_rep": f"rep_{rng.randrange(N_REPS):03d}",
            "store_id": f"store_{rng.randrange(N_STORES):03d}",
            "payment_method": rng.choice(PAYMENT_METHODS),
            "order_status": rng.choice(ORDER_STATUSES),
            "shipping_method": rng.choice(SHIPPING_METHODS),
            "year": year,
            "quarter": quarter,
            "month": month,
            "day_of_week": dow,
            "is_weekend": dow in ("sat", "sun"),
        }

    rows = []
    for line_item_id in range(n_line_items):
        order_id = rng.randrange(N_ORDERS)
        meta = order_meta[order_id]
        category = rng.choice(CATEGORIES)
        subcategory = rng.choice(SUBCATEGORIES[category])
        quantity = rng.randrange(1, 6)
        unit_price = round(rng.uniform(5.0, 400.0), 2)
        cost = round(unit_price * rng.uniform(0.4, 0.7), 2)
        discount = round(unit_price * quantity * rng.uniform(0.0, 0.2), 2)
        line_total = round(unit_price * quantity - discount, 2)
        row = {
            "line_item_id": line_item_id,
            "order_id": order_id,
            "product_id": f"product_{rng.randrange(N_PRODUCTS):04d}",
            "category": category,
            "subcategory": subcategory,
            "quantity": quantity,
            "unit_price": unit_price,
            "cost": cost * quantity,
            "discount": discount,
            "line_total": line_total,
        }
        row.update(meta)
        rows.append(row)
    return rows


COLUMNS = [
    "line_item_id", "order_id", "customer_id", "product_id", "region", "country",
    "category", "subcategory", "channel", "customer_segment", "sales_rep", "store_id",
    "payment_method", "order_status", "shipping_method", "year", "quarter", "month",
    "day_of_week", "is_weekend", "quantity", "unit_price", "line_total", "cost", "discount",
]
