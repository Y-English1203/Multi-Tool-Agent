"""Text-to-SQL Agent。

流程：
    自然语言问题
        -> 读取真实 Schema（含视图与业务口径）
        -> LLM 生成 SQL
        -> SQL 安全校验
        -> 只读执行
        -> 失败时把错误反馈给 LLM 自动修正一次
        -> LLM 根据结果生成中文回答
"""

from __future__ import annotations

import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from database import (
    MAX_RESULT_ROWS,
    execute_readonly,
    get_schema_prompt,
)
from sql_validator import ensure_limit, validate_sql

load_dotenv()

MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    timeout=90,
    max_retries=2,
)

SQL_EXAMPLES = """【示例】
问：销售额最高的品类是什么？
SQL:
SELECT category, ROUND(SUM(amount), 2) AS revenue
FROM v_sales_line
WHERE status IN ('已完成','已发货')
GROUP BY category
ORDER BY revenue DESC
LIMIT 1;

问：上个月有哪些订单？
SQL:
SELECT order_no, order_date, customer_name, total_amount, status
FROM v_order_summary
WHERE order_date >= '2026-09-01' AND order_date <= '2026-09-30'
ORDER BY order_date DESC
LIMIT 50;

问：哪个城市的客户下单最多？
SQL:
SELECT customer_city, COUNT(DISTINCT order_id) AS orders
FROM v_sales_line
WHERE status IN ('已完成','已发货')
GROUP BY customer_city
ORDER BY orders DESC
LIMIT 1;"""


def _clean_sql(text: str) -> str:
    sql = (text or "").strip()
    sql = re.sub(r"^```[a-zA-Z]*\s*", "", sql)
    sql = re.sub(r"\s*```$", "", sql).strip()
    sql = re.sub(r"^(SQL|sql)\s*[:：]\s*", "", sql)
    return sql.strip()


def generate_sql(
    question: str,
    schema: str,
    prior_sql: str | None = None,
    prior_error: str | None = None,
) -> str:
    """根据问题与真实 Schema 生成 SQL。"""
    repair_context = ""
    if prior_sql and prior_error:
        repair_context = f"""

【上一次生成的 SQL 执行失败，请修正】
上一次 SQL：
{prior_sql}

错误信息：
{prior_error}

请根据真实 Schema 修正 SQL，仍然只输出一条 SQL。"""

    system_prompt = f"""你是一个严谨的 SQLite Text-to-SQL 分析助手。

你的任务：把用户问题转换成一条可在 SQLite 中执行的 SELECT 查询。

{get_schema_prompt()}

{SQL_EXAMPLES}

【输出规则】
1. 只输出一条 SQL，不要解释，不要输出 Markdown 代码块。
2. 只能使用 Schema 中真实存在的表、视图和字段。
3. 优先使用视图 v_sales_line（订单商品明细）和 v_order_summary（订单汇总）。
4. 需要明细时加 ORDER BY 和 LIMIT，避免返回过多行。
5. 如果问题涉及数据库中不存在的数据，返回：
   CANNOT_ANSWER: 简短原因
6. 不要生成 INSERT / UPDATE / DELETE / DROP 等写操作。{repair_context}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=1200,
    )

    return _clean_sql(response.choices[0].message.content or "")


def _format_rows_for_llm(
    columns: list[str],
    rows: list[list[Any]],
    limit: int = 50,
) -> str:
    if not columns:
        return "（无结果）"

    header = " | ".join(str(col) for col in columns)
    lines = [header, "-" * len(header)]
    for row in rows[:limit]:
        lines.append(" | ".join("" if value is None else str(value) for value in row))
    if len(rows) > limit:
        lines.append(f"... 共 {len(rows)} 行，仅展示前 {limit} 行")
    return "\n".join(lines)


def _summarize(
    question: str,
    sql: str,
    columns: list[str],
    rows: list[list[Any]],
    note: str | None = None,
) -> str:
    if not rows:
        return "没有查询到符合条件的数据。"

    result_text = _format_rows_for_llm(columns, rows)
    note_text = f"\n注意：{note}" if note else ""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是企业数据分析助手。请严格根据 SQL 查询结果回答用户问题。\n"
                    "要求：\n"
                    "1. 先给出直接结论，再补 1-3 条关键数据说明。\n"
                    "2. 不要编造查询结果之外的信息。\n"
                    "3. 金额保留两位小数，必要时说明统计口径。\n"
                    "4. 如果查询结果来自 company_profile，金额单位是亿元，请在回答中注明。\n"
                    "5. 回答简洁，使用中文。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户问题：{question}\n\n"
                    f"执行的 SQL：\n{sql}{note_text}\n\n"
                    f"查询结果：\n{result_text}"
                ),
            },
        ],
        temperature=0,
        max_tokens=800,
    )

    return (response.choices[0].message.content or "").strip()


def ask_database(question: str) -> dict[str, Any]:
    """完整 Text-to-SQL 流程，返回结构化结果，供 API 与 Supervisor 使用。"""
    result: dict[str, Any] = {
        "answer": "",
        "sql": "",
        "columns": [],
        "rows": [],
        "row_count": 0,
        "truncated": False,
        "error": None,
        "tool_used": "sql",
    }

    try:
        schema = get_schema_prompt()
        sql = generate_sql(question, schema)
        result["sql"] = sql

        if not sql:
            result["answer"] = "无法根据当前数据库生成有效查询。"
            result["error"] = "empty_sql"
            return result

        if sql.upper().startswith("CANNOT_ANSWER"):
            reason = sql.split(":", 1)[-1].strip()
            result["answer"] = f"无法回答该问题：{reason}"
            result["error"] = "cannot_answer"
            return result

        is_valid, error_message = validate_sql(sql)
        if not is_valid:
            result["answer"] = f"SQL 校验未通过：{error_message}"
            result["error"] = error_message
            return result

        sql = ensure_limit(sql, MAX_RESULT_ROWS)
        result["sql"] = sql
        columns, rows, execute_error, truncated = execute_readonly(sql)

        # 执行失败时自动修正一次
        if execute_error:
            repaired = generate_sql(
                question,
                schema,
                prior_sql=sql,
                prior_error=execute_error,
            )
            if repaired and not repaired.upper().startswith("CANNOT_ANSWER"):
                repaired_valid, _repaired_message = validate_sql(repaired)
                if repaired_valid:
                    repaired_sql = ensure_limit(repaired, MAX_RESULT_ROWS)
                    columns, rows, execute_error, truncated = execute_readonly(
                        repaired_sql
                    )
                    if not execute_error:
                        sql = repaired_sql
                        result["sql"] = sql

        if execute_error:
            result["answer"] = f"SQL 执行失败：{execute_error}"
            result["error"] = execute_error
            return result

        columns = columns or []
        rows = rows or []

        result["columns"] = columns
        result["rows"] = rows
        result["row_count"] = len(rows)
        result["truncated"] = truncated
        result["answer"] = _summarize(
            question,
            sql,
            columns,
            rows,
            note="结果超过 200 行，已截断" if truncated else None,
        )
        return result

    except Exception as exc:  # 网络 / 模型异常
        result["answer"] = "数据分析服务暂时不可用，请稍后再试。"
        result["error"] = str(exc)
        return result


def text2sql(question: str) -> str:
    """兼容旧调用方式的字符串入口。"""
    return ask_database(question)["answer"]


if __name__ == "__main__":
    question = "销售额最高的品类是什么？"
    outcome = ask_database(question)
    print(outcome["sql"])
    print(outcome["answer"])
