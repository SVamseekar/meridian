import random

CHURN_WINDOW_DAYS = 75  # within D03's 60-90 day range
CHURN_RATE_MIN = 0.08
CHURN_RATE_MAX = 0.12

FIRM_TYPE_SEARCH_MULTIPLIER = {
    "boutique": 1.3,
    "midmarket": 1.0,
    "enterprise": 0.7,
}


def _churn_decay(day_index: int, is_churning: bool) -> float:
    """Returns a multiplier in (0, 1] that decays toward the end of the
    churn window when is_churning is True; 1.0 (no decay) otherwise."""
    if not is_churning:
        return 1.0
    progress = min(day_index / CHURN_WINDOW_DAYS, 1.0)
    return max(1.0 - progress, 0.05)


def daily_feature_depth(base: float, day_index: int, is_churning: bool) -> float:
    return base * _churn_decay(day_index, is_churning)


def daily_search_volume(base: float, day_index: int, firm_type: str, is_churning: bool) -> float:
    multiplier = FIRM_TYPE_SEARCH_MULTIPLIER.get(firm_type, 1.0)
    return base * multiplier * _churn_decay(day_index, is_churning)


def daily_login_frequency(base: float, day_index: int, is_churning: bool) -> float:
    return base * _churn_decay(day_index, is_churning)


def churn_probability(feature_depth: float) -> float:
    """Higher feature_depth -> lower churn_probability (Decision D03)."""
    return 1.0 / (1.0 + feature_depth)


def usage_volume_multiplier(contract_value: int, activity_level: float) -> float:
    """Usage volume scales with contract_value and activity level
    (Decision D03) — shaped for later use as a Prophet exogenous
    regressor input."""
    return (contract_value / 10_000) * activity_level


def funnel_stage_duration_days(feature_usage_index: float) -> int:
    """Low pre-opportunity feature_usage_index -> longer funnel stage
    duration (Decision D03). feature_usage_index in [0, 1]."""
    base_days = 30
    return int(base_days * (1.5 - feature_usage_index))


def select_churning_account_ids(account_ids: list, seed: int) -> set:
    """Deterministically selects 8-12% of the given account IDs (Decision
    D03), scoped to whatever list is passed in — callers pass one
    tenant's account IDs at a time for a true per-tenant churn rate."""
    rng = random.Random(seed)
    rate = rng.uniform(CHURN_RATE_MIN, CHURN_RATE_MAX)
    count = max(1, round(len(account_ids) * rate)) if account_ids else 0
    return set(rng.sample(account_ids, count)) if count <= len(account_ids) else set(account_ids)
