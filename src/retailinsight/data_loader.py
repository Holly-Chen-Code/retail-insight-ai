"""Load and lightly clean the four Olist CSV files.

Cleaning rules (decided during EDA, see notebooks/olist_eda.ipynb):
- Order date columns are converted from text to datetime.
- All products are kept; products without a category get the category "unknown".
- Missing English category names are filled from MISSING_TRANSLATIONS.
- Every join is a left join with validate="many_to_one", and row counts and
  revenue totals are checked after joining so nothing is silently dropped or duplicated.
"""
import pandas as pd

from retailinsight import config

ORDER_DATE_COLUMNS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]

UNKNOWN_CATEGORY = "unknown"

# Categories that exist in products but are missing from product_category_name_translation.csv.
MISSING_TRANSLATIONS = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_food_preparers",
}


def load_orders(path=None):
    """Read orders.csv and convert the date columns to datetime."""
    orders = pd.read_csv(path or config.RAW_FILES["orders"])
    for column in ORDER_DATE_COLUMNS:
        orders[column] = pd.to_datetime(orders[column])
    return orders


def load_order_items(path=None):
    """Read order_items.csv and convert shipping_limit_date to datetime."""
    items = pd.read_csv(path or config.RAW_FILES["order_items"])
    items["shipping_limit_date"] = pd.to_datetime(items["shipping_limit_date"])
    return items


def load_products(path=None):
    """Read products.csv as is. Products with a missing category are kept."""
    return pd.read_csv(path or config.RAW_FILES["products"])


def load_category_translation(path=None):
    """Read the Portuguese -> English category name table."""
    return pd.read_csv(path or config.RAW_FILES["category_translation"])


def check_rows_and_revenue_unchanged(before, after, label):
    """Raise ValueError if a join changed the number of rows or the total price."""
    if len(after) != len(before):
        raise ValueError(f"{label}: row count changed from {len(before)} to {len(after)}")
    if abs(before["price"].sum() - after["price"].sum()) > 0.01:
        raise ValueError(
            f"{label}: total price changed from {before['price'].sum()} to {after['price'].sum()}"
        )


def add_english_category(products, translation):
    """Add a clean `category` column (English name) to every product.

    Lookup order: translation CSV -> MISSING_TRANSLATIONS dict -> "unknown".
    """
    merged = products.merge(
        translation, on="product_category_name", how="left", validate="many_to_one"
    )
    if len(merged) != len(products):
        raise ValueError(f"products: row count changed from {len(products)} to {len(merged)}")

    manual = merged["product_category_name"].map(MISSING_TRANSLATIONS)
    merged["category"] = (
        merged["product_category_name_english"].fillna(manual).fillna(UNKNOWN_CATEGORY)
    )
    return merged


def build_sales_items(orders, items, products):
    """One row per order item, with order status/date and product category attached.

    `products` must already have the `category` column (see add_english_category).
    """
    sales = items.merge(
        orders[["order_id", "order_status", "order_purchase_timestamp"]],
        on="order_id",
        how="left",
        validate="many_to_one",
    )
    check_rows_and_revenue_unchanged(items, sales, "items + orders")

    with_category = sales.merge(
        products[["product_id", "category"]],
        on="product_id",
        how="left",
        validate="many_to_one",
    )
    check_rows_and_revenue_unchanged(sales, with_category, "items + products")
    return with_category


def load_all():
    """Load and clean everything. Returns a dict of DataFrames."""
    orders = load_orders()
    items = load_order_items()
    products = add_english_category(load_products(), load_category_translation())
    return {
        "orders": orders,
        "order_items": items,
        "products": products,
        "sales_items": build_sales_items(orders, items, products),
    }
