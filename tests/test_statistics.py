import pandas as pd

from src.agents.analysis.statistics import compute_regression


def _df():
    # y = 2*x1 + 3 exactly, x2 is noise-ish but irrelevant to the point:
    # what matters is which column becomes y.
    return pd.DataFrame({
        "x1": [1, 2, 3, 4, 5],
        "noise": [5, 1, 4, 2, 3],
        "y": [5, 7, 9, 11, 13],
    })


def test_regression_with_explicit_target_predicts_named_column():
    result = compute_regression(_df(), target="y")
    assert result["result"]["target"] == "y"
    assert set(result["result"]["predictors"]) == {"x1", "noise"}
    # y = 2*x1 + 3 is an exact linear relationship -> r2 should be ~1.0
    assert result["result"]["r2"] > 0.99


def test_regression_without_target_falls_back_to_last_column():
    # legacy behavior: last column in the DataFrame becomes y
    result = compute_regression(_df())
    assert result["result"]["target"] == "y"


def test_regression_target_changes_which_column_is_predicted():
    # predicting "noise" (not well explained by x1) should give a much
    # worse r2 than predicting "y" (which IS well explained by x1) --
    # this is the exact failure mode the target field fixes: picking the
    # wrong column silently gives a low-r2 "valid-looking" wrong answer.
    result_right = compute_regression(_df(), target="y")
    result_wrong = compute_regression(_df(), target="noise")
    assert result_right["result"]["r2"] > result_wrong["result"]["r2"]


def test_regression_unknown_target_raises():
    import pytest
    with pytest.raises(ValueError):
        compute_regression(_df(), target="not_a_real_column")
