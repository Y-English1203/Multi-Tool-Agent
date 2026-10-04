import sqlite3

conn = sqlite3.connect("business.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    product TEXT,
    category TEXT,
    quantity INTEGER,
    price REAL,
    order_date TEXT,
    customer_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    name TEXT,
    city TEXT,
    age INTEGER
)
""")

cursor.executemany("INSERT OR REPLACE INTO customers VALUES (?,?,?,?)", [
    (1, "张三", "广州", 28), (2, "李四", "深圳", 35), (3, "王五", "北京", 22),
])

cursor.executemany("INSERT OR REPLACE INTO orders VALUES (?,?,?,?,?,?,?)", [
    (1, "笔记本电脑", "电子", 2, 5999, "2026-08-01", 1),
    (2, "手机", "电子", 1, 3999, "2026-08-15", 2),
    (3, "办公椅", "家具", 3, 899, "2026-09-01", 1),
    (4, "显示器", "电子", 1, 1599, "2026-09-10", 3),
    (5, "台灯", "家具", 2, 199, "2026-09-18", 2),
])

conn.commit()
conn.close()
print("数据库初始化完成")