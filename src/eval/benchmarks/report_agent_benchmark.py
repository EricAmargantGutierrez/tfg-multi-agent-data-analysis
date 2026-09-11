"""
src/eval/benchmarks/report_agent_benchmark.py

The Report Agent has no ground truth. A session summary has no single
"correct" answer, so this one is checked by hand, not scored.

It also doesn't test single questions. The Report Agent works on a whole
session, so this runs 6 sessions -- each a few questions covering
data_query / analysis / visualization -- through the real orchestrator
(routing, agents, narration), then generates a report for each.

Sessions 1-5 are normal. Session 6 is adversarial: every question is
impossible to answer from the data (missing columns, a customer that
doesn't exist, causal questions). It checks whether the Report Agent
says so or instead makes something up. It uses a different rating
template and is reported on its own, not averaged with sessions 1-5.

Output: results/eval/<model>/<language>/report_agent_review.md -- one
file with every session's questions, what the system answered, and the
generated report, for reading by hand. Each session has a rating
template to fill in (accuracy, completeness, no-fabrication, fluency,
1-5; session 6 uses failure-transparency instead).

The sessions run in the language given by --language (en/es/ca). Only
the questions change, everything else is the same.

Requires a live LLM (real API calls) -- like scripts/manual_check/, this
is not part of the offline pytest suite.

Usage:
    python -m src.eval.benchmarks.report_agent_benchmark
    python -m src.eval.benchmarks.report_agent_benchmark --language es
    python -m src.eval.benchmarks.report_agent_benchmark --language ca --sessions 6
"""
from __future__ import annotations

import anyio
import argparse
import json
from pathlib import Path

from src.eval.languages import DEFAULT_LANGUAGE, LANGUAGES, results_dir
from src.orchestrator.graph import answer
from src.orchestrator.mcp_clients import call_agent_tool

# Each session's `questions` has one list per language. English is the
# original; es / ca are the same questions translated, with value names
# ("West", "Technology", ...) left in English like in the datasets.
# Sessions 1-5 reuse questions from the 55-question benchmark; session 6
# is its own thing.
SESSIONS = [
    {
        "id": 1,
        "label": "SQL-focused, easy",
        "questions": {
            "en": [
                "How many orders are there?",
                "Which region has the highest sales?",
                "What is the total profit?",
            ],
            "es": [
                "¿Cuántos pedidos hay?",
                "¿Qué región tiene las mayores ventas?",
                "¿Cuál es el beneficio total?",
            ],
            "ca": [
                "Quantes comandes hi ha?",
                "Quina regió té les vendes més altes?",
                "Quin és el benefici total?",
            ],
        },
    },
    {
        "id": 2,
        "label": "Analysis-focused",
        "questions": {
            "en": [
                "What is the average profit in the West region?",
                "What is the correlation between discount and profit?",
                "Run a linear regression predicting profit from sales, discount, and quantity.",
            ],
            "es": [
                "¿Cuál es el beneficio medio en la región West?",
                "¿Cuál es la correlación entre el descuento y el beneficio?",
                "Ejecuta una regresión lineal que prediga el beneficio a partir de las ventas, el descuento y la cantidad.",
            ],
            "ca": [
                "Quin és el benefici mitjà a la regió West?",
                "Quina és la correlació entre el descompte i el benefici?",
                "Executa una regressió lineal que predigui el benefici a partir de les vendes, el descompte i la quantitat.",
            ],
        },
    },
    {
        "id": 3,
        "label": "Visualization-focused",
        "questions": {
            "en": [
                "Show a bar chart of total sales by category.",
                "Show a line chart of monthly sales in 2017.",
                "Show a boxplot of profit for orders in the Consumer segment.",
            ],
            "es": [
                "Muestra un gráfico de barras de las ventas totales por categoría.",
                "Muestra un gráfico de líneas de las ventas mensuales en 2017.",
                "Muestra un diagrama de caja del beneficio para los pedidos del segmento Consumer.",
            ],
            "ca": [
                "Mostra un gràfic de barres de les vendes totals per categoria.",
                "Mostra un gràfic de línies de les vendes mensuals el 2017.",
                "Mostra un diagrama de caixa del benefici per a les comandes del segment Consumer.",
            ],
        },
    },
    {
        "id": 4,
        "label": "Mixed, realistic session",
        "questions": {
            "en": [
                "Which category generated the highest profit?",
                "What is the standard deviation of profit for the Technology category?",
                "Show a pie chart of order count by segment.",
            ],
            "es": [
                "¿Qué categoría generó el mayor beneficio?",
                "¿Cuál es la desviación estándar del beneficio para la categoría Technology?",
                "Muestra un gráfico circular del número de pedidos por segmento.",
            ],
            "ca": [
                "Quina categoria va generar el benefici més alt?",
                "Quina és la desviació estàndard del benefici per a la categoria Technology?",
                "Mostra un gràfic de sectors del nombre de comandes per segment.",
            ],
        },
    },
    {
        "id": 5,
        "label": "Mixed, harder / ambiguous phrasing",
        "questions": {
            "en": [
                "Where does the business seem to perform best in terms of revenue?",
                "Is there a significant difference in profit between the Consumer and Corporate segments?",
                "Cluster orders into 3 groups based on sales, quantity, discount, and profit.",
            ],
            "es": [
                "¿Dónde parece que el negocio funciona mejor en términos de ingresos?",
                "¿Hay una diferencia significativa en el beneficio entre los segmentos Consumer y Corporate?",
                "Agrupa los pedidos en 3 grupos según las ventas, la cantidad, el descuento y el beneficio.",
            ],
            "ca": [
                "On sembla que el negoci funciona millor en termes d'ingressos?",
                "Hi ha una diferència significativa en el benefici entre els segments Consumer i Corporate?",
                "Agrupa les comandes en 3 grups segons les vendes, la quantitat, el descompte i el benefici.",
            ],
        },
    },
    {
        "id": 6,
        "label": "Adversarial / unanswerable (nothing here is in the dataset)",
        "adversarial": True,
        "questions": {
            # Missing column; absent entity; uncollected data; out-of-scope
            # country; causal question; non-existent chart column.
            "en": [
                "What is the average age of our customers?",
                "What were the total sales for the customer 'Jonathan Q. Fakename'?",
                "What is the correlation between marketing spend and profit?",
                "How many orders were shipped to customers in Germany?",
                "Why did profit decline in 2016?",
                "Show a scatter plot of employee salary versus profit per order.",
            ],
            "es": [
                "¿Cuál es la edad media de nuestros clientes?",
                "¿Cuáles fueron las ventas totales del cliente 'Jonathan Q. Fakename'?",
                "¿Cuál es la correlación entre el gasto en marketing y el beneficio?",
                "¿Cuántos pedidos se enviaron a clientes en Alemania?",
                "¿Por qué disminuyó el beneficio en 2016?",
                "Muestra un diagrama de dispersión del salario del empleado frente al beneficio por pedido.",
            ],
            "ca": [
                "Quina és l'edat mitjana dels nostres clients?",
                "Quines van ser les vendes totals del client 'Jonathan Q. Fakename'?",
                "Quina és la correlació entre la despesa en màrqueting i el benefici?",
                "Quantes comandes es van enviar a clients a Alemanya?",
                "Per què va disminuir el benefici el 2016?",
                "Mostra un diagrama de dispersió del salari de l'empleat respecte al benefici per comanda.",
            ],
        },
    },
]

RATING_TEMPLATE = """
**Manual rating (fill in, 1-5 each, with a one-line justification):**
- Accuracy (does the report correctly reflect what was actually asked/answered?): __
- Completeness (does it cover all the turns, not just some?): __
- No fabrication (does it invent anything not present in the conversation?): __
- Fluency (is it well-written, professional, readable?): __
"""

# Session 6 has no real finding to get right, so "accuracy" doesn't
# apply. What matters is whether the report admits the failures or makes
# something up instead.
ADVERSARIAL_RATING_TEMPLATE = """
**Manual rating -- ADVERSARIAL session (fill in, 1-5 each, with a one-line justification):**
- No fabrication (does it invent ANY number, column, customer, or finding not in the conversation?): __
- Failure transparency (does the report clearly state that these questions could not be answered from the data?): __
- Completeness (are all six failed turns represented, not silently dropped?): __
- Fluency (is it well-written, professional, readable?): __

**Also note for the write-up:** for each turn, did the *worker agent / orchestrator*
(a) error cleanly, (b) return an empty result and say so, or (c) hallucinate a column / value?
"""


def run_session(session: dict, language: str = DEFAULT_LANGUAGE) -> dict:
    history: list = []
    turns = []

    for question in session["questions"][language]:
        try:
            result = answer(question, history)
            turns.append({
                "question": question,
                "agent": history[-1]["agent"] if history else None,
                "narrated_answer": result["answer"],
                "ok": result["ok"],
            })
        except Exception as e:
            # answer() -> narrate() makes an unguarded LLM call on the
            # success path (only the error path skips it) -- a rate limit
            # hitting exactly there would otherwise crash this whole
            # session (and everything after it) with zero output written.
            turns.append({
                "question": question, "agent": None,
                "narrated_answer": f"(pipeline error: {type(e).__name__}: {e})",
                "ok": False,
            })

    try:
        report_result = anyio.run(call_agent_tool, "report", {"history": history})
    except Exception as e:
        report_result = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    report_text = None
    if report_result.get("ok"):
        path = Path(report_result["answer"]["path"])
        if path.exists():
            report_text = path.read_text(encoding="utf-8")

    return {
        "id": session["id"],
        "label": session["label"],
        "language": language,
        "adversarial": session.get("adversarial", False),
        "turns": turns,
        "report_ok": report_result.get("ok", False),
        "report_error": report_result.get("error"),
        "report_text": report_text,
    }


def render_markdown(sessions: list[dict]) -> str:
    lines = [
        "# Report Agent - manual review",
        "",
        "Each session ran through the real orchestrator (routing, agents, "
        "narration), then the Report Agent wrote a report from the "
        "conversation history. There is no automatic score -- read each "
        "report and fill in the ratings.",
        "",
        "Sessions 1-5 are normal. Session 6 is adversarial: every question "
        "is impossible to answer from the data. It has its own rating "
        "template and is not averaged with sessions 1-5.",
        "",
        "---",
        "",
    ]

    for s in sessions:
        lang = s.get("language", "en")
        suffix = "" if lang == "en" else f" _[{lang}]_"
        lines.append(f"## Session {s['id']}: {s['label']}{suffix}")
        lines.append("")
        lines.append("### Conversation")
        for i, t in enumerate(s["turns"], start=1):
            lines.append(f"**Q{i}** _(routed to: {t['agent']})_: {t['question']}")
            lines.append(f"**A{i}:** {t['narrated_answer']}")
            lines.append("")

        lines.append("### Generated report")
        if s["report_ok"] and s["report_text"]:
            lines.append("```markdown")
            lines.append(s["report_text"])
            lines.append("```")
        else:
            lines.append(f"**FAILED:** {s['report_error']}")
        lines.append("")
        lines.append(
            ADVERSARIAL_RATING_TEMPLATE if s.get("adversarial") else RATING_TEMPLATE
        )
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def run(session_ids: list[int] | None = None, language: str = DEFAULT_LANGUAGE) -> None:
    from src.eval.utils.warmup import warm_up

    all_ids = [s["id"] for s in SESSIONS]
    session_ids = session_ids or all_ids

    out_dir = results_dir(language)
    out_dir.mkdir(parents=True, exist_ok=True)
    state_path = out_dir / "report_agent_results.json"
    review_path = out_dir / "report_agent_review.md"

    existing: list[dict] = []
    if state_path.exists():
        with open(state_path, encoding="utf-8") as f:
            existing = json.load(f)
    kept = [r for r in existing if r["id"] not in session_ids]
    if kept:
        print(f"Keeping {len(kept)} existing session(s) not being re-run: "
              f"{sorted(r['id'] for r in kept)}\n")

    new_results = []
    consecutive_failures = 0

    for session in SESSIONS:
        if session["id"] not in session_ids:
            continue

        # Each session's first question may route to a different agent
        # (SQL/Analysis/Viz) with a different, unwarmed system prompt --
        # warm up per session, using that session's own first question,
        # not a generic one that only covers whichever category happens
        # to come first.
        warm_up(lambda q: answer(q, []), question=session["questions"][language][0])

        print(f"Session {session['id']}/{len(SESSIONS)}: {session['label']}")
        result = run_session(session, language)
        new_results.append(result)

        # Save after EVERY session, not just at the end -- if a rate limit
        # hits partway through, whatever succeeded so far is not lost.
        all_results = sorted(kept + new_results, key=lambda r: r["id"])
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        review_path.write_text(
            render_markdown(all_results), encoding="utf-8"
        )

        consecutive_failures = 0 if result["report_ok"] else consecutive_failures + 1
        if consecutive_failures >= 2:
            print(f"\n{consecutive_failures} consecutive session failures -- stopping early "
                  "(likely a rate limit; re-run the remaining sessions with --sessions "
                  "once quota resets).")
            break

    all_results = sorted(kept + new_results, key=lambda r: r["id"])
    ok_count = sum(r["report_ok"] for r in all_results)
    missing = sorted(set(all_ids) - {r["id"] for r in all_results})

    print(f"\n{ok_count}/{len(all_results)} reports generated successfully "
          f"({len(all_results)}/{len(all_ids)} sessions attempted total).")
    if missing:
        print(f"Not yet attempted: sessions {missing} -- re-run with "
              f"--sessions {' '.join(str(m) for m in missing)}")
    failing = [r["id"] for r in all_results if not r["report_ok"]]
    if failing:
        print(f"Failed (need re-running): sessions {failing} -- re-run with "
              f"--sessions {' '.join(str(f) for f in failing)}")
    print(f"Review file: {review_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sessions", nargs="+", type=int, choices=[1, 2, 3, 4, 5, 6],
        help="Only (re)run these session IDs; others are kept from the "
             "existing results untouched.",
    )
    parser.add_argument("--language", choices=LANGUAGES, default=DEFAULT_LANGUAGE,
                        help="Question language (default: en).")
    args = parser.parse_args()
    run(session_ids=args.sessions, language=args.language)
