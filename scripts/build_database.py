"""Rebuild data/retail.db from the Olist CSV files in data/raw/.

Usage (from the project root):
    python scripts/build_database.py
"""
import sys
from pathlib import Path

# Scripts are run directly, so Python does not know about src/ yet.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retailinsight import config, database  # noqa: E402


def main():
    missing = [path.name for path in config.RAW_FILES.values() if not path.exists()]
    if missing:
        sys.exit(f"Missing CSV files in {config.RAW_DATA_DIR}: {', '.join(missing)}")

    sales_items = database.build_database()
    delivered = sales_items.loc[sales_items["order_status"] == "delivered", "price"].sum()
    print(f"Database written to {config.DB_PATH}")
    print(f"sales_items rows: {len(sales_items):,}")
    print(f"Completed sales revenue (delivered, excl. freight): R$ {delivered:,.2f}")


if __name__ == "__main__":
    main()
