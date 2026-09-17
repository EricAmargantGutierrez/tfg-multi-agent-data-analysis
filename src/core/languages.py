"""
src/core/languages.py

The three language codes this project supports, shared by the eval
harness (src/eval/languages.py, which knows the language for certain)
and any agent that needs to name a language back to an LLM (currently
just the Report Agent). Kept here, not in src/eval, so an agent doesn't
have to depend on eval-only code to use it.
"""
from __future__ import annotations

LANGUAGES: tuple[str, ...] = ("en", "es", "ca")

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "ca": "Catalan",
}

DEFAULT_LANGUAGE = "en"
