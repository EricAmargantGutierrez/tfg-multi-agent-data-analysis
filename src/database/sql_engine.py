"""
sql_agent.py — MCP server exposing the SQL Agent.

Responsibility (single, narrow — the whole point of the agent pattern):
    given a natural-language question + the schema, produce and run a
    read-only SQL query against the Superstore SQLite DB, self-correcting on
    error, and return structured rows.

It exposes ONE MCP tool: run_sql(question, max_retries) -> structured result.

Why the LLM lives *inside* this server:
    Your proposal has the orchestrator's LLM do routing, and each agent do its
    own specialised work. The SQL agent needs its own LLM call to turn language
    into SQL and to self-correct. That call uses the same llm factory, so the
    agent's model can match (or deliberately differ from) the orchestrator's.

Run standalone for debugging:
    python -m src.agents.sql_agent            # starts an MCP stdio server
Or test the core function directly:
    python -m src.agents.sql_agent --selftest "Which region had the most sales?"
"""
from pathlib import Path
import sqlite3
from typing import Any

from src.agents.safety import UnsafeSQLError, validate_sql_readonly
from src.config.settings import settings
from src.llm import build_llm

DB_PATH = settings.database_path
MAX_ROWS = 1000  # hard cap so a runaway query can't flood the context


# ---------------------------------------------------------------------------
# Schema introspection — the LLM writes better SQL when handed the real schema.
# ---------------------------------------------------------------------------
def get_schema(db_path: Path = DB_PATH, table: str = "orders") -> str:
    con = sqlite3.connect(db_path)
    try:
        cols = con.execute(f"PRAGMA table_info({table})").fetchall()
        # sample a couple of rows so the model sees value formats (e.g. dates)
        sample = con.execute(f"SELECT * FROM {table} LIMIT 2").fetchall()
    finally:
        con.close()
    lines = [f"Table: {table}", "Columns:"]
    for _, name, ctype, *_ in cols:
        lines.append(f"  - {name} ({ctype})")
    lines.append("")
    lines.append("Notes for writing SQL:")
    lines.append("  - order_date and ship_date are ISO strings 'YYYY-MM-DD'.")
    lines.append("  - Use strftime('%Y', order_date) to extract the year,")
    lines.append("    strftime('%Y-%m', order_date) for year-month.")
    lines.append(f"Sample rows: {sample}")
    return "\n".join(lines)


def _run_query(sql: str, db_path: Path = DB_PATH) -> dict[str, Any]:
    """Execute a validated read-only query. Returns columns + rows."""
    safe = validate_sql_readonly(sql)
    # Open read-only via URI so even a bug can't mutate the DB.
    uri = f"file:{db_path}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        cur = con.execute(safe)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(MAX_ROWS)
    finally:
        con.close()
    return {"columns": columns, "rows": [list(r) for r in rows], "sql": safe}


SYSTEM_PROMPT = """
You are an expert SQLite SQL generator.

Your task is to answer the user's question by generating ONE read-only SQLite query.

Return ONLY SQL.
No markdown.
No explanations.
No comments.

Rules:

- Use only SELECT or WITH statements.
- Never modify the database.
- Use ONLY the columns present in the provided schema.
- Use valid SQLite syntax.
- Dates are stored as ISO strings (YYYY-MM-DD).
- Use strftime() when extracting dates.
- Never use SELECT *.
- Return ONLY the columns needed to answer the question.

Ranking questions:

If the question contains ideas such as:

- highest
- lowest
- largest
- smallest
- most
- least
- best
- worst
- top

always return:

1. the entity requested
2. the numerical value used for ranking

Examples:

Question:
Which region has the highest total sales?

Correct:

SELECT
    region,
    SUM(sales) AS total_sales
FROM orders
GROUP BY region
ORDER BY total_sales DESC
LIMIT 1;

------------------------------------

Question:
Which customer placed the most orders?

Correct:

SELECT
    customer_name,
    COUNT(*) AS total_orders
FROM orders
GROUP BY customer_name
ORDER BY total_orders DESC
LIMIT 1;

------------------------------------

Question:
Which category generated the highest profit?

Correct:

SELECT
    category,
    SUM(profit) AS total_profit
FROM orders
GROUP BY category
ORDER BY total_profit DESC
LIMIT 1;

------------------------------------

Question:
Find the order with the highest sales.

Correct:

SELECT
    order_id,
    sales
FROM orders
ORDER BY sales DESC
LIMIT 1;

Do NOT return the entire row.

------------------------------------

Aggregation rules:

If the question asks for:

- total
- average
- mean
- count
- sum
- minimum
- maximum

return the aggregated value.

Never include unrelated columns.

When grouping, always include the aggregate value used for sorting.

Always prefer explicit aliases such as:

AS total_sales
AS total_profit
AS total_orders
AS total_quantity

The generated query should be the smallest query that completely answers the user's question.
"""


def generate_sql(question: str, schema: str, llm, error_context: str | None = None) -> str:
    """Ask the LLM for SQL, optionally with a prior error to correct."""
    user = f"Schema:\n{schema}\n\nQuestion: {question}"
    if error_context:
        user += (
            f"\n\nYour previous attempt failed with this error:\n{error_context}\n"
            "Return a corrected query. Output ONLY the SQL."
        )
    resp = llm.invoke(
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user", "content": user}]
    )
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    # Strip accidental markdown fences.
    return text.replace("```sql", "").replace("```", "").strip()


def run_sql_core(
    question: str,
    *,
    model_key: str | None = None,
    max_retries: int = 3,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    """
    The self-correcting SQL loop. This is the function the MCP tool wraps and
    the function your unit tests call directly.

    Returns a dict with keys:
      ok, columns, rows, sql, attempts, retried, error
    """
    llm = build_llm(model_key)
    schema = get_schema(db_path)
    error_context: str | None = None
    last_error = ""

    for attempt in range(1, max_retries + 1):
        sql = generate_sql(question, schema, llm, error_context)
        try:
            result = _run_query(sql, db_path)
            result.update(
                ok=True, attempts=attempt, retried=attempt > 1, error=None
            )
            return result
        except (sqlite3.Error, UnsafeSQLError) as e:
            last_error = f"{type(e).__name__}: {e}"
            error_context = f"Query:\n{sql}\nError: {last_error}"

    return {
        "ok": False, "columns": [], "rows": [], "sql": sql,
        "attempts": max_retries, "retried": True, "error": last_error,
    }