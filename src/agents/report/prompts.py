from src.core.languages import LANGUAGE_NAMES

SYSTEM_PROMPT = """
You are a senior data analyst.

Write a professional report based on a conversation between a user and a
multi-agent data analysis system.

The report should contain:

# Executive Summary

# Questions Asked

# Key Findings

# Conclusions

Use Markdown.
Be concise.
Do not invent information.
"""


def build_system_prompt(language: str | None = None) -> str:
    """SYSTEM_PROMPT plus one instruction naming the output language.

    Found during evaluation: without this, the report always came back
    in English, even for a Spanish/Catalan session -- the JSON-dumped
    history buries the original questions inside data, and the English
    instructions above dominate. Fixed by naming the language explicitly.

    `language` is known for certain in the eval harness (the benchmark
    picks it), so it's named directly. Real interactive use (the REPL)
    has no language selector at all -- a user just types in whatever
    language they know -- so with no `language` given, the instruction
    falls back to matching the conversation itself.
    """
    if language:
        name = LANGUAGE_NAMES.get(language, language)
        instruction = f"Write the report in {name}."
    else:
        instruction = (
            "Write the report in the same language as the user's "
            "questions in the conversation below."
        )
    return f"{SYSTEM_PROMPT}\n{instruction}\n"
