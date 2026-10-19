"""工单数据访问层。

所有工单操作都带 ``user_id`` 过滤，避免用户之间互相看到工单。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tickets.db"

STATUSES = ["待处理", "处理中", "已解决", "已关闭"]
PRIORITIES = ["高", "中", "低"]
CATEGORIES = [
    "账号权限",
    "办公设备",
    "网络服务",
    "软件系统",
    "财务报销",
    "门禁工牌",
    "行政服务",
    "差旅服务",
    "人力资源",
    "其他",
]

STATUS_ALIASES = {
    "未处理": "待处理",
    "待分配": "待处理",
    "处理完成": "已解决",
    "已完成": "已解决",
    "完成": "已解决",
    "已回复": "已解决",
    "关闭": "已关闭",
}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_ticket_db() -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                issue TEXT NOT NULL,
                category TEXT DEFAULT '其他',
                priority TEXT DEFAULT '中',
                status TEXT DEFAULT '待处理',
                assignee TEXT,
                resolution TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)"
        )

        # 兼容旧版数据库：补上新增字段
        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(tickets)").fetchall()
        }
        for column, ddl in {
            "category": "TEXT DEFAULT '其他'",
            "assignee": "TEXT",
            "resolution": "TEXT",
        }.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE tickets ADD COLUMN {column} {ddl}")

        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _normalize_status(status: str | None) -> str | None:
    if not status:
        return None
    value = str(status).strip()
    return STATUS_ALIASES.get(value, value)


def create_ticket(
    user_id: str,
    issue: str,
    priority: str = "中",
    category: str = "其他",
    assignee: str | None = None,
) -> dict[str, Any]:
    issue = (issue or "").strip()
    if not issue:
        raise ValueError("工单问题描述不能为空")

    priority = priority if priority in PRIORITIES else "中"
    category = category if category in CATEGORIES else "其他"
    now = _now()

    conn = _connect()
    try:
        cursor = conn.execute(
            """
            INSERT INTO tickets
                (user_id, issue, category, priority, status,
                 assignee, resolution, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                user_id,
                issue,
                category,
                priority,
                "待处理",
                assignee,
                None,
                now,
                now,
            ),
        )
        conn.commit()
        ticket_id = cursor.lastrowid
    finally:
        conn.close()

    return get_ticket(ticket_id) or {}


def get_ticket(ticket_id: int) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def list_tickets(
    user_id: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    keyword: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if user_id:
        clauses.append("user_id = ?")
        params.append(user_id)
    if status:
        normalized = _normalize_status(status)
        if normalized in STATUSES:
            clauses.append("status = ?")
            params.append(normalized)
    if priority and priority in PRIORITIES:
        clauses.append("priority = ?")
        params.append(priority)
    if keyword:
        clauses.append("(issue LIKE ? OR category LIKE ? OR resolution LIKE ?)")
        like = f"%{keyword.strip()}%"
        params.extend([like, like, like])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit = max(1, min(int(limit or 100), 500))

    conn = _connect()
    try:
        rows = conn.execute(
            f"""
            SELECT * FROM tickets
            {where}
            ORDER BY
                CASE status
                    WHEN '待处理' THEN 0
                    WHEN '处理中' THEN 1
                    WHEN '已解决' THEN 2
                    ELSE 3
                END,
                id DESC
            LIMIT ?
            """,
            tuple(params + [limit]),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_ticket(
    ticket_id: int,
    status: str | None = None,
    priority: str | None = None,
    resolution: str | None = None,
    assignee: str | None = None,
) -> dict[str, Any] | None:
    updates: list[str] = []
    params: list[Any] = []

    if status is not None:
        normalized = _normalize_status(status)
        if normalized not in STATUSES:
            raise ValueError(f"无效的工单状态：{status}")
        updates.append("status = ?")
        params.append(normalized)

    if priority is not None:
        if priority not in PRIORITIES:
            raise ValueError(f"无效的优先级：{priority}")
        updates.append("priority = ?")
        params.append(priority)

    if resolution is not None:
        updates.append("resolution = ?")
        params.append(resolution.strip() or None)

    if assignee is not None:
        updates.append("assignee = ?")
        params.append(assignee.strip() or None)

    if not updates:
        return get_ticket(ticket_id)

    updates.append("updated_at = ?")
    params.append(_now())
    params.append(ticket_id)

    conn = _connect()
    try:
        cursor = conn.execute(
            f"UPDATE tickets SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        return get_ticket(ticket_id)
    finally:
        conn.close()


def ticket_stats(user_id: str | None = None) -> dict[str, Any]:
    where = "WHERE user_id = ?" if user_id else ""
    params: tuple[Any, ...] = (user_id,) if user_id else ()

    conn = _connect()
    try:
        rows = conn.execute(
            f"""
            SELECT status, priority, COUNT(*) AS count
            FROM tickets
            {where}
            GROUP BY status, priority
            """,
            params,
        ).fetchall()

        total = sum(row["count"] for row in rows)
        by_status = {status: 0 for status in STATUSES}
        by_priority = {priority: 0 for priority in PRIORITIES}
        for row in rows:
            by_status[row["status"]] = by_status.get(row["status"], 0) + row["count"]
            by_priority[row["priority"]] = (
                by_priority.get(row["priority"], 0) + row["count"]
            )

        resolved = by_status.get("已解决", 0) + by_status.get("已关闭", 0)
        return {
            "total": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "open": by_status.get("待处理", 0) + by_status.get("处理中", 0),
            "resolved": resolved,
            "resolve_rate": round(resolved / total * 100, 2) if total else 0.0,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 给 Agent 使用的文本格式化
# ---------------------------------------------------------------------------

def format_ticket(ticket: dict[str, Any]) -> str:
    lines = [
        f"工单 #{ticket['id']}",
        f"问题：{ticket['issue']}",
        f"分类：{ticket.get('category') or '其他'}",
        f"优先级：{ticket.get('priority') or '中'}",
        f"状态：{ticket.get('status') or '待处理'}",
    ]
    if ticket.get("assignee"):
        lines.append(f"处理人：{ticket['assignee']}")
    if ticket.get("resolution"):
        lines.append(f"处理结果：{ticket['resolution']}")
    lines.append(f"创建时间：{ticket.get('created_at')}")
    lines.append(f"更新时间：{ticket.get('updated_at')}")
    return "\n".join(lines)


def format_ticket_list(tickets: list[dict[str, Any]], user_id: str) -> str:
    if not tickets:
        return f"用户 {user_id} 暂无工单。"

    lines = [f"用户 {user_id} 的工单列表（共 {len(tickets)} 张）："]
    for ticket in tickets:
        lines.append(
            f"- #{ticket['id']} [{ticket.get('status')}] "
            f"{ticket['issue']}（优先级：{ticket.get('priority')}，"
            f"创建于 {ticket.get('created_at')}）"
        )
    return "\n".join(lines)


# 兼容旧接口 ---------------------------------------------------------------

def list_user_tickets(user_id: str) -> str:
    return format_ticket_list(list_tickets(user_id=user_id), user_id)


def check_ticket_status(ticket_id: int) -> str:
    ticket = get_ticket(ticket_id)
    if not ticket:
        return f"未找到编号为 {ticket_id} 的工单。"
    return format_ticket(ticket)


init_ticket_db()
