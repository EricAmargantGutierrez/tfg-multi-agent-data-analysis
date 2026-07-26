from __future__ import annotations

import json
import sqlite3
import uuid

import matplotlib.pyplot as plt

from src.agents.safety import validate_sql_readonly
from src.config.settings import settings
from src.core.paths import RESULTS_DIR
from src.database.sql_engine import get_schema
from src.llm import build_llm


SYSTEM_PROMPT = """
You generate chart specifications for a SQLite database.

Return ONLY valid JSON.

Supported chart types:

- bar
- line
- scatter
- pie
- histogram
- boxplot

The database is SQLite.

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
    "chart_type":"bar",
    "sql":"SELECT category, SUM(sales) AS total_sales FROM orders GROUP BY category",
    "title":"Sales by Category",
    "xlabel":"Category",
    "ylabel":"Sales"
}

Rules:

- Output ONLY JSON.
- SQL must be valid SQLite.
- SQL must be read-only.
- Use ONLY the supported chart types.
"""


def execute(sql):

    sql = validate_sql_readonly(sql)

    con = sqlite3.connect(settings.database_path)
    con.row_factory = sqlite3.Row

    rows = con.execute(sql).fetchall()

    con.close()

    return [dict(r) for r in rows]


def render(spec, rows):

    if not rows:
        raise ValueError("No rows returned.")

    chart = spec["chart_type"].lower()

    plt.figure(figsize=(8, 5))

    keys = list(rows[0].keys())

    x = keys[0]
    y = keys[1] if len(keys) > 1 else None

    if chart == "bar":

        plt.bar(
            [r[x] for r in rows],
            [r[y] for r in rows],
        )

    elif chart == "line":

        plt.plot(
            [r[x] for r in rows],
            [r[y] for r in rows],
            marker="o",
        )

    elif chart == "scatter":

        plt.scatter(
            [r[x] for r in rows],
            [r[y] for r in rows],
        )

    elif chart == "pie":

        plt.pie(
            [r[y] for r in rows],
            labels=[r[x] for r in rows],
            autopct="%1.1f%%",
        )

    elif chart == "histogram":

        plt.hist(
            [r[x] for r in rows],
            bins=20,
        )

    elif chart == "boxplot":

        plt.boxplot(
            [r[x] for r in rows],
            vert=True,
        )

    else:

        raise ValueError(
            f"Unsupported chart type '{chart}'."
        )

    plt.title(spec.get("title", ""))

    if chart != "pie":

        plt.xlabel(spec.get("xlabel", ""))
        plt.ylabel(spec.get("ylabel", ""))

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

        prompt = f"""
Schema:

{get_schema()}

Question:

{question}
"""

        if error_context:

            prompt += f"""

Previous attempt failed.

Error:

{error_context}

Return corrected JSON only.
"""

        try:

            response = llm.invoke(
                [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ]
            )

            raw = response.content.strip()

            raw = raw.replace("```json", "")
            raw = raw.replace("```", "")

            spec = json.loads(raw)

            if "chart_type" not in spec:
                raise ValueError("Missing chart_type.")

            if "sql" not in spec:
                raise ValueError("Missing sql.")

            rows = execute(spec["sql"])

            path = render(spec, rows)

            return {
                "ok": True,
                "path": path,
                "rows": rows,
                "spec": spec,
                "attempts": attempt,
                "retried": attempt > 1,
                "error": None,
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
        "error": last_error,
    }