import pytest

from src.agents.safety import UnsafeSQLError, validate_sql_readonly


def test_allows_select():
    assert validate_sql_readonly("SELECT 1") == "SELECT 1"


def test_allows_with():
    sql = "WITH x AS (SELECT 1) SELECT * FROM x"
    assert validate_sql_readonly(sql) == sql


def test_rejects_non_select():
    with pytest.raises(UnsafeSQLError):
        validate_sql_readonly("UPDATE orders SET sales = 0")


@pytest.mark.parametrize("keyword", ["insert", "update", "delete", "drop", "alter",
                                      "create", "attach", "vacuum", "pragma"])
def test_rejects_forbidden_keywords(keyword):
    with pytest.raises(UnsafeSQLError):
        validate_sql_readonly(f"SELECT 1; {keyword} something")


def test_rejects_stacked_statements_even_without_forbidden_words():
    # Two harmless-looking SELECTs stacked together should still be
    # rejected by structure, not rely on a forbidden keyword happening
    # to appear in the second statement.
    with pytest.raises(UnsafeSQLError):
        validate_sql_readonly("SELECT 1; SELECT 2")


def test_strips_single_trailing_semicolon():
    assert validate_sql_readonly("SELECT 1;") == "SELECT 1"
