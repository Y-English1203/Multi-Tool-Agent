"""SQLite 访问层。

统一负责：
* 业务库连接（默认只读，避免 Text-to-SQL 误写）；
* 读取真实 Schema 并生成给 LLM 的提示词；
* 安全的只读查询执行；
* 基础数据统计，供仪表盘和健康检查使用。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "business.db"

MAX_RESULT_ROWS = 200

# 供 LLM 参考的字段说明。只写业务语义，不写运行时数据。
COLUMN_NOTES = {
    "orders": {
        "id": "订单主键",
        "order_no": "订单号",
        "customer_id": "客户 ID，关联 customers.id",
        "employee_id": "负责该订单的销售员工 ID，关联 employees.id",
        "order_date": "下单日期，格式 YYYY-MM-DD",
        "status": "订单状态：已完成 / 已发货 / 待付款 / 已取消 / 退款中",
        "channel": "下单渠道：京东APP / 京东小程序 / 京东PC / 京东到家 / 企业采购",
        "total_amount": "订单总金额（元）",
        "created_at": "下单时间",
    },
    "order_items": {
        "order_id": "订单 ID，关联 orders.id",
        "product_id": "商品 ID，关联 products.id",
        "quantity": "购买数量",
        "unit_price": "成交单价（元）",
        "amount": "行金额 = quantity × unit_price",
    },
    "products": {
        "category": "商品品类，共 10 类",
        "unit_price": "商品参考售价（元）",
        "cost": "商品成本（元）",
        "stock": "库存数量",
    },
    "company_profile": {
        "company": "公司名称",
        "fiscal_year": "财年",
        "revenue": "全年营收（亿元）",
        "revenue_yoy": "营收同比增速（%）",
        "net_profit": "归母净利润（亿元）",
        "net_profit_yoy": "净利润同比增速（%）",
        "logistics_revenue": "京东物流全年营收（亿元）",
        "new_business_revenue": "新业务全年营收（亿元）",
        "source": "公开资料来源链接",
    },
    "customers": {
        "city": "客户所在城市",
        "level": "会员等级：普通会员 / 银牌会员 / 金牌会员 / 钻石会员",
        "join_date": "注册日期",
    },
    "employees": {
        "department_id": "所属事业部 ID，关联 departments.id",
        "position": "岗位",
        "hire_date": "入职日期",
    },
    "departments": {
        "name": "事业部名称",
        "manager": "事业部负责人",
    },
    "v_sales_line": {
        "one_row": "一行 = 一个订单中的一个商品明细",
        "amount": "行金额（元）",
        "order_month": "订单月份，格式 YYYY-MM",
        "department": "负责该订单的事业部",
        "sales_rep": "负责该订单的销售员工",
    },
    "v_order_summary": {
        "one_row": "一行 = 一个订单",
        "total_amount": "订单总金额（元）",
        "item_count": "订单中的商品明细行数",
        "total_quantity": "订单商品总件数",
    },
}

BUSINESS_RULES = """【业务口径】
1. 订单状态只有：已完成、已发货、待付款、已取消、退款中。
2. 有效销售默认指 status IN ('已完成','已发货')；统计销售额、销量、订单数时默认使用该口径，除非用户明确要求包含其他状态。
3. 销售额：对明细表用 SUM(amount)，对订单表用 SUM(total_amount)；不要把订单级 total_amount 与明细行 amount 混在同一层汇总。
4. 订单数：COUNT(DISTINCT order_id)；客户数：COUNT(DISTINCT customer_id)；销量：SUM(quantity)。
5. 客单价 = 有效销售额 / 有效订单数。
6. 时间字段是 TEXT：order_date 为 YYYY-MM-DD，order_month 为 YYYY-MM。
7. “本月”指 2026-10，“上个月”指 2026-09，“今年”指 2026 年。
8. 金额单位为人民币元，结果建议保留 2 位小数。
9. 明细查询返回前请加 ORDER BY + LIMIT，默认最多 200 行。
10. 不要查询 sqlite_master 等系统表。
11. company_profile 存放京东集团公开年度业绩，金额单位为亿元，与订单明细表的元不是同一粒度，禁止直接相加或比较。"""


def connect(readonly: bool = True) -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"业务数据库不存在：{DB_PATH}")

    if readonly:
        # URI 只读模式可以防止任何写操作
        conn = sqlite3.connect(
            f"file:{DB_PATH.as_posix()}?mode=ro",
            uri=True,
            timeout=15,
        )
        conn.execute("PRAGMA query_only = ON")
    else:
        conn = sqlite3.connect(DB_PATH, timeout=15)

    conn.row_factory = sqlite3.Row
    return conn


def query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect(readonly=True) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


def scalar(sql: str, params: tuple[Any, ...] = (), default: Any = None) -> Any:
    rows = query(sql, params)
    if not rows:
        return default
    value = next(iter(rows[0].values()))
    return default if value is None else value


def _column_notes(table: str, column: str) -> str:
    note = COLUMN_NOTES.get(table, {}).get(column, "")
    return f"  -- {note}" if note else ""


def get_schema_prompt(include_counts: bool = True) -> str:
    """读取数据库真实 Schema，生成 Text-to-SQL 提示词。"""
    with connect(readonly=True) as conn:
        objects = conn.execute(
            """
            SELECT name, type
            FROM sqlite_master
            WHERE type IN ('table', 'view')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name
            """
        ).fetchall()

        lines = [
            "数据库类型：SQLite",
            "数据库名称：business.db（京东商城业务演示库）",
            "当前日期：2026-10-19（Asia/Shanghai）",
            "",
        ]

        for row in objects:
            name, kind = row["name"], row["type"]
            cols = conn.execute(f'PRAGMA table_info("{name}")').fetchall()

            count = ""
            if include_counts:
                try:
                    total = conn.execute(
                        f'SELECT COUNT(*) FROM "{name}"'
                    ).fetchone()[0]
                    count = f"（约 {total} 行）"
                except sqlite3.Error:
                    count = ""

            label = "表" if kind == "table" else "视图"
            column_text = ",\n".join(
                f"    {col['name']} {col['type'] or 'TEXT'}"
                f"{_column_notes(name, col['name'])}"
                for col in cols
            )
            lines.append(f"{label} {name}{count}：")
            lines.append(column_text)
            lines.append("")

    lines.append(BUSINESS_RULES)
    return "\n".join(lines)


def table_counts() -> dict[str, int]:
    """返回各业务表/视图行数，用于设置页和健康检查。"""
    result: dict[str, int] = {}
    try:
        with connect(readonly=True) as conn:
            tables = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
            for row in tables:
                name = row["name"]
                result[name] = conn.execute(
                    f'SELECT COUNT(*) FROM "{name}"'
                ).fetchone()[0]
    except (sqlite3.Error, FileNotFoundError):
        pass
    return result


def data_stats() -> dict[str, Any]:
    """业务数据概览，供前端设置页展示。"""
    counts = table_counts()
    first_date = None
    last_date = None
    try:
        first_date = scalar("SELECT MIN(order_date) FROM orders")
        last_date = scalar("SELECT MAX(order_date) FROM orders")
    except (sqlite3.Error, FileNotFoundError):
        pass

    return {
        "tables": counts,
        "orders": counts.get("orders", 0),
        "customers": counts.get("customers", 0),
        "products": counts.get("products", 0),
        "employees": counts.get("employees", 0),
        "date_range": {"start": first_date, "end": last_date},
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    return value


def execute_readonly(
    sql: str,
    max_rows: int = MAX_RESULT_ROWS,
) -> tuple[list[str] | None, list[list[Any]] | None, str | None, bool]:
    """执行只读 SQL。

    返回 ``(columns, rows, error, truncated)``。使用 SQLite authorizer 作为
    第二道防线，即使 SQL 校验被绕过，也不能执行写操作。
    """
    conn = None
    try:
        conn = connect(readonly=True)

        allowed = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
            sqlite3.SQLITE_RECURSIVE,
        }

        def authorizer(action, arg1, arg2, dbname, trigger):  # noqa: ANN001
            return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

        conn.set_authorizer(authorizer)
        cursor = conn.execute(sql)

        if cursor.description is None:
            return [], [], "该语句没有返回结果集", False

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchmany(max_rows + 1)
        truncated = len(rows) > max_rows
        rows = rows[:max_rows]

        return (
            columns,
            [[_json_safe(value) for value in row] for row in rows],
            None,
            truncated,
        )
    except sqlite3.Error as exc:
        return None, None, str(exc), False
    finally:
        if conn is not None:
            conn.close()
