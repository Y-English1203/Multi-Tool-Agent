"""多轮对话记忆。

按 ``(user_id, session_id)`` 隔离会话；提供历史读取、会话列表、
删除会话和基础统计，供聊天接口与前端会话面板使用。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "conversation_memory.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_memory_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_session
            ON conversation_messages(user_id, session_id, id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_user
            ON conversation_messages(user_id, id)
            """
        )
        conn.execute("PRAGMA journal_mode = WAL")


def get_history(user_id: str, session_id: str, limit: int = 10) -> list[dict[str, str]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM conversation_messages
            WHERE user_id = ? AND session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, session_id, max(1, min(int(limit or 10), 50))),
        ).fetchall()

    rows = list(reversed(rows))
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def save_message(user_id: str, session_id: str, role: str, content: str) -> None:
    if role not in ("user", "assistant"):
        raise ValueError("role 必须是 user 或 assistant")
    if not (content or "").strip():
        return

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO conversation_messages
                (user_id, session_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                session_id,
                role,
                content,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )


def list_sessions(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """返回会话列表，标题取该会话第一条用户消息。"""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                m.session_id                AS session_id,
                COUNT(*)                    AS message_count,
                MIN(m.id)                   AS first_id,
                MAX(m.id)                   AS last_id,
                MAX(m.created_at)           AS updated_at,
                (
                    SELECT content
                    FROM conversation_messages t
                    WHERE t.user_id = m.user_id
                      AND t.session_id = m.session_id
                      AND t.role = 'user'
                    ORDER BY t.id
                    LIMIT 1
                )                           AS title
            FROM conversation_messages m
            WHERE m.user_id = ?
            GROUP BY m.session_id
            ORDER BY last_id DESC
            LIMIT ?
            """,
            (user_id, max(1, min(int(limit or 50), 200))),
        ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        title = (item.get("title") or "新对话").strip().replace("\n", " ")
        item["title"] = title[:24] + ("…" if len(title) > 24 else "")
        result.append(item)
    return result


def get_session_messages(
    user_id: str,
    session_id: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, role, content, created_at
            FROM conversation_messages
            WHERE user_id = ? AND session_id = ?
            ORDER BY id
            LIMIT ?
            """,
            (user_id, session_id, max(1, min(int(limit or 200), 500))),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_session(user_id: str, session_id: str) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            """
            DELETE FROM conversation_messages
            WHERE user_id = ? AND session_id = ?
            """,
            (user_id, session_id),
        )
        return cursor.rowcount


def clear_user_history(user_id: str) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM conversation_messages WHERE user_id = ?", (user_id,)
        )
        return cursor.rowcount


def conversation_stats(user_id: str | None = None) -> dict[str, Any]:
    where = "WHERE user_id = ?" if user_id else ""
    params: tuple[Any, ...] = (user_id,) if user_id else ()

    with _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM conversation_messages {where}", params
        ).fetchone()[0]
        sessions = conn.execute(
            f"SELECT COUNT(DISTINCT session_id) FROM conversation_messages {where}",
            params,
        ).fetchone()[0]
        users = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM conversation_messages"
        ).fetchone()[0]
        today = conn.execute(
            f"""
            SELECT COUNT(*) FROM conversation_messages
            {where + ' AND' if where else 'WHERE'} date(created_at) = date('now', 'localtime')
            """,
            params,
        ).fetchone()[0]

    return {
        "messages": total,
        "sessions": sessions,
        "users": users,
        "today_messages": today,
    }


init_memory_db()
