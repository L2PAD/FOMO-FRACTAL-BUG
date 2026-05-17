"""
Replay Universe Builder
========================
Determines which dates / horizons / assets to replay.
Only dates where outcome is fully evaluable are included.
"""

from datetime import datetime, timedelta, timezone

HORIZON_DAYS = {"24H": 1, "7D": 7, "30D": 30}


def build_replay_jobs(
    asset: str,
    horizon: str,
    start_date: str,
    end_date: str,
    prices: dict[str, float],
) -> list[dict]:
    """
    Build list of replay jobs for the given window.
    Only includes dates where:
      - enough price history exists (30+ days before as_of)
      - outcome date has price data (as_of + horizon_days)
    """
    horizon_days = HORIZON_DAYS.get(horizon, 7)
    all_dates = sorted(prices.keys())

    if not all_dates:
        return []

    latest_outcome_date = all_dates[-1]
    jobs = []

    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end:
        as_of_str = current.strftime("%Y-%m-%d")
        outcome_date = (current + timedelta(days=horizon_days)).strftime("%Y-%m-%d")

        # Must have outcome date in price data
        if outcome_date > latest_outcome_date:
            current += timedelta(days=1)
            continue

        # Must have 30+ days of price history before as_of
        prior_dates = [d for d in all_dates if d <= as_of_str]
        if len(prior_dates) < 14:
            current += timedelta(days=1)
            continue

        jobs.append({
            "asset": asset,
            "horizon": horizon,
            "horizon_days": horizon_days,
            "as_of": as_of_str,
            "outcome_date": outcome_date,
        })

        current += timedelta(days=1)

    return jobs
