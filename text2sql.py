import os
import sqlite3
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

DB_PATH = "business.db"


def get_database_schema():
    """
    动态读取 SQLite 数据库真实 Schema。
    不再依赖硬编码的表结构。
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 获取所有用户表
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)

        tables = [row[0] for row in cursor.fetchall()]

        schema_lines = []

        for table in tables:
            cursor.execute(f'PRAGMA table_info("{table}")')
            columns = cursor.fetchall()

            column_names = [column[1] for column in columns]

            schema_lines.append(
                f"- {table}({', '.join(column_names)})"
            )

        return "\n".join(schema_lines)

    finally:
        conn.close()


def generate_sql(question: str, schema: str) -> str:
    """
    根据用户问题 + 真实数据库 Schema 生成 SQL。
    """

    system_prompt = f"""
你是一个专业的 SQLite Text-to-SQL Agent。

你的任务是根据用户问题和数据库真实 Schema 生成 SQL。

【数据库真实 Schema】
{schema}

【重要规则】
1. 只能使用 Schema 中真实存在的表和字段。
2. 严禁虚构不存在的字段。
3. 严禁虚构不存在的表。
4. 如果用户问题涉及数据库中不存在的数据，
   不要强行生成 SQL。
5. 如果无法回答，请返回：
   CANNOT_ANSWER: 原因
6. 如果可以回答，只返回 SQL，不要解释。
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": question
            }
        ],
        temperature=0
    )

    sql = response.choices[0].message.content.strip()

    # 清理 Markdown SQL 代码块
    sql = sql.replace("```sql", "")
    sql = sql.replace("```", "")
    sql = sql.strip()

    return sql


def execute_sql(sql: str):
    """
    执行 SQL 并返回结果。
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(sql)

        results = cursor.fetchall()

        if cursor.description:
            columns = [
                desc[0]
                for desc in cursor.description
            ]
        else:
            columns = []

        return columns, results

    except Exception as e:
        return None, str(e)

    finally:
        conn.close()


def text2sql(question: str) -> str:
    """
    完整流程：

    用户问题
        ↓
    获取真实 Schema
        ↓
    LLM Schema Linking
        ↓
    SQL
        ↓
    数据库执行
        ↓
    自然语言回答
    """

    # 1. 获取真实数据库 Schema
    schema = get_database_schema()

    print("\n[SQL Agent] ===== 数据库 Schema =====")
    print(schema)

    # 2. 根据 Schema 生成 SQL
    sql = generate_sql(
        question,
        schema
    )

    print("\n[SQL Agent] ===== 生成的 SQL =====")
    print(sql)

    # 3. 如果模型判断无法回答
    if sql.startswith("CANNOT_ANSWER:"):
        reason = sql.replace(
            "CANNOT_ANSWER:",
            "",
            1
        ).strip()

        return f"无法回答该问题：{reason}"

    # 4. 执行 SQL
    columns, results = execute_sql(sql)

    if columns is None:
        return f"SQL执行失败：{results}"

    # 5. 把查询结果交给 LLM
    data_str = f"""
列名：
{columns}

数据：
{results}
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": """
你是一个数据分析助手。

请根据 SQL 查询结果回答用户问题。

要求：
1. 直接回答用户问题。
2. 不要编造查询结果中不存在的信息。
3. 可以给出简短的数据分析。
"""
            },
            {
                "role": "user",
                "content": f"""
用户问题：
{question}

查询结果：
{data_str}
"""
            }
        ],
        temperature=0
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    question = "销量最高的产品是什么？"

    answer = text2sql(question)

    print(f"\n回答：{answer}")