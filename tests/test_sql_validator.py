from sql_validator import ensure_limit, validate_sql


def test_allows_select():
    ok, error = validate_sql("SELECT * FROM orders LIMIT 10")
    assert ok is True
    assert error is None


def test_allows_cte():
    ok, _ = validate_sql(
        "WITH monthly AS (SELECT order_month FROM v_sales_line) "
        "SELECT * FROM monthly"
    )
    assert ok is True


def test_allows_trailing_semicolon():
    ok, _ = validate_sql("SELECT 1;")
    assert ok is True


def test_rejects_delete():
    ok, error = validate_sql("DELETE FROM orders")
    assert ok is False
    assert "DELETE" in error or "禁止" in error


def test_rejects_multiple_statements():
    ok, error = validate_sql("SELECT 1; DROP TABLE orders;")
    assert ok is False
    assert "多条" in error


def test_rejects_dangerous_keyword_in_comment():
    ok, error = validate_sql("SELECT * FROM orders -- DROP TABLE orders")
    assert ok is True, error


def test_ignores_keyword_inside_string_literal():
    ok, error = validate_sql("SELECT 'DROP TABLE' AS demo")
    assert ok is True, error


def test_allows_semicolon_inside_string_literal():
    ok, error = validate_sql("SELECT ';' AS demo")
    assert ok is True, error


def test_rejects_attach():
    ok, error = validate_sql("SELECT 1; ATTACH DATABASE 'x.db' AS x")
    assert ok is False
    assert "多条" in error or "ATTACH" in error


def test_ensure_limit_appends():
    assert ensure_limit("SELECT * FROM orders", 50).endswith("LIMIT 50")


def test_ensure_limit_keeps_existing():
    sql = "SELECT * FROM orders LIMIT 5"
    assert ensure_limit(sql, 50) == sql
