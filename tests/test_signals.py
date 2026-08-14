"""Checks on the options-free "big move" signals.

The interesting property is the one in
`test_fixed_percentage_selects_on_volatility_but_sigma_does_not`: a fixed
percentage threshold is not a neutral filter, it is a volatility screen wearing
a disguise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pead.data import EarningsEvent, read_price_csv
from pead.eventstudy import MIN_PRIOR_EVENTS, run_event_study


def noisy_series(daily_vol: float, n: int = 400, seed: int = 0) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-02", periods=n)
    stock = pd.Series(100 * np.cumprod(1 + rng.normal(0, daily_vol, n)), index=dates)
    market = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.008, n)), index=dates)
    return stock, market


def jump(prices: pd.Series, day: pd.Timestamp, size: float) -> pd.Series:
    factors = np.ones(len(prices))
    factors[prices.index.get_loc(day) :] = 1 + size
    return pd.Series(prices.to_numpy() * factors, index=prices.index)


def event_on(day: pd.Timestamp, ticker: str = "X", quarter: str = "Q1") -> EarningsEvent:
    return EarningsEvent(ticker, quarter, day, "amc")


def test_fixed_percentage_selects_on_volatility_but_sigma_does_not():
    """The same 10% move is routine for one stock and extraordinary for another.

    abs_move fires on both, so a fixed threshold across a universe quietly
    selects high-volatility names. sigma_move separates them.
    """
    announce = pd.Timestamp("2024-09-02")
    event_day = pd.Timestamp("2024-09-03")

    calm, market = noisy_series(0.01, seed=1)
    wild, _ = noisy_series(0.05, seed=2)
    calm = jump(calm, event_day, 0.10)
    wild = jump(wild, event_day, 0.10)

    (calm_res,) = run_event_study([event_on(announce)], calm, market, horizons=(21,))
    (wild_res,) = run_event_study([event_on(announce)], wild, market, horizons=(21,))

    # Identical raw move, so the fixed-percentage filter cannot tell them apart.
    assert calm_res.signal("abs_move", 0.10) == 1
    assert wild_res.signal("abs_move", 0.10) == 1

    # Scaled by each stock's own volatility, only one is a genuine surprise.
    assert calm_res.sigma_multiple > wild_res.sigma_multiple * 2
    assert calm_res.signal("sigma_move", 3.0) == 1
    assert wild_res.signal("sigma_move", 3.0) == 0


def test_abs_move_respects_its_threshold_and_direction():
    announce = pd.Timestamp("2024-09-02")
    day = pd.Timestamp("2024-09-03")
    stock, market = noisy_series(0.01, seed=3)
    stock = jump(stock, day, -0.15)

    (result,) = run_event_study([event_on(announce)], stock, market, horizons=(21,))
    # The injected jump compounds with that session's own noise, so the
    # realized move lands near -15% rather than exactly on it.
    assert result.announcement_raw == pytest.approx(-0.15, abs=0.02)
    assert result.signal("abs_move", 0.10) == -1  # short, with the move
    assert result.signal("abs_move", 0.20) == 0  # below threshold, no trade


def test_sigma_move_is_none_without_enough_history():
    """An event too early in the series has no volatility window to scale by."""
    stock, market = noisy_series(0.02, n=60, seed=4)
    announce = stock.index[2]
    (result,) = run_event_study([event_on(announce)], stock, market, horizons=(5,))
    assert result.trailing_vol is None
    assert result.sigma_multiple is None
    assert result.signal("sigma_move") is None


def _quarterly_events(stock: pd.Series, n: int) -> list[EarningsEvent]:
    days = stock.index[80::40][:n]
    return [event_on(d, quarter=f"Q{i + 1}") for i, d in enumerate(days)]


def test_earnings_vol_proxy_needs_a_burn_in():
    """The first few events have no prior earnings moves to average."""
    stock, market = noisy_series(0.02, seed=5)
    events = _quarterly_events(stock, 6)
    results = run_event_study(events, stock, market, horizons=(21,))

    for early in results[:MIN_PRIOR_EVENTS]:
        assert early.expected_move_proxy is None
        assert early.signal("earnings_vol_move") is None
    for later in results[MIN_PRIOR_EVENTS:]:
        assert later.expected_move_proxy is not None


def test_earnings_vol_proxy_does_not_look_ahead():
    """Event k's expected move must average only events before it.

    A huge move on the *last* event must not change the proxy used by any
    earlier one. This is the failure that would make the signal look
    prescient in backtest and useless live.
    """
    stock, market = noisy_series(0.02, seed=6)
    events = _quarterly_events(stock, 6)

    baseline = run_event_study(events, stock, market, horizons=(21,))
    proxies = [r.expected_move_proxy for r in baseline]

    # Inject a massive move on the final event only.
    spiked = jump(stock, baseline[-1].event_day, 0.60)
    after = run_event_study(events, spiked, market, horizons=(21,))

    for before, later in zip(proxies[:-1], [r.expected_move_proxy for r in after][:-1]):
        if before is None:
            assert later is None
        else:
            assert later == pytest.approx(before, abs=1e-9)


def test_earnings_vol_proxy_averages_prior_absolute_moves():
    stock, market = noisy_series(0.02, seed=7)
    events = _quarterly_events(stock, 5)
    results = run_event_study(events, stock, market, horizons=(21,))

    expected = float(np.mean([abs(r.announcement_raw) for r in results[:MIN_PRIOR_EVENTS]]))
    assert results[MIN_PRIOR_EVENTS].expected_move_proxy == pytest.approx(expected, abs=1e-12)


def test_reads_a_yahoo_finance_csv_and_prefers_adjusted_close(tmp_path):
    """Yahoo's export must work unmodified, using Adj Close over Close."""
    path = tmp_path / "AAA.csv"
    path.write_text(
        "Date,Open,High,Low,Close,Adj Close,Volume\n"
        "2025-01-02,10.0,11.0,9.5,10.5,5.25,1000\n"
        "2025-01-03,10.5,12.0,10.0,11.5,5.75,1200\n"
    )
    series = read_price_csv(str(path))
    assert list(series) == [5.25, 5.75]  # adjusted, not raw close
    assert series.index[0] == pd.Timestamp("2025-01-02")


def test_reads_a_plain_date_close_csv_with_currency_formatting(tmp_path):
    path = tmp_path / "BBB.csv"
    path.write_text('date,close\n2025-01-02,"$1,234.50"\n2025-01-03,"$1,240.00"\n')
    series = read_price_csv(str(path))
    assert series.iloc[0] == pytest.approx(1234.50)


def test_price_csv_rows_are_deduplicated_and_sorted(tmp_path):
    path = tmp_path / "CCC.csv"
    path.write_text(
        "date,close\n2025-01-03,11\n2025-01-02,10\n2025-01-03,11\n2025-01-06,bad\n"
    )
    series = read_price_csv(str(path))
    assert list(series.index) == [pd.Timestamp("2025-01-02"), pd.Timestamp("2025-01-03")]
