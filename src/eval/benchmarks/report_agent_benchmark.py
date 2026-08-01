"""
src/eval/benchmarks/report_agent_benchmark.py

The Report Agent has no ground truth to score against -- a session
summary has no single "correct" answer, so unlike the other three agents
this is evaluated qualitatively, not automatically (per the original
proposal).

Unlike the other benchmarks, this doesn't test single questions: the
Report Agent's real unit of work is a whole SESSION (a sequence of Q&A
turns), so this runs 5 curated sessions -- each a handful of questions
spanning SQL/Analysis/Visualization and easy-to-hard phrasing -- through
the REAL orchestrator end-to-end (routing, agent execution, narration,
history accumulation), then generates a real report for each session.

Output: results/eval/report_agent_review.md -- one file with every
session's questions, what the system actually answered, and the
generated report, laid out for manual reading with a rating template
ready to fill in (accuracy, completeness, no-fabrication, fluency, 1-5).

Requires a live LLM (real API calls) -- like scripts/manual_check/, this
is not part of the offline pytest suite.

Usage: python -m src.eval.benchmarks.report_agent_benchmark
"""
from __future__ import annotations

import anyio
import argparse
import json
from pathlib import Path

from src.orchestrator.graph import answer
from src.orchestrator.mcp_clients import call_agent_tool

SESSIONS = [
    {
        "id": 1,
        "label": "SQL-focused, easy",
        "questions": [
            "How many orders are there?",
            "Which region has the highest sales?",
            "What is the total profit?",
        ],
    },
    {
        "id": 2,
        "label": "Analysis-focused",
        "questions": [
            "What is the average profit in the West region?",
            "What is the correlation between discount and profit?",
            "Run a linear regression predicting profit from sales, discount, and quantity.",
        ],
    },
    {
        "id": 3,
        "label": "Visualization-focused",
        "questions": [
            "Show a bar chart of total sales by category.",
            "Show a line chart of monthly sales in 2017.",
            "Show a boxplot of profit for orders in the Consumer segment.",
        ],
    },
    {
        "id": 4,
        "label": "Mixed, realistic session",
        "questions": [
            "Which category generated the highest profit?",
            "What is the standard deviation of profit for the Technology category?",
            "Show a pie chart of order count by segment.",
        ],
    },
    {
        "id": 5,
        "label": "Mixed, harder / ambiguous phrasing",
        "questions": [
            "Where does the business seem to perform best in terms of revenue?",
            "Is there a significant difference in profit between the Consumer and Corporate segments?",
            "Cluster orders into 3 groups based on sales, quantity, discount, and profit.",
        ],
    },
]

RATING_TEMPLATE = """
**Manual rating (fill in, 1-5 each, with a one-line justification):**
- Accuracy (does the report correctly reflect what was actually asked/answered?): __
- Completeness (does it cover all the turns, not just some?): __
- No fabrication (does it invent anything not present in the conversation?): __
- Fluency (is it well-written, professional, readable?): __
"""


def run_session(session: dict) -> dict:
    history: list = []
    turns = []

    for question in session["questions"]:
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
        "turns": turns,
        "report_ok": report_result.get("ok", False),
        "report_error": report_result.get("error"),
        "report_text": report_text,
    }


def render_markdown(sessions: list[dict]) -> str:
    lines = [
        "# Report Agent — Manual Qualitative Review",
        "",
        "Each session below ran through the real orchestrator end-to-end "
        "(routing, agent execution, narration), then the Report Agent "
        "generated a real summary from the accumulated history. No "
        "automated scoring -- read each report and fill in the rating "
        "template.",
        "",
        "---",
        "",
    ]

    for s in sessions:
        lines.append(f"## Session {s['id']}: {s['label']}")
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
        lines.append(RATING_TEMPLATE)
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def run(session_ids: list[int] | None = None) -> None:
    from src.eval.utils.warmup import warm_up

    all_ids = [s["id"] for s in SESSIONS]
    session_ids = session_ids or all_ids

    Path("results/eval").mkdir(parents=True, exist_ok=True)
    state_path = Path("results/eval/report_agent_results.json")

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
        warm_up(lambda q: answer(q, []), question=session["questions"][0])

        print(f"Session {session['id']}/{len(SESSIONS)}: {session['label']}")
        result = run_session(session)
        new_results.append(result)

        # Save after EVERY session, not just at the end -- if a rate limit
        # hits partway through, whatever succeeded so far is not lost.
        all_results = sorted(kept + new_results, key=lambda r: r["id"])
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        Path("results/eval/report_agent_review.md").write_text(
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
    print(f"Review file: results/eval/report_agent_review.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sessions", nargs="+", type=int, choices=[1, 2, 3, 4, 5],
        help="Only (re)run these session IDs; others are kept from the "
             "existing results untouched.",
    )
    args = parser.parse_args()
    run(session_ids=args.sessions)
