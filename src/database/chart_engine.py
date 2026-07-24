from __future__ import annotations

import json
import sqlite3
import uuid

import matplotlib.pyplot as plt

from src.agents.safety import validate_sql_readonly
from src.config.settings import settings
from src.core.paths import RESULTS_DIR
from src.llm import build_llm
from src.database.sql_engine import get_schema


SYSTEM_PROMPT = """
You generate chart specifications for a SQLite database.

Return ONLY valid JSON.

The database is SQLite.

VERY IMPORTANT:

Dates are stored as ISO strings.

To extract months use:

strftime('%Y-%m', order_date)

Never use:

EXTRACT(...)
DATE_TRUNC(...)
MONTH(...)
YEAR(...)

Return JSON exactly like:

{
    "chart_type":"line",
    "sql":"SELECT strftime('%Y-%m', order_date) AS month, SUM(sales) AS total_sales FROM orders GROUP BY month ORDER BY month",
    "title":"Monthly Sales",
    "xlabel":"Month",
    "ylabel":"Sales"
}

Rules:

- Output ONLY JSON.
- SQL must be valid SQLite.
- SQL must be read-only.
- No explanations.
"""


def execute(sql):

    sql = validate_sql_readonly(sql)

    con = sqlite3.connect(settings.database_path)
    con.row_factory = sqlite3.Row

    rows = con.execute(sql).fetchall()

    con.close()

    return [dict(r) for r in rows]


def render(spec, rows):

    chart = spec["chart_type"]

    plt.figure(figsize=(8,5))

    if chart == "bar":

        x = list(rows[0].keys())[0]
        y = list(rows[0].keys())[1]

        plt.bar(
            [r[x] for r in rows],
            [r[y] for r in rows]
        )

    elif chart == "line":

        x = list(rows[0].keys())[0]
        y = list(rows[0].keys())[1]

        plt.plot(
            [r[x] for r in rows],
            [r[y] for r in rows]
        )

    plt.title(spec["title"])
    plt.xlabel(spec["xlabel"])
    plt.ylabel(spec["ylabel"])

    plt.tight_layout()

    RESULTS_DIR.mkdir(exist_ok=True)

    output = RESULTS_DIR / f"{uuid.uuid4().hex}.png"

    plt.savefig(output)

    plt.close()

    return str(output)


def generate_chart_core(question, max_retries=3):

    llm = build_llm()

    error_context = None
    last_error = ""

    for attempt in range(1, max_retries + 1):

        user_prompt = question

        if error_context:

            user_prompt += f"""

Previous attempt failed.

Error:

{error_context}

Return corrected JSON.
"""

        response = llm.invoke([
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": f"""
        Schema:

        {get_schema()}

        Question:

        {question}
        """
            }
        ])

        raw = response.content.strip()

        raw = raw.replace("```json", "")
        raw = raw.replace("```", "")

        try:

            spec = json.loads(raw)

            rows = execute(spec["sql"])

            path = render(spec, rows)

            return {
                "ok": True,
                "path": path,
                "rows": rows,
                "spec": spec,
                "attempts": attempt,
                "retried": attempt > 1,
                "error": None
            }

        except Exception as e:

            last_error = str(e)
            error_context = last_error

    return {
        "ok": False,
        "path": None,
        "rows": None,
        "spec": None,
        "attempts": max_retries,
        "retried": True,
        "error": last_error
    }