from __future__ import annotations

import json
import sqlite3
import uuid

import matplotlib.pyplot as plt

from src.agents.safety import validate_sql_readonly
from src.config.settings import settings
from src.core.paths import RESULTS_DIR
from src.llm import build_llm


SYSTEM_PROMPT = """
You generate chart specifications.

Return ONLY valid JSON.

Example:

{
    "chart_type":"bar",
    "sql":"SELECT region, SUM(sales) AS total_sales FROM orders GROUP BY region ORDER BY total_sales DESC",
    "title":"Sales by Region",
    "xlabel":"Region",
    "ylabel":"Sales"
}

Rules:

- chart_type must be one of:
bar
line
scatter
hist

- SQL must be read only.
- Do not explain anything.
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


def generate_chart_core(question):

    llm = build_llm()

    response = llm.invoke([
        {
            "role":"system",
            "content":SYSTEM_PROMPT
        },
        {
            "role":"user",
            "content":question
        }
    ])

    raw = response.content.strip()

    raw = raw.replace("```json","")
    raw = raw.replace("```","")

    spec = json.loads(raw)

    rows = execute(spec["sql"])

    path = render(spec, rows)

    return {
        "ok":True,
        "path":path,
        "rows":rows,
        "spec":spec
    }