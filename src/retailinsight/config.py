"""Central place for file paths and settings, so no other file hardcodes them."""
from pathlib import Path

# config.py lives at <project>/src/retailinsight/config.py, so the project root is 2 levels up.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "retail.db"

# The four Olist CSV files used in Milestone 1.
RAW_FILES = {
    "orders": RAW_DATA_DIR / "olist_orders_dataset.csv",
    "order_items": RAW_DATA_DIR / "olist_order_items_dataset.csv",
    "products": RAW_DATA_DIR / "olist_products_dataset.csv",
    "category_translation": RAW_DATA_DIR / "product_category_name_translation.csv",
}
