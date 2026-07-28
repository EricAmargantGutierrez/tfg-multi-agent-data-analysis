import pytest

from src.core.llm_json import parse_llm_json


def test_parses_plain_json():
    assert parse_llm_json('{"agent": "sql"}') == {"agent": "sql"}


def test_strips_markdown_fences():
    text = '```json\n{"agent": "sql"}\n```'
    assert parse_llm_json(text) == {"agent": "sql"}


def test_rejects_invalid_json():
    with pytest.raises(ValueError):
        parse_llm_json("not json at all")


def test_rejects_non_object_json():
    with pytest.raises(ValueError):
        parse_llm_json("[1, 2, 3]")


def test_rejects_empty_content():
    with pytest.raises(ValueError):
        parse_llm_json(None)
