"""
src/eval/languages.py

The evaluation can run in three languages. Only the questions are
translated. The reference SQL and the ground truth stay the same in every
language (same database, same expected answer), so each dataset file
keeps one copy of them.

In the dataset files, each item's "question" is a dict with one entry per
language, like {"en": "...", "es": "...", "ca": "..."}. question_text()
picks the right one (and still works if it's just a plain string).

Names that are actual values in the data -- "West", "Technology",
"Consumer", "Second Class" -- are left in English in all three languages.
That way we test how the system handles the language of the question, not
the separate problem of translating a value name back to what's stored.

Results are saved under results/eval/<model>/<language>/, where <model>
is the current TFG_MODEL (e.g. "anthropic", "ollama"). So running a
different model writes to its own folder instead of overwriting.
"""
from __future__ import annotations

from pathlib import Path

from src.config.settings import settings

LANGUAGES: tuple[str, ...] = ("en", "es", "ca")

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "ca": "Catalan",
}

DEFAULT_LANGUAGE = "en"


def question_text(item: dict, language: str = DEFAULT_LANGUAGE) -> str:
    """Get the question string for a language from a dataset item."""
    question = item["question"]
    if isinstance(question, str):
        return question
    return question[language]


def results_dir(language: str = DEFAULT_LANGUAGE) -> Path:
    """Output folder for one model + language, e.g. results/eval/anthropic/en."""
    return Path("results/eval") / settings.default_model / language
