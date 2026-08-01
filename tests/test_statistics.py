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


# --- compute_ttest: group comparison, not column-vs-column -----------------

def _group_df():
    import pandas as pd
    return pd.DataFrame({
        "segment": ["A", "A", "A", "A", "B", "B", "B", "B"],
        "value": [10, 12, 11, 9, 20, 22, 21, 19],
    })


def test_ttest_compares_two_groups_correctly():
    from src.agents.analysis.statistics import compute_ttest
    result = compute_ttest(_group_df(), group_column="segment", group_values=["A", "B"])
    r = result["result"]
    assert r["group_a"] == "A"
    assert r["group_b"] == "B"
    assert r["group_a_mean"] == 10.5
    assert r["group_b_mean"] == 20.5
    # groups are clearly different -> small p-value
    assert r["p_value"] < 0.01


def test_ttest_requires_group_column_and_values():
    import pytest
    from src.agents.analysis.statistics import compute_ttest
    with pytest.raises(ValueError):
        compute_ttest(_group_df())


def test_ttest_unknown_group_column_raises():
    import pytest
    from src.agents.analysis.statistics import compute_ttest
    with pytest.raises(ValueError):
        compute_ttest(_group_df(), group_column="not_a_column", group_values=["A", "B"])


def test_ttest_insufficient_group_data_raises():
    import pytest
    import pandas as pd
    from src.agents.analysis.statistics import compute_ttest
    df = pd.DataFrame({"segment": ["A", "A", "B"], "value": [1, 2, 3]})
    with pytest.raises(ValueError):
        compute_ttest(df, group_column="segment", group_values=["A", "B"])  # B has only 1 row
