import pandas as pd
import pytest

from retailinsight import config, data_loader


# ---------- unit tests: tiny hand-made DataFrames, no CSV files needed ----------

@pytest.fixture
def translation():
    return pd.DataFrame(
        {"product_category_name": ["beleza_saude"], "product_category_name_english": ["health_beauty"]}
    )


@pytest.fixture
def products():
    return pd.DataFrame(
        {
            "product_id": ["p1", "p2", "p3", "p4"],
            "product_category_name": ["beleza_saude", "pc_gamer", None, "other_unlisted"],
        }
    )


def test_add_english_category_applies_translation_dictionary_and_unknown(products, translation):
    result = data_loader.add_english_category(products, translation)

    assert len(result) == len(products)  # no product dropped
    categories = dict(zip(result["product_id"], result["category"]))
    assert categories["p1"] == "health_beauty"  # from translation CSV
    assert categories["p2"] == "pc_gamer"  # from MISSING_TRANSLATIONS
    assert categories["p3"] == "unknown"  # missing category is kept as "unknown"
    assert categories["p4"] == "unknown"  # unlisted category has no English name


def test_add_english_category_rejects_duplicate_translation_keys(products):
    bad_translation = pd.DataFrame(
        {
            "product_category_name": ["beleza_saude", "beleza_saude"],
            "product_category_name_english": ["a", "b"],
        }
    )
    with pytest.raises(pd.errors.MergeError):
        data_loader.add_english_category(products, bad_translation)


def make_orders_items(order_ids):
    orders = pd.DataFrame(
        {
            "order_id": order_ids,
            "order_status": ["delivered"] * len(order_ids),
            "order_purchase_timestamp": pd.to_datetime(["2018-01-01"] * len(order_ids)),
        }
    )
    items = pd.DataFrame(
        {"order_id": ["o1", "o1", "o2"], "product_id": ["p1", "p2", "p1"], "price": [10.0, 20.0, 30.0]}
    )
    return orders, items


def test_build_sales_items_keeps_rows_and_revenue(products, translation):
    orders, items = make_orders_items(["o1", "o2"])
    products = data_loader.add_english_category(products, translation)

    sales = data_loader.build_sales_items(orders, items, products)

    assert len(sales) == len(items)
    assert sales["price"].sum() == items["price"].sum()
    assert {"order_status", "category"} <= set(sales.columns)


def test_build_sales_items_rejects_duplicate_order_ids(products, translation):
    orders, items = make_orders_items(["o1", "o2", "o2"])  # o2 appears twice
    products = data_loader.add_english_category(products, translation)

    with pytest.raises(pd.errors.MergeError):
        data_loader.build_sales_items(orders, items, products)


def test_check_rows_and_revenue_unchanged_detects_changes():
    before = pd.DataFrame({"price": [10.0, 20.0]})

    with pytest.raises(ValueError, match="row count"):
        data_loader.check_rows_and_revenue_unchanged(before, pd.DataFrame({"price": [10.0]}), "t")
    with pytest.raises(ValueError, match="total price"):
        data_loader.check_rows_and_revenue_unchanged(before, pd.DataFrame({"price": [10.0, 99.0]}), "t")


# ---------- integration tests: need the real CSVs in data/raw/ ----------

needs_data = pytest.mark.skipif(
    not all(path.exists() for path in config.RAW_FILES.values()),
    reason="Olist CSV files not found in data/raw/",
)


@needs_data
def test_load_orders_converts_dates():
    orders = data_loader.load_orders()
    assert pd.api.types.is_datetime64_any_dtype(orders["order_purchase_timestamp"])
    assert len(orders) == 99441


@needs_data
def test_load_all_matches_known_totals():
    data = data_loader.load_all()

    assert len(data["products"]) == 32951  # all products kept
    assert len(data["sales_items"]) == 112650  # same as order_items
    assert data["sales_items"]["category"].notna().all()
    assert (data["products"]["category"] == "unknown").sum() == 610

    delivered = data["sales_items"][data["sales_items"]["order_status"] == "delivered"]
    assert delivered["price"].sum() == pytest.approx(13221498.11, abs=0.01)
