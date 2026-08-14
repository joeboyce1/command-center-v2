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


def _event_with_implied(implied: float) -> EarningsEvent:
    return EarningsEvent(
        "X", "Q1", pd.Timestamp("2025-06-10"), "amc", implied_move_pct=implied
    )


def test_excess_move_signal_fires_only_past_the_implied_move():
    """A 20% break of a 12% implied move trades; the same move vs 25% does not."""
    stock, market = build_series()
    stock = inject(stock, pd.Timestamp("2025-06-11"), 1, -0.20)

    (fires,) = run_event_study([_event_with_implied(0.12)], stock, market, horizons=(21,))
    assert fires.implied_multiple == pytest.approx(0.20 / 0.12, abs=1e-3)
    assert fires.signal("excess_move") == -1  # short, in the direction of the move

    (quiet,) = run_event_study([_event_with_implied(0.25)], stock, market, horizons=(21,))
    assert quiet.signal("excess_move") == 0  # inside the implied move, no trade


def test_excess_move_threshold_is_configurable():
    stock, market = build_series()
    stock = inject(stock, pd.Timestamp("2025-06-11"), 1, 0.18)
    (result,) = run_event_study([_event_with_implied(0.15)], stock, market, horizons=(21,))

    # The move is 1.2x the implied move. Exact-boundary thresholds are left
    # untested on purpose: 0.18/0.15 is 1.1999... in binary floating point, so
    # asserting behaviour exactly at the threshold would be testing float
    # representation rather than the signal.
    assert result.implied_multiple == pytest.approx(1.2, abs=1e-6)
    assert result.signal("excess_move", implied_threshold=1.0) == 1
    assert result.signal("excess_move", implied_threshold=1.15) == 1
    assert result.signal("excess_move", implied_threshold=1.5) == 0


def test_excess_move_uses_the_raw_move_not_the_abnormal_one():
    """The straddle prices the total move, so the filter must use raw returns."""
    stock, market = build_series()
    start = pd.Timestamp("2025-06-11")
    stock = inject(stock, start, 1, 0.20)
    market = inject(market, start, 1, 0.20)  # all of it is market-driven

    (result,) = run_event_study([_event_with_implied(0.12)], stock, market, horizons=(21,))
    assert result.announcement_raw == pytest.approx(0.20, abs=1e-9)
    assert result.announcement_ar == pytest.approx(0.0, abs=1e-9)
    # Fires on the raw 20% even though the abnormal move is zero.
    assert result.implied_multiple == pytest.approx(0.20 / 0.12, abs=1e-3)
    assert result.signal("excess_move") == 1


def test_excess_move_signal_is_none_without_an_implied_move():
    stock, market = build_series()
    stock = inject(stock, pd.Timestamp("2025-06-11"), 1, -0.20)
    event = EarningsEvent("X", "Q1", pd.Timestamp("2025-06-10"), "amc")
    (result,) = run_event_study([event], stock, market, horizons=(21,))
    assert result.implied_multiple is None
    assert result.signal("excess_move") is None


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
