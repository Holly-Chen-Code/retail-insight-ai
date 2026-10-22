import json

import pandas as pd
import pytest

from retailinsight import analytics, config, database


# ---------- unit tests: tiny database where the right answers are easy to compute by hand ----------

@pytest.fixture
def small_db(tmp_path, monkeypatch):
    sales_items = pd.DataFrame(
        {
            "order_id": ["o1", "o1", "o2", "o3", "o4"],
            "order_status": ["delivered", "delivered", "delivered", "canceled", "shipped"],
            "category": ["toys", "auto", "toys", "toys", "auto"],
            "price": [10.0, 20.0, 30.0, 1000.0, 2000.0],
            "freight_value": [5.0, 5.0, 5.0, 5.0, 5.0],
            "order_purchase_timestamp": [
                "2018-01-05 10:00:00",
                "2018-01-05 10:00:00",
                "2018-02-10 09:30:00",
                "2018-02-11 12:00:00",
                "2018-03-01 08:00:00",
            ],
        }
    )
    path = tmp_path / "small.db"
    database.save_sales_items(sales_items, path)
    monkeypatch.setattr(config, "DB_PATH", path)


def test_total_revenue_only_delivered_and_excludes_freight(small_db):
    assert analytics.total_revenue() == 60.0  # 10 + 20 + 30, not canceled/shipped, no freight


def test_average_order_value_divides_by_orders_not_items(small_db):
    assert analytics.average_order_value() == 30.0  # 60 / 2 delivered orders (o1, o2)


def test_top_categories_sorted_and_limited(small_db):
    assert analytics.top_categories(1) == [{"category": "toys", "revenue": 40.0}]
    assert analytics.top_categories(5) == [
        {"category": "toys", "revenue": 40.0},
        {"category": "auto", "revenue": 20.0},
    ]


@pytest.mark.parametrize("bad_n", [0, -1, 51])
def test_top_categories_rejects_invalid_n(small_db, bad_n):
    with pytest.raises(ValueError):
        analytics.top_categories(bad_n)


def test_top_categories_accepts_float_n_from_llm(small_db):
    assert len(analytics.top_categories(1.0)) == 1


def test_monthly_revenue_groups_delivered_orders_by_purchase_month(small_db):
    assert analytics.monthly_revenue() == [
        {"month": "2018-01", "revenue": 30.0},
        {"month": "2018-02", "revenue": 30.0},
    ]


def test_tools_are_documented_and_return_json_serializable_values(small_db):
    for tool in analytics.ANALYTICS_TOOLS:
        assert tool.__doc__, f"{tool.__name__} needs a docstring for the LLM"
        json.dumps(tool())  # raises TypeError if the result is not plain JSON data


# ---------- integration tests: results must match the EDA findings ----------

needs_data = pytest.mark.skipif(
    not all(path.exists() for path in config.RAW_FILES.values()),
    reason="Olist CSV files not found in data/raw/",
)


@pytest.fixture(scope="module")
def real_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "retail.db"
    database.build_database(path)
    return path


@pytest.fixture
def use_real_db(real_db, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", real_db)


@needs_data
def test_total_revenue_matches_eda(use_real_db):
    assert analytics.total_revenue() == pytest.approx(13221498.11, abs=0.01)


@needs_data
def test_average_order_value_matches_eda(use_real_db):
    assert analytics.average_order_value() == pytest.approx(137.04, abs=0.01)


@needs_data
def test_top_categories_match_eda(use_real_db):
    top = analytics.top_categories()
    assert [row["category"] for row in top] == [
        "health_beauty",
        "watches_gifts",
        "bed_bath_table",
        "sports_leisure",
        "computers_accessories",
    ]
    assert top[0]["revenue"] == pytest.approx(1233131.72, abs=0.01)


@needs_data
def test_monthly_revenue_adds_up_to_total_revenue(use_real_db):
    months = analytics.monthly_revenue()
    assert [row["month"] for row in months] == sorted(row["month"] for row in months)
    assert sum(row["revenue"] for row in months) == pytest.approx(analytics.total_revenue(), abs=0.1)
