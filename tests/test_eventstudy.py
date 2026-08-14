"""Synthetic checks on the event-study mechanics.

The point of these is alignment: that the announcement session is identified
correctly for AMC vs BMO releases, that it is excluded from the drift window,
and that a known injected drift is recovered at the right magnitude.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pead.data import EarningsEvent
from pead.eventstudy import run_event_study, summarize


def build_series(n_days: int = 400, seed: int = 0) -> tuple[pd.Series, pd.Series]:
    """Flat stock and benchmark on business days, so any CAR is injected."""
    dates = pd.bdate_range("2025-01-02", periods=n_days)
    flat = pd.Series(100.0, index=dates)
    return flat.copy(), flat.copy()


def inject(prices: pd.Series, start: pd.Timestamp, days: int, daily_pct: float) -> pd.Series:
    """Apply `daily_pct` per day for `days` sessions starting at `start`."""
    out = prices.copy()
    idx = out.index.get_loc(start)
    factors = np.ones(len(out))
    factors[idx : idx + days] = 1 + daily_pct
    return pd.Series(out.to_numpy() * np.cumprod(factors), index=out.index)


def test_amc_event_prices_on_the_next_session():
    stock, market = build_series()
    announce = pd.Timestamp("2025-06-10")  # a Tuesday
    event = EarningsEvent("X", "Q1", announce, "amc")
    stock = inject(stock, pd.Timestamp("2025-06-11"), 1, 0.10)

    (result,) = run_event_study([event], stock, market, horizons=(5,))
    assert result.event_day == pd.Timestamp("2025-06-11")
    assert result.announcement_ar == pytest.approx(0.10, abs=1e-9)


def test_bmo_event_prices_on_the_same_session():
    stock, market = build_series()
    announce = pd.Timestamp("2025-06-10")
    event = EarningsEvent("X", "Q1", announce, "bmo")
    stock = inject(stock, announce, 1, 0.08)

    (result,) = run_event_study([event], stock, market, horizons=(5,))
    assert result.event_day == announce
    assert result.announcement_ar == pytest.approx(0.08, abs=1e-9)


def test_announcement_move_is_excluded_from_drift():
    """A one-day pop with nothing after it must show zero drift."""
    stock, market = build_series()
    announce = pd.Timestamp("2025-06-10")
    event = EarningsEvent("X", "Q1", announce, "amc")
    stock = inject(stock, pd.Timestamp("2025-06-11"), 1, 0.25)

    (result,) = run_event_study([event], stock, market, horizons=(1, 5, 10))
    assert result.announcement_ar == pytest.approx(0.25, abs=1e-9)
    for horizon in (1, 5, 10):
        assert result.drift[horizon] == pytest.approx(0.0, abs=1e-9)


def test_injected_drift_is_recovered():
    """0.5%/day for the 10 sessions after the event -> CAR(+10d) ~ 5%."""
    stock, market = build_series()
    announce = pd.Timestamp("2025-06-10")
    event = EarningsEvent("X", "Q1", announce, "amc")
    stock = inject(stock, pd.Timestamp("2025-06-12"), 10, 0.005)

    (result,) = run_event_study([event], stock, market, horizons=(10,))
    assert result.drift[10] == pytest.approx(0.05, abs=1e-6)


def test_market_move_is_netted_out():
    """Stock and benchmark moving together is not drift."""
    stock, market = build_series()
    announce = pd.Timestamp("2025-06-10")
    event = EarningsEvent("X", "Q1", announce, "amc")
    start = pd.Timestamp("2025-06-12")
    stock = inject(stock, start, 10, 0.01)
    market = inject(market, start, 10, 0.01)

    (result,) = run_event_study([event], stock, market, horizons=(10,))
    assert result.drift[10] == pytest.approx(0.0, abs=1e-6)
    assert result.raw_drift[10] == pytest.approx(1.01**10 - 1, abs=1e-6)


def test_signed_summary_flips_on_a_negative_signal():
    """A down-reaction followed by further decline is positive signed drift."""
    stock, market = build_series()
    announce = pd.Timestamp("2025-06-10")
    event = EarningsEvent("X", "Q1", announce, "amc")
    stock = inject(stock, pd.Timestamp("2025-06-11"), 1, -0.20)
    stock = inject(stock, pd.Timestamp("2025-06-12"), 10, -0.005)

    results = run_event_study([event], stock, market, horizons=(10,))
    assert results[0].announcement_ar < 0
    assert results[0].drift[10] < 0

    table = summarize(results, "reaction", (10,))
    assert table.loc[0, "mean_signed_car"] > 0  # drift continued with the signal
    assert table.loc[0, "hit_rate"] == 1.0


def test_market_model_estimates_beta_and_nets_out_high_beta_moves():
    """A 2x-beta stock with a noisy benchmark: beta is recovered, drift is ~0."""
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2025-01-02", periods=400)
    market_ret = rng.normal(0.0, 0.01, len(dates))
    stock_ret = 2.0 * market_ret  # no idiosyncratic component

    market = pd.Series(100 * np.cumprod(1 + market_ret), index=dates)
    stock = pd.Series(100 * np.cumprod(1 + stock_ret), index=dates)

    announce = pd.Timestamp("2025-11-10")
    event = EarningsEvent("X", "Q1", announce, "amc")
    (result,) = run_event_study([event], stock, market, horizons=(10,))

    assert "market model" in result.beta_source
    assert result.beta == pytest.approx(2.0, abs=0.05)
    # All of this stock's movement is explained by the benchmark.
    assert result.drift[10] == pytest.approx(0.0, abs=5e-3)


def test_revenue_surprise_sign_and_negative_eps_convention():
    event = EarningsEvent(
        "X", "Q1", pd.Timestamp("2025-06-10"), "amc",
        revenue_actual=1360.0, revenue_consensus=1290.0,
        eps_actual=-1.03, eps_consensus=-1.24,
    )
    assert event.revenue_surprise_pct == pytest.approx(0.05426, abs=1e-4)
    # A smaller loss than feared is a positive surprise.
    assert event.eps_surprise_pct > 0

    worse = EarningsEvent(
        "X", "Q2", pd.Timestamp("2025-06-10"), "amc",
        eps_actual=-1.40, eps_consensus=-0.91,
    )
    assert worse.eps_surprise_pct < 0
