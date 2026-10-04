import os
import sqlite3
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")

SCHEMA = """
数据库表结构：
- customers(id, name, city, age)
- orders(id, product, category, quantity, price, order_date, customer_id)
"""

def generate_sql(question: str) -> str:
    """将自然语言转换为 SQL"""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f"你是一个SQL专家。请根据用户问题生成SQLite查询语句，只返回SQL，不要解释。\n\n{SCHEMA}"},
            {"role": "user", "content": question}
        ],
        temperature=0
    )
    sql = response.choices[0].message.content.strip()
    # 清理可能的 markdown 代码块标记
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql

def execute_sql(sql: str):
    """执行 SQL 并返回结果"""
    conn = sqlite3.connect("business.db")
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return columns, results
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()

def text2sql(question: str) -> str:
    """完整流程：自然语言 → SQL → 查询结果 → 自然语言回答"""
    sql = generate_sql(question)
    print(f"生成的SQL: {sql}")

    columns, results = execute_sql(sql)
    if columns is None:
        return f"SQL执行失败: {results}"

    # 将查询结果交给大模型，生成自然语言回答
    data_str = f"列名: {columns}\n数据: {results}"
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是一个数据分析助手。请根据SQL查询结果，用自然语言回答用户问题，并给出简要洞察。"},
            {"role": "user", "content": f"用户问题：{question}\n\n查询结果：{data_str}"}
        ]
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    question = "销量最高的产品是什么？"
    answer = text2sql(question)
    print(f"\n回答：{answer}")