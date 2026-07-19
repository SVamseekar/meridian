from data.generator.correlations import (
    churn_probability,
    daily_feature_depth,
    daily_login_frequency,
    daily_search_volume,
    funnel_stage_duration_days,
    select_churning_account_ids,
    usage_volume_multiplier,
)


def test_churn_probability_is_inverse_to_feature_depth():
    low_depth_churn = churn_probability(feature_depth=1.0)
    high_depth_churn = churn_probability(feature_depth=10.0)
    assert low_depth_churn > high_depth_churn


def test_daily_feature_depth_declines_over_churn_window_when_churning():
    early = daily_feature_depth(base=8.0, day_index=0, is_churning=True)
    late = daily_feature_depth(base=8.0, day_index=75, is_churning=True)
    assert late < early


def test_daily_feature_depth_stable_when_not_churning():
    early = daily_feature_depth(base=8.0, day_index=0, is_churning=False)
    late = daily_feature_depth(base=8.0, day_index=75, is_churning=False)
    assert abs(late - early) < early * 0.5  # allowed to vary, must not collapse toward zero


def test_daily_search_volume_declines_over_churn_window_when_churning():
    early = daily_search_volume(base=50.0, day_index=0, firm_type="boutique", is_churning=True)
    late = daily_search_volume(base=50.0, day_index=75, firm_type="boutique", is_churning=True)
    assert late < early


def test_daily_search_volume_varies_by_firm_type():
    boutique = daily_search_volume(base=50.0, day_index=10, firm_type="boutique", is_churning=False)
    enterprise = daily_search_volume(base=50.0, day_index=10, firm_type="enterprise", is_churning=False)
    assert boutique != enterprise


def test_daily_login_frequency_declines_over_churn_window_when_churning():
    early = daily_login_frequency(base=5.0, day_index=0, is_churning=True)
    late = daily_login_frequency(base=5.0, day_index=75, is_churning=True)
    assert late < early


def test_usage_volume_scales_with_contract_value():
    low_value = usage_volume_multiplier(contract_value=10_000, activity_level=1.0)
    high_value = usage_volume_multiplier(contract_value=200_000, activity_level=1.0)
    assert high_value > low_value


def test_funnel_stage_duration_is_longer_for_low_feature_usage_index():
    low_usage_duration = funnel_stage_duration_days(feature_usage_index=0.1)
    high_usage_duration = funnel_stage_duration_days(feature_usage_index=0.9)
    assert low_usage_duration > high_usage_duration


def test_select_churning_account_ids_is_8_to_12_percent():
    account_ids = list(range(100))
    churning = select_churning_account_ids(account_ids, seed=42)
    assert 8 <= len(churning) <= 12
    assert churning.issubset(set(account_ids))


def test_select_churning_account_ids_is_deterministic_for_same_seed():
    account_ids = list(range(100))
    first = select_churning_account_ids(account_ids, seed=42)
    second = select_churning_account_ids(account_ids, seed=42)
    assert first == second
