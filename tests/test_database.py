import pandas as pd
import pytest

from retailinsight import config, database


@pytest.fixture
def sales_items():
    return pd.DataFrame(
        {
            "order_id": ["o1", "o1", "o2", "o3"],
            "order_status": ["delivered", "delivered", "canceled", "delivered"],
            "category": ["toys", "toys", "auto", "unknown"],
            "price": [10.0, 20.0, 99.0, 5.5],
        }
    )


@pytest.fixture
def db_path(tmp_path, sales_items):
    path = tmp_path / "test.db"
    database.save_sales_items(sales_items, path)
    return path


# ---------- unit tests: small DataFrame, temporary database file ----------

def test_save_and_query_round_trip(db_path, sales_items):
    result = database.run_query("SELECT * FROM sales_items", db_path=db_path)
    assert len(result) == len(sales_items)
    assert list(result.columns) == list(sales_items.columns)


def test_run_query_group_by(db_path):
    result = database.run_query(
        "SELECT category, SUM(price) AS revenue FROM sales_items "
        "WHERE order_status = 'delivered' GROUP BY category ORDER BY revenue DESC",
        db_path=db_path,
    )
    assert result["category"].tolist() == ["toys", "unknown"]
    assert result["revenue"].tolist() == [30.0, 5.5]


def test_run_query_uses_parameters(db_path):
    result = database.run_query(
        "SELECT COUNT(*) AS n FROM sales_items WHERE order_status = ?",
        params=("canceled",),
        db_path=db_path,
    )
    assert result["n"][0] == 1


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM sales_items",
        "DROP TABLE sales_items",
        "UPDATE sales_items SET price = 0",
        "INSERT INTO sales_items (order_id) VALUES ('x')",
    ],
)
def test_run_query_is_read_only(db_path, sql):
    # pandas wraps the sqlite3 error in its own DatabaseError
    with pytest.raises(pd.errors.DatabaseError, match="readonly"):
        database.run_query(sql, db_path=db_path)
    assert len(database.run_query("SELECT * FROM sales_items", db_path=db_path)) == 4


def test_save_sales_items_replaces_existing_table(db_path, sales_items):
    database.save_sales_items(sales_items.head(2), db_path)
    assert len(database.run_query("SELECT * FROM sales_items", db_path=db_path)) == 2


def test_verify_sales_items_passes_for_matching_data(db_path, sales_items):
    database.verify_sales_items(sales_items, db_path)


def test_verify_sales_items_detects_missing_rows(db_path, sales_items):
    with pytest.raises(ValueError, match="rows"):
        database.verify_sales_items(pd.concat([sales_items, sales_items]), db_path)


def test_verify_sales_items_detects_revenue_change(db_path, sales_items):
    changed = sales_items.copy()
    changed.loc[0, "price"] = 11.0
    with pytest.raises(ValueError, match="revenue"):
        database.verify_sales_items(changed, db_path)


# ---------- integration test: needs the real CSVs in data/raw/ ----------

needs_data = pytest.mark.skipif(
    not all(path.exists() for path in config.RAW_FILES.values()),
    reason="Olist CSV files not found in data/raw/",
)


@needs_data
def test_build_database_matches_known_totals(tmp_path):
    path = tmp_path / "retail.db"
    database.build_database(path)

    rows = database.run_query("SELECT COUNT(*) AS n FROM sales_items", db_path=path)
    assert rows["n"][0] == 112650

    revenue = database.run_query(
        "SELECT SUM(price) AS revenue FROM sales_items WHERE order_status = 'delivered'",
        db_path=path,
    )
    assert revenue["revenue"][0] == pytest.approx(13221498.11, abs=0.01)
