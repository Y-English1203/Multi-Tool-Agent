"""SQL 安全校验。

Text-to-SQL 生成的 SQL 在真正执行前必须经过这里：
* 只允许单条 SELECT / WITH ... SELECT；
* 拒绝 DDL、DML、PRAGMA、ATTACH 等语句；
* 关键词检测会先屏蔽字符串字面量和注释，避免误判。
"""

from __future__ import annotations

import re

ALLOWED_FIRST_WORDS = {"SELECT", "WITH"}

FORBIDDEN_KEYWORDS = (
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "REPLACE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
    "LOAD_EXTENSION",
    "WRITEFILE",
    "READFILE",
)

_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE = re.compile(r"--[^\n]*")
_STRING_LITERAL = re.compile(r"'(?:''|[^'])*'", re.DOTALL)
_DOUBLE_QUOTED = re.compile(r'"(?:""|[^"])*"', re.DOTALL)


def _mask_literals(sql: str) -> str:
    """把字符串字面量替换为占位符，防止关键词出现在字符串中被误判。"""
    masked = _COMMENT_BLOCK.sub(" ", sql)
    masked = _COMMENT_LINE.sub(" ", masked)
    masked = _STRING_LITERAL.sub("''", masked)
    masked = _DOUBLE_QUOTED.sub('""', masked)
    return masked


def validate_sql(sql: str) -> tuple[bool, str | None]:
    """返回值：``(是否通过, 错误信息)``。"""
    if not sql or not sql.strip():
        return False, "SQL 为空"

    sql_clean = sql.strip()

    # 去除代码块标记（模型偶尔会带 ```sql）
    sql_clean = re.sub(r"^```[a-zA-Z]*\s*", "", sql_clean)
    sql_clean = re.sub(r"\s*```$", "", sql_clean).strip()

    if not sql_clean:
        return False, "SQL 为空"

    # 只允许一个结尾分号；先屏蔽字符串/注释，避免把字面量里的分号误判为多语句
    body = sql_clean.rstrip(";").strip()
    masked = _mask_literals(body)
    if ";" in masked:
        return False, "检测到多条 SQL 语句，禁止执行"

    sql_upper = masked.upper()

    tokens = sql_upper.split()
    first_word = tokens[0] if tokens else ""
    if first_word not in ALLOWED_FIRST_WORDS:
        return False, f"禁止执行 {first_word or '未知'} 类型 SQL，系统只允许查询操作"

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", sql_upper):
            return False, f"检测到危险关键词：{keyword}"

    if re.search(r"\bINTO\b", sql_upper):
        return False, "禁止使用 INTO 子句"

    return True, None


def ensure_limit(sql: str, limit: int = 200) -> str:
    """给没有 LIMIT 的明细查询补一个上限，避免一次拉取过多数据。"""
    body = sql.strip().rstrip(";")
    if re.search(r"\bLIMIT\b", body, re.IGNORECASE):
        return body
    return f"{body}\nLIMIT {limit}"
