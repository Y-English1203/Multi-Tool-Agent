import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "conversation_memory.db"


def init_memory_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_session
            ON conversation_messages(user_id, session_id, id)
        """)


def get_history(user_id: str, session_id: str, limit: int = 10):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT role, content
            FROM conversation_messages
            WHERE user_id = ? AND session_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, session_id, limit)).fetchall()

    rows.reverse()
    return [
        {"role": role, "content": content}
        for role, content in rows
    ]


def save_message(user_id: str, session_id: str, role: str, content: str):
    if role not in ("user", "assistant"):
        raise ValueError("role 必须是 user 或 assistant")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO conversation_messages
                (user_id, session_id, role, content)
            VALUES (?, ?, ?, ?)
        """, (user_id, session_id, role, content))


init_memory_db()
