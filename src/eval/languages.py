"""
src/eval/languages.py

The evaluation can run in three languages. Only the questions are
translated -- reference SQL and ground truth stay the same, since it's
the same database and expected answer either way.

Each dataset item's "question" is a dict with one entry per language
({"en": ..., "es": ..., "ca": ...}); question_text() picks the right one.
Data values ("West", "Technology", ...) stay in English in every
language, so this tests handling the question's language, not
translating stored values.

Results are saved under results/eval/<model>/<language>/, so a
different TFG_MODEL writes to its own folder instead of overwriting.

LANGUAGES/LANGUAGE_NAMES/DEFAULT_LANGUAGE live in src/core/languages.py,
not here, so an agent (Report) can use them without depending on eval
code; re-exported here so existing benchmark imports don't change.
"""
from __future__ import annotations

from pathlib import Path

from src.config.settings import settings
from src.core.languages import DEFAULT_LANGUAGE, LANGUAGE_NAMES, LANGUAGES

__all__ = [
    "DEFAULT_LANGUAGE", "LANGUAGE_NAMES", "LANGUAGES",
    "question_text", "results_dir",
]


def question_text(item: dict, language: str = DEFAULT_LANGUAGE) -> str:
    """Get the question string for a language from a dataset item."""
    question = item["question"]
    if isinstance(question, str):
        return question
    return question[language]


def results_dir(language: str = DEFAULT_LANGUAGE) -> Path:
    """Output folder for one model + language, e.g. results/eval/anthropic/en."""
    return Path("results/eval") / settings.default_model / language
