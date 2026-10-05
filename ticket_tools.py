import sqlite3
from datetime import datetime

def init_ticket_db():
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        issue TEXT,
        priority TEXT,
        status TEXT DEFAULT '待处理',
        created_at TEXT,
        updated_at TEXT
    )
    """)
    conn.commit()
    conn.close()

def create_ticket(user_id: str, issue: str, priority: str = "中") -> str:
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO tickets (user_id, issue, priority, created_at, updated_at) VALUES (?,?,?,?,?)",
        (user_id, issue, priority, now, now)
    )
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return f"工单已创建，编号：{ticket_id}，优先级：{priority}，问题：{issue}"

def list_user_tickets(user_id: str) -> str:
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, issue, status FROM tickets WHERE user_id=?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return f"用户 {user_id} 暂无工单"
    result = "\n".join([f"工单 {r[0]}：{r[1]}，状态：{r[2]}" for r in rows])
    return f"用户 {user_id} 的工单列表：\n{result}"

def check_ticket_status(ticket_id: int) -> str:
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, issue, status FROM tickets WHERE id=?", (ticket_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return f"未找到编号为 {ticket_id} 的工单"
    return f"工单 {row[0]}：{row[1]}，状态：{row[2]}"