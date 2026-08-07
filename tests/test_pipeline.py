"""Correctness tests. Run with: python -m pytest tests -q"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nfl_seasonality import analysis, backtest  # noqa: E402
from nfl_seasonality.config import FRONT_RUN, NFL_SEASON, OFF_SEASON  # noqa: E402
from nfl_seasonality.stats_tests import (  # noqa: E402
    benjamini_hochberg,
    bonferroni,
    mean_difference,
    newey_west_dummy,
    permutation_pvalue,
)
from nfl_seasonality.windows import (  # noqa: E402
    count_full_seasons,
    in_window,
    season_year,
)


# --------------------------------------------------------------------------
# Window definitions
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "date,expected",
    [
        ("2023-08-31", False),  # day before kickoff window opens
        ("2023-09-01", True),   # inclusive start
        ("2023-12-31", True),
        ("2024-01-15", True),   # playoffs
        ("2024-02-15", True),   # inclusive end (Super Bowl covered)
        ("2024-02-16", False),  # off-season begins
        ("2024-06-01", False),
    ],
)
def test_nfl_window_boundaries(date, expected):
    idx = pd.DatetimeIndex([date])
    assert bool(in_window(idx, NFL_SEASON).iloc[0]) is expected


def test_season_and_offseason_partition_the_year():
    """Every calendar day is in exactly one of in-season / off-season."""
    idx = pd.date_range("2023-01-01", "2024-12-31", freq="D")
    a = in_window(idx, NFL_SEASON).to_numpy()
    b = in_window(idx, OFF_SEASON).to_numpy()
    assert np.all(a ^ b), "windows must partition the calendar with no gap or overlap"


@pytest.mark.parametrize(
    "date,expected",
    [("2023-07-31", False), ("2023-08-01", True), ("2023-12-31", True), ("2024-01-01", False)],
)
def test_front_run_window(date, expected):
    assert bool(in_window(pd.DatetimeIndex([date]), FRONT_RUN).iloc[0]) is expected


def test_season_year_spans_new_year():
    """The Super Bowl belongs to the previous autumn's season."""
    idx = pd.DatetimeIndex(["2023-09-10", "2023-12-25", "2024-01-20", "2024-02-11"])
    assert season_year(idx).tolist() == [2023, 2023, 2023, 2023]


def test_count_full_seasons_ignores_partial():
    """A ticker that starts in December does not get credit for that season."""
    full = pd.bdate_range("2020-09-01", "2024-02-15")
    assert count_full_seasons(full) == 4
    late = pd.bdate_range("2023-12-15", "2024-02-15")
    assert count_full_seasons(late) == 0


# --------------------------------------------------------------------------
# Returns
# --------------------------------------------------------------------------

def test_daily_returns_skip_foreign_calendar_holes():
    """A gap in one column must not corrupt the next return of another."""
    idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-01-04"])
    prices = pd.DataFrame({"US": [100.0, np.nan, 110.0], "UK": [50.0, 51.0, 52.0]}, index=idx)
    out = analysis.daily_returns(prices)
    # US trades on the 2nd and 4th only: its return on the 4th is 100 -> 110.
    assert out.loc["2024-01-04", "US"] == pytest.approx(0.10)
    assert np.isnan(out.loc["2024-01-03", "US"])


def test_excess_is_difference_over_benchmark():
    idx = pd.bdate_range("2024-01-01", periods=5)
    returns = pd.DataFrame({"AAA": [0.02] * 5, "SPY": [0.01] * 5}, index=idx)
    exc = analysis.excess_daily_returns(returns, "SPY")
    assert "SPY" not in exc.columns
    assert exc["AAA"].to_numpy() == pytest.approx([0.01] * 5)


def test_monthly_returns_compound_within_month():
    idx = pd.bdate_range("2024-01-01", "2024-01-31")
    returns = pd.DataFrame({"AAA": [0.01] * len(idx)}, index=idx)
    monthly = analysis.monthly_returns(returns)
    assert monthly["AAA"].iloc[0] == pytest.approx(1.01 ** len(idx) - 1)


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------

def test_mean_difference_recovers_known_gap():
    values = np.concatenate([np.full(500, 0.003), np.full(500, 0.001)])
    mask = np.concatenate([np.ones(500, bool), np.zeros(500, bool)])
    md = mean_difference(values, mask)
    assert md.mean_in == pytest.approx(0.003)
    assert md.mean_out == pytest.approx(0.001)
    assert md.diff == pytest.approx(0.002)


def test_newey_west_recovers_ols_slope_and_flags_real_effect():
    rng = np.random.default_rng(0)
    dummy = np.tile([1.0, 0.0], 1000)
    y = 0.01 * dummy + rng.normal(0, 0.005, 2000)
    t, p = newey_west_dummy(y, dummy)
    assert t > 10 and p < 1e-6


def test_newey_west_is_calibrated_under_the_null():
    """On pure noise the HAC t must behave like a standard normal.

    Calibration across many draws, not one seed: a single draw legitimately
    lands past |t| = 2.5 about 1% of the time, so a one-seed test would be
    testing the seed rather than the estimator.
    """
    idx = pd.bdate_range("2010-01-01", "2024-12-31")
    dummy = in_window(idx, NFL_SEASON).to_numpy().astype(float)
    ts, ps = [], []
    for seed in range(200):
        rng = np.random.default_rng(2000 + seed)
        t, p = newey_west_dummy(rng.normal(0, 0.02, len(idx)), dummy)
        ts.append(t)
        ps.append(p)
    ts, ps = np.array(ts), np.array(ps)
    assert abs(ts.mean()) < 0.25, "HAC slope should be unbiased under the null"
    assert 0.8 < ts.std() < 1.25, "HAC t should have roughly unit variance"
    assert (ps < 0.05).mean() < 0.12, "rejection rate must stay near nominal"


def test_permutation_detects_a_strong_planted_season_effect():
    """Low-noise data with a real in-season drift must produce a small p-value."""
    idx = pd.bdate_range("2010-01-01", "2024-12-31")
    mask = in_window(idx, NFL_SEASON).to_numpy()
    rng = np.random.default_rng(3)
    values = 0.004 * mask + rng.normal(0, 0.002, len(idx))
    p, observed, null = permutation_pvalue(values, mask, 2000, seed=1, scheme="rotate")
    assert observed == pytest.approx(0.004, abs=5e-4)
    assert p < 0.01
    assert null.size == 2000


def test_permutation_is_calibrated_on_pure_noise():
    """No effect: p-values across seeds should be roughly uniform, not tiny."""
    idx = pd.bdate_range("2010-01-01", "2024-12-31")
    mask = in_window(idx, NFL_SEASON).to_numpy()
    pvals = []
    for seed in range(12):
        rng = np.random.default_rng(100 + seed)
        p, _, _ = permutation_pvalue(rng.normal(0, 0.02, len(idx)), mask, 400, seed=seed)
        pvals.append(p)
    # A broken (anticonservative) test would return near-zero almost every time.
    assert np.mean(np.array(pvals) < 0.05) <= 0.25
    assert np.median(pvals) > 0.15


def test_rotation_null_is_wider_than_shuffle_null_under_autocorrelation():
    """The whole reason the rotation scheme exists."""
    idx = pd.bdate_range("2010-01-01", "2024-12-31")
    mask = in_window(idx, NFL_SEASON).to_numpy()
    rng = np.random.default_rng(11)
    # Strongly autocorrelated series (a slow-moving factor).
    noise = pd.Series(rng.normal(0, 0.01, len(idx))).ewm(span=120).mean().to_numpy()
    _, _, null_rot = permutation_pvalue(noise, mask, 800, seed=2, scheme="rotate")
    _, _, null_shuf = permutation_pvalue(noise, mask, 800, seed=2, scheme="shuffle")
    assert null_rot.std() > 3 * null_shuf.std()


def test_bonferroni_and_bh():
    p = np.array([0.001, 0.02, 0.04, 0.5])
    assert bonferroni(p) == pytest.approx([0.004, 0.08, 0.16, 1.0])
    # BH: p * m / rank (0.004, 0.04, 0.05333, 0.5), then made monotone from
    # the largest down -- which leaves all four unchanged here.
    assert benjamini_hochberg(p) == pytest.approx([0.004, 0.04, 0.0533333, 0.5])


def test_bh_enforces_monotonicity():
    """A later-ranked p must never end up below an earlier-ranked one."""
    out = benjamini_hochberg(np.array([0.02, 0.021, 0.5]))
    assert out[0] == pytest.approx(out[1])  # 0.06 pulled down to 0.0315
    assert out[0] == pytest.approx(0.0315)


def test_bh_preserves_nan_positions():
    out = benjamini_hochberg(np.array([0.01, np.nan, 0.02]))
    assert np.isnan(out[1]) and np.isfinite(out[0]) and np.isfinite(out[2])


def test_multiple_testing_columns_use_full_family_size():
    idx = pd.date_range("2010-01-31", periods=180, freq="ME")
    rng = np.random.default_rng(5)
    monthly = pd.DataFrame(
        {f"T{i}": rng.normal(0, 0.05, len(idx)) for i in range(9)}, index=idx
    )
    frame = analysis.monthly_significance(monthly)
    assert len(frame) == 9 * 12
    assert frame["n_tests"].iloc[0] == 108
    ratio = frame["p_bonferroni"] / frame["p_raw"]
    assert ratio[frame["p_bonferroni"] < 1.0].round(6).eq(108).all()


# --------------------------------------------------------------------------
# Earnings exclusion
# --------------------------------------------------------------------------

def test_drop_earnings_windows_blanks_the_right_days():
    idx = pd.bdate_range("2024-01-01", periods=40)
    frame = pd.DataFrame({"AAA": 0.01, "BBB": 0.01}, index=idx)
    target = idx[20]
    out = analysis.drop_earnings_windows(frame, {"AAA": pd.DatetimeIndex([target])}, pad=3)
    assert out["AAA"].isna().sum() == 7          # centre +/- 3 trading days
    assert out["BBB"].isna().sum() == 0          # untouched ticker
    assert out["AAA"].iloc[17:24].isna().all()
    assert not np.isnan(out["AAA"].iloc[16])


def test_exclude_years_removes_only_named_years():
    idx = pd.bdate_range("2019-01-01", "2022-12-31")
    frame = pd.DataFrame({"AAA": 1.0}, index=idx)
    out = analysis.exclude_years(frame, (2020, 2021))
    assert set(out.index.year.unique()) == {2019, 2022}


# --------------------------------------------------------------------------
# Backtest
# --------------------------------------------------------------------------

def test_backtest_holds_cash_out_of_season():
    """Off-season days must contribute exactly zero at a 0% cash yield."""
    idx = pd.bdate_range("2015-01-01", "2020-12-31")
    returns = pd.DataFrame({"AAA": 0.001, "SPY": 0.0}, index=idx)
    curves, perf = backtest.run_backtest(returns, ["AAA"], cost_bps=0.0)
    n_in = int(in_window(idx, NFL_SEASON).sum())
    assert curves["seasonal"].iloc[-1] == pytest.approx(10_000 * 1.001 ** n_in, rel=1e-9)
    assert curves["buy_hold"].iloc[-1] == pytest.approx(10_000 * 1.001 ** len(idx), rel=1e-9)
    assert perf.loc["seasonal", "time_in_market_pct"] < 50


def test_transaction_costs_are_charged_once_per_switch():
    """On a flat market the cost drag is exactly (1 - c) per switch."""
    idx = pd.bdate_range("2015-01-01", "2020-12-31")
    flat = pd.DataFrame({"AAA": 0.0, "SPY": 0.0}, index=idx)
    charged, perf = backtest.run_backtest(flat, ["AAA"], cost_bps=5.0)
    switches = int(perf.loc["seasonal", "n_switches"])
    # Six seasons of entries and exits, plus the initial buy-in on day one.
    assert switches == 13
    assert perf.loc["seasonal", "n_round_trips"] == 6
    assert charged["seasonal"].iloc[-1] == pytest.approx(10_000 * (1 - 5e-4) ** switches, rel=1e-9)
    # Always-on sleeves are never charged.
    assert perf.loc["buy_hold", "n_switches"] == 0


def test_transaction_costs_reduce_a_profitable_strategy():
    idx = pd.bdate_range("2015-01-01", "2020-12-31")
    returns = pd.DataFrame({"AAA": 0.001, "SPY": 0.0}, index=idx)
    free, _ = backtest.run_backtest(returns, ["AAA"], cost_bps=0.0)
    charged, perf = backtest.run_backtest(returns, ["AAA"], cost_bps=5.0)
    assert charged["seasonal"].iloc[-1] < free["seasonal"].iloc[-1]
    # Cost is deducted from the day's return, so the drag is slightly lighter
    # than (1-c)^n: each charge lands on a notional that also grew that day.
    ratio = charged["seasonal"].iloc[-1] / free["seasonal"].iloc[-1]
    assert (1 - 5e-4) ** 13 < ratio < (1 - 5e-4) ** 12


def test_equal_weight_basket_includes_names_as_they_list():
    idx = pd.bdate_range("2024-01-01", periods=4)
    returns = pd.DataFrame(
        {"AAA": [0.02, 0.02, 0.02, 0.02], "BBB": [np.nan, np.nan, 0.04, 0.04]}, index=idx
    )
    basket = backtest.equal_weight_basket(returns, ["AAA", "BBB"])
    assert basket.iloc[0] == pytest.approx(0.02)   # AAA alone
    assert basket.iloc[2] == pytest.approx(0.03)   # equal weight of both


def test_performance_stats_drawdown_and_cagr():
    idx = pd.bdate_range("2020-01-01", periods=252)
    returns = pd.Series(0.0, index=idx)
    returns.iloc[10] = -0.5
    curve = 10_000 * (1 + returns).cumprod()
    stats = backtest.performance_stats(returns, curve)
    assert stats["max_drawdown_pct"] == pytest.approx(-50.0)
    assert stats["cagr_pct"] == pytest.approx(-50.0, abs=1.0)


# --------------------------------------------------------------------------
# End-to-end: the pipeline must recover a planted effect and only that effect
# --------------------------------------------------------------------------

def test_window_comparison_recovers_planted_effect_only_where_planted():
    idx = pd.bdate_range("2008-01-01", "2024-12-31")
    mask = in_window(idx, NFL_SEASON).to_numpy()
    rng = np.random.default_rng(42)
    exc = pd.DataFrame(
        {
            "HIT": 0.004 * mask + rng.normal(0, 0.002, len(idx)),
            "MISS": rng.normal(0, 0.002, len(idx)),
        },
        index=idx,
    )
    out = analysis.window_comparison(exc, n_permutations=1000, seed=9).set_index("ticker")
    assert out.loc["HIT", "diff_bps_day"] == pytest.approx(40.0, abs=3.0)
    assert out.loc["HIT", "p_perm_rotate"] < 0.01
    assert abs(out.loc["MISS", "diff_bps_day"]) < 5.0
    assert out.loc["MISS", "p_perm_rotate"] > 0.10
    assert out.loc["HIT", "n_seasons"] == 16
