import pytest

import analytics
import database


def test_schema_contains_core_tables():
    schema = database.get_schema_prompt()
    for name in (
        "orders",
        "order_items",
        "products",
        "customers",
        "employees",
        "departments",
        "v_sales_line",
        "v_order_summary",
    ):
        assert name in schema


def test_business_tables_seeded():
    counts = database.table_counts()
    assert counts["orders"] > 100
    assert counts["order_items"] > counts["orders"]
    assert counts["customers"] >= 50
    assert counts["products"] >= 40


def test_overview_is_consistent():
    overview = analytics.overview()
    assert overview["revenue"] > 0
    assert overview["orders"] > 0
    assert overview["total_orders"] >= overview["orders"]
    assert overview["aov"] == pytest.approx(
        overview["revenue"] / overview["orders"], rel=1e-4
    )


def test_category_shares_sum_to_100():
    categories = analytics.category_sales()
    assert categories
    total_share = sum(item["share"] for item in categories)
    assert total_share == pytest.approx(100.0, abs=0.2)


def test_orders_page_pagination():
    page = analytics.orders_page(page=1, size=5)
    assert len(page["items"]) == 5
    assert page["total"] > 5
    assert page["pages"] >= 2


def test_execute_readonly_select():
    columns, rows, error, truncated = database.execute_readonly(
        "SELECT COUNT(*) AS total FROM orders"
    )
    assert error is None
    assert columns == ["total"]
    assert rows[0][0] > 0
    assert truncated is False


def test_authorizer_blocks_write():
    columns, rows, error, truncated = database.execute_readonly(
        "DELETE FROM orders"
    )
    assert columns is None
    assert error is not None
    assert truncated is False
