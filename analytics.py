"""业务分析查询。

所有聚合查询集中在这里，供仪表盘、数据分析页和设置页复用。
统一销售口径：``status IN ('已完成','已发货')``。
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from database import query

VALID_SALES = "status IN ('已完成','已发货')"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _date_clause(start: str | None, end: str | None) -> tuple[str, list[Any]]:
    """生成安全的日期过滤条件。"""
    clauses: list[str] = []
    params: list[Any] = []

    if start and DATE_RE.match(start):
        clauses.append("order_date >= ?")
        params.append(start)
    if end and DATE_RE.match(end):
        clauses.append("order_date <= ?")
        params.append(end)

    if not clauses:
        return "", params
    return " AND " + " AND ".join(clauses), params


def _safe_query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    try:
        return query(sql, params)
    except Exception:
        return []


def overview(start: str | None = None, end: str | None = None) -> dict[str, Any]:
    clause, params = _date_clause(start, end)

    row = _safe_query(
        f"""
        SELECT
            COALESCE(SUM(amount), 0)            AS revenue,
            COUNT(DISTINCT order_id)            AS orders,
            COUNT(DISTINCT customer_id)         AS customers,
            COALESCE(SUM(quantity), 0)          AS units,
            COALESCE(SUM(amount - unit_cost * quantity), 0) AS gross_profit
        FROM v_sales_line
        WHERE {VALID_SALES}{clause}
        """,
        tuple(params),
    )

    data = row[0] if row else {}
    revenue = round(float(data.get("revenue") or 0), 2)
    orders = int(data.get("orders") or 0)
    customers = int(data.get("customers") or 0)
    units = int(data.get("units") or 0)
    gross_profit = round(float(data.get("gross_profit") or 0), 2)

    total_order_row = _safe_query(
        f"SELECT COUNT(*) AS c FROM orders WHERE 1=1{clause}",
        tuple(params),
    )
    total_orders = int(total_order_row[0]["c"]) if total_order_row else orders

    return {
        "revenue": revenue,
        "orders": orders,
        "customers": customers,
        "units": units,
        "gross_profit": gross_profit,
        "gross_margin": round(gross_profit / revenue * 100, 2) if revenue else 0.0,
        "aov": round(revenue / orders, 2) if orders else 0.0,
        "total_orders": total_orders,
        "valid_order_ratio": round(orders / total_orders * 100, 2) if total_orders else 0.0,
    }


def sales_trend(
    months: int = 10,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    clause, params = _date_clause(start, end)
    rows = _safe_query(
        f"""
        SELECT
            order_month,
            ROUND(SUM(amount), 2)       AS revenue,
            COUNT(DISTINCT order_id)    AS orders,
            COUNT(DISTINCT customer_id) AS customers,
            SUM(quantity)               AS units
        FROM v_sales_line
        WHERE {VALID_SALES}{clause}
        GROUP BY order_month
        ORDER BY order_month
        """,
        tuple(params),
    )

    if start or end:
        return rows

    # 用现有数据补齐月份，避免图表出现断点
    all_months = _safe_query(
        """
        SELECT DISTINCT order_month FROM v_sales_line
        ORDER BY order_month
        """
    )
    month_keys = [item["order_month"] for item in all_months][-max(months, 1):]
    by_month = {row["order_month"]: row for row in rows}

    result = []
    for month in month_keys:
        row = by_month.get(month)
        result.append(
            row
            or {
                "order_month": month,
                "revenue": 0,
                "orders": 0,
                "customers": 0,
                "units": 0,
            }
        )
    return result


def category_sales(
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    clause, params = _date_clause(start, end)
    rows = _safe_query(
        f"""
        SELECT
            category,
            ROUND(SUM(amount), 2)        AS revenue,
            SUM(quantity)                AS units,
            COUNT(DISTINCT order_id)     AS orders
        FROM v_sales_line
        WHERE {VALID_SALES}{clause}
        GROUP BY category
        ORDER BY revenue DESC
        """,
        tuple(params),
    )
    total = sum(float(row["revenue"] or 0) for row in rows) or 1.0
    for row in rows:
        row["share"] = round(float(row["revenue"] or 0) / total * 100, 2)
    return rows


def top_products(
    limit: int = 10,
    metric: str = "revenue",
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    clause, params = _date_clause(start, end)
    order_by = "units DESC" if metric == "units" else "revenue DESC"
    limit = max(1, min(int(limit or 10), 50))

    rows = _safe_query(
        f"""
        SELECT
            product_name,
            category,
            brand,
            ROUND(SUM(amount), 2)    AS revenue,
            SUM(quantity)            AS units,
            COUNT(DISTINCT order_id) AS orders
        FROM v_sales_line
        WHERE {VALID_SALES}{clause}
        GROUP BY product_id, product_name, category, brand
        ORDER BY {order_by}
        LIMIT ?
        """,
        tuple(params + [limit]),
    )
    return rows


def city_sales(
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    clause, params = _date_clause(start, end)
    rows = _safe_query(
        f"""
        SELECT
            customer_city                 AS city,
            ROUND(SUM(amount), 2)         AS revenue,
            COUNT(DISTINCT order_id)      AS orders,
            COUNT(DISTINCT customer_id)   AS customers,
            SUM(quantity)                 AS units
        FROM v_sales_line
        WHERE {VALID_SALES}{clause}
        GROUP BY customer_city
        ORDER BY revenue DESC
        """,
        tuple(params),
    )
    total = sum(float(row["revenue"] or 0) for row in rows) or 1.0
    for row in rows:
        row["share"] = round(float(row["revenue"] or 0) / total * 100, 2)
    return rows


def department_sales(
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    clause, params = _date_clause(start, end)
    rows = _safe_query(
        f"""
        SELECT
            department,
            ROUND(SUM(amount), 2)                AS revenue,
            COUNT(DISTINCT order_id)             AS orders,
            COUNT(DISTINCT employee_id)          AS sales_reps,
            COUNT(DISTINCT customer_id)          AS customers,
            SUM(quantity)                        AS units
        FROM v_sales_line
        WHERE {VALID_SALES} AND department IS NOT NULL{clause}
        GROUP BY department
        ORDER BY revenue DESC
        """,
        tuple(params),
    )
    total = sum(float(row["revenue"] or 0) for row in rows) or 1.0
    for row in rows:
        row["share"] = round(float(row["revenue"] or 0) / total * 100, 2)
    return rows


def order_status() -> list[dict[str, Any]]:
    rows = _safe_query(
        """
        SELECT
            status,
            COUNT(*)                     AS orders,
            ROUND(SUM(total_amount), 2)  AS amount
        FROM orders
        GROUP BY status
        ORDER BY orders DESC
        """
    )
    total = sum(int(row["orders"] or 0) for row in rows) or 1
    for row in rows:
        row["share"] = round(int(row["orders"] or 0) / total * 100, 2)
    return rows


def channel_sales() -> list[dict[str, Any]]:
    return _safe_query(
        f"""
        SELECT
            channel,
            ROUND(SUM(amount), 2)    AS revenue,
            COUNT(DISTINCT order_id) AS orders
        FROM v_sales_line
        WHERE {VALID_SALES}
        GROUP BY channel
        ORDER BY revenue DESC
        """
    )


def company_profile() -> list[dict[str, Any]]:
    """京东集团公开年度业绩（单位：亿元）。"""
    return _safe_query(
        """
        SELECT company, fiscal_year, revenue, revenue_yoy,
               net_profit, net_profit_yoy, logistics_revenue,
               logistics_yoy, new_business_revenue, source, updated_at
        FROM company_profile
        ORDER BY fiscal_year DESC
        """
    )


def recent_orders(limit: int = 8) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 8), 50))
    return _safe_query(
        """
        SELECT
            order_id,
            order_no,
            order_date,
            status,
            channel,
            customer_name,
            customer_city,
            sales_rep,
            department,
            total_amount,
            total_quantity
        FROM v_order_summary
        ORDER BY order_date DESC, order_id DESC
        LIMIT ?
        """,
        (limit,),
    )


def month_over_month() -> dict[str, Any]:
    """计算最近两个完整月份的环比，用于仪表盘提示。"""
    rows = sales_trend(months=12)
    if len(rows) < 2:
        return {"current": None, "previous": None, "growth": 0.0}

    current, previous = rows[-1], rows[-2]
    current_revenue = float(current.get("revenue") or 0)
    previous_revenue = float(previous.get("revenue") or 0)
    growth = (
        round((current_revenue - previous_revenue) / previous_revenue * 100, 2)
        if previous_revenue
        else 0.0
    )
    return {
        "current": current,
        "previous": previous,
        "growth": growth,
    }


def dashboard() -> dict[str, Any]:
    return {
        "kpis": overview(),
        "sales_trend": sales_trend(months=10),
        "categories": category_sales(),
        "top_products": top_products(limit=8),
        "cities": city_sales(),
        "departments": department_sales(),
        "order_status": order_status(),
        "channels": channel_sales(),
        "recent_orders": recent_orders(limit=6),
        "month_over_month": month_over_month(),
        "company_profile": company_profile(),
    }


def orders_page(
    page: int = 1,
    size: int = 20,
    status: str | None = None,
    keyword: str | None = None,
    city: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """订单明细分页，供数据分析页的订单表格使用。"""
    clauses: list[str] = []
    params: list[Any] = []

    if status and status in ("已完成", "已发货", "待付款", "已取消", "退款中"):
        clauses.append("status = ?")
        params.append(status)
    if keyword:
        like = f"%{keyword.strip()}%"
        clauses.append("(order_no LIKE ? OR customer_name LIKE ? OR sales_rep LIKE ?)")
        params.extend([like, like, like])
    if city:
        clauses.append("customer_city = ?")
        params.append(city)

    date_clause, date_params = _date_clause(start, end)
    if date_clause:
        clauses.append(date_clause[len(" AND "):])
        params.extend(date_params)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    page = max(1, int(page or 1))
    size = max(1, min(int(size or 20), 100))
    offset = (page - 1) * size

    total_rows = _safe_query(
        f"SELECT COUNT(*) AS total FROM v_order_summary {where}",
        tuple(params),
    )
    total = int(total_rows[0]["total"]) if total_rows else 0

    items = _safe_query(
        f"""
        SELECT order_id, order_no, order_date, status, channel,
               customer_name, customer_city, sales_rep, department,
               total_amount, total_quantity, item_count
        FROM v_order_summary
        {where}
        ORDER BY order_date DESC, order_id DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [size, offset]),
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size,
    }


def products_list(limit: int = 60) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 60), 200))
    return _safe_query(
        """
        SELECT id, name, category, brand, unit_price, cost, stock, status
        FROM products
        ORDER BY category, id
        LIMIT ?
        """,
        (limit,),
    )


def filter_options() -> dict[str, Any]:
    categories = [
        row["category"]
        for row in _safe_query(
            "SELECT DISTINCT category FROM products ORDER BY category"
        )
    ]
    cities = [
        row["city"]
        for row in _safe_query(
            "SELECT DISTINCT city FROM customers ORDER BY city"
        )
    ]
    return {
        "categories": categories,
        "cities": cities,
        "statuses": ["已完成", "已发货", "待付款", "已取消", "退款中"],
        "channels": ["京东APP", "京东小程序", "京东PC", "京东到家", "企业采购"],
        "today": date.today().isoformat(),
    }
