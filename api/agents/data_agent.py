"""Data agent: text-to-SQL over the procurement.duckdb structured data.

Guardrails: the generated SQL is checked against a keyword/shape allowlist
(single SELECT/WITH statement, no DDL/DML/pragma/attach keywords, no
statement chaining) before it's ever executed, and it runs against a
DuckDB connection opened read_only=True. This is a regex-based guard, not
a full SQL parser -- acceptable here because the SQL is model-generated
from a fixed, known schema (not raw user input), but a production version
would add an AST-level allowlist (e.g. via sqlglot) as defense in depth.
"""

import json
import re

from .store import CHAT_MODEL, get_client, get_db_connection, get_schema_description

SQL_SYSTEM_PROMPT = """You write DuckDB SQL for a procurement data analyst tool. \
Given the schema below, write ONE read-only SQL query (SELECT or WITH...SELECT only) that \
answers the user's question.

{schema}

Rules:
- Only reference the tables/columns listed above.
- Use ILIKE for case-insensitive text matching. UNSPSC titles use formal commodity terminology \
(e.g. "Notebook computers", not "laptops") -- consider likely synonyms when matching titles.
- Always alias aggregates with clear names (e.g. total_spend, not sum(total_price)).
- Add a LIMIT unless the query is a single-row aggregate.
- Respond with strict JSON: {{"sql": "<the query>"}}"""

SUMMARY_SYSTEM_PROMPT = """You are a procurement data analyst. Given the user's question, the \
SQL query that was run, and the resulting rows (as JSON), write a concise natural-language \
answer. Use ONLY the numbers present in the result rows -- never invent or round in a way that \
changes the figure. If the result is empty, say so plainly."""

FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter", "attach", "detach", "pragma",
    "create", "copy ", "export", "import", "call ", "install", "load ", "vacuum",
    "truncate", "grant", "revoke", "set ",
)

MAX_ROWS_RETURNED = 200
MAX_ROWS_FOR_SUMMARY = 30


def validate_and_prepare_sql(sql: str) -> str:
    s = sql.strip().rstrip(";").strip()
    if not s:
        raise ValueError("empty SQL")
    lowered = s.lower()
    first_word = re.split(r"\s", lowered, maxsplit=1)[0]
    if first_word not in ("select", "with"):
        raise ValueError(f"only SELECT/WITH queries are allowed, got: {first_word!r}")
    if ";" in s:
        raise ValueError("multiple statements are not allowed")
    for kw in FORBIDDEN_KEYWORDS:
        if kw in lowered:
            raise ValueError(f"forbidden keyword detected: {kw.strip()!r}")
    if "limit" not in lowered:
        s = f"SELECT * FROM ({s}) AS _sub LIMIT {MAX_ROWS_RETURNED}"
    return s


def generate_sql(query: str) -> str:
    resp = get_client().chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SQL_SYSTEM_PROMPT.format(schema=get_schema_description())},
            {"role": "user", "content": query},
        ],
    )
    result = json.loads(resp.choices[0].message.content)
    return result["sql"]


def summarize_results(query: str, sql: str, columns: list, rows: list) -> str:
    sample = rows[:MAX_ROWS_FOR_SUMMARY]
    payload = json.dumps({"columns": columns, "rows": sample, "truncated": len(rows) > len(sample)}, default=str)
    resp = get_client().chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {query}\n\nSQL: {sql}\n\nResults: {payload}"},
        ],
    )
    return resp.choices[0].message.content


def answer_from_data(query: str) -> dict:
    raw_sql = generate_sql(query)
    try:
        safe_sql = validate_and_prepare_sql(raw_sql)
    except ValueError as e:
        return {"sql": raw_sql, "error": f"blocked unsafe SQL: {e}", "answer": None, "columns": [], "rows": []}

    try:
        con = get_db_connection()
        cursor = con.execute(safe_sql)
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
    except Exception as e:
        return {"sql": safe_sql, "error": f"SQL execution failed: {e}", "answer": None, "columns": [], "rows": []}

    row_dicts = [dict(zip(columns, r)) for r in rows]
    answer = summarize_results(query, safe_sql, columns, row_dicts)
    return {"sql": safe_sql, "error": None, "answer": answer, "columns": columns, "rows": row_dicts[:MAX_ROWS_FOR_SUMMARY]}
