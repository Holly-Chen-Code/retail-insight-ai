"""SQLite layer: save the cleaned sales items and run read-only SQL queries on them."""
import sqlite3
from contextlib import closing

import pandas as pd

from retailinsight import config, data_loader

SALES_ITEMS_TABLE = "sales_items"


def save_sales_items(sales_items, db_path=None):
    """Write the sales items DataFrame to SQLite, replacing any previous table."""
    db_path = db_path or config.DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        sales_items.to_sql(SALES_ITEMS_TABLE, conn, if_exists="replace", index=False)


def run_query(sql, params=None, db_path=None):
    """Run one SELECT query and return the result as a DataFrame.

    The database is opened in read-only mode, so INSERT / UPDATE / DELETE / DROP
    fail with sqlite3.OperationalError. Pass values via `params` (using ? placeholders)
    instead of building the SQL string by hand.
    """
    db_path = db_path or config.DB_PATH
    with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def verify_sales_items(sales_items, db_path=None):
    """Raise ValueError if the table does not match the DataFrame it was saved from."""
    row_count = run_query(f"SELECT COUNT(*) AS n FROM {SALES_ITEMS_TABLE}", db_path=db_path)["n"][0]
    if row_count != len(sales_items):
        raise ValueError(f"database has {row_count} rows, expected {len(sales_items)}")

    revenue_sql = (
        f"SELECT SUM(price) AS revenue FROM {SALES_ITEMS_TABLE} WHERE order_status = ?"
    )
    db_revenue = run_query(revenue_sql, params=("delivered",), db_path=db_path)["revenue"][0]
    expected = sales_items.loc[sales_items["order_status"] == "delivered", "price"].sum()
    if abs(db_revenue - expected) > 0.01:
        raise ValueError(f"database delivered revenue {db_revenue}, expected {expected}")


def build_database(db_path=None):
    """Load and clean the CSVs, save them to SQLite and verify the result."""
    sales_items = data_loader.load_all()["sales_items"]
    save_sales_items(sales_items, db_path)
    verify_sales_items(sales_items, db_path)
    return sales_items
