"""Predefined analytics functions ("tools") that the AI agent can call.

Every function:
- uses delivered orders only and sums `price` (freight is excluded);
- has simple arguments and a docstring, because the docstring and type hints are what
  the LLM reads to decide which function to call;
- returns plain Python values (float / list of dicts) so the result can be sent back to the LLM as JSON.
"""
from retailinsight import database

DELIVERED = "delivered"
MAX_TOP_N = 50


def total_revenue() -> float:
    """Total completed sales revenue in R$ (sum of item price for delivered orders, freight excluded)."""
    result = database.run_query(
        "SELECT SUM(price) AS revenue FROM sales_items WHERE order_status = ?",
        params=(DELIVERED,),
    )
    return round(float(result["revenue"][0] or 0), 2)


def average_order_value() -> float:
    """Average order value in R$: completed sales revenue divided by the number of delivered orders (freight excluded)."""
    result = database.run_query(
        "SELECT SUM(price) * 1.0 / COUNT(DISTINCT order_id) AS aov "
        "FROM sales_items WHERE order_status = ?",
        params=(DELIVERED,),
    )
    return round(float(result["aov"][0] or 0), 2)


def top_categories(n: int = 5) -> list[dict]:
    """Top n product categories by completed sales revenue in R$ (delivered orders, freight excluded).

    Args:
        n: How many categories to return, between 1 and 50. Defaults to 5.
    """
    n = int(n)
    if not 1 <= n <= MAX_TOP_N:
        raise ValueError(f"n must be between 1 and {MAX_TOP_N}, got {n}")

    result = database.run_query(
        "SELECT category, ROUND(SUM(price), 2) AS revenue "
        "FROM sales_items WHERE order_status = ? "
        "GROUP BY category ORDER BY revenue DESC LIMIT ?",
        params=(DELIVERED, n),
    )
    return result.to_dict("records")


def monthly_revenue() -> list[dict]:
    """Completed sales revenue in R$ per month, oldest first (delivered orders, freight excluded).

    Each row has `month` (YYYY-MM, based on the order purchase date) and `revenue`.
    """
    result = database.run_query(
        "SELECT strftime('%Y-%m', order_purchase_timestamp) AS month, "
        "ROUND(SUM(price), 2) AS revenue "
        "FROM sales_items WHERE order_status = ? "
        "GROUP BY month ORDER BY month",
        params=(DELIVERED,),
    )
    return result.to_dict("records")


# The list the agent will hand to the LLM so it can choose which function to call.
ANALYTICS_TOOLS = [total_revenue, average_order_value, top_categories, monthly_revenue]
