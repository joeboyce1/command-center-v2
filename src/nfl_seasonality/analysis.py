"""Return construction and the seasonality analyses."""

from __future__ import annotations

import calendar

import numpy as np
import pandas as pd

from .config import (
    EARNINGS_EXCLUSION_TRADING_DAYS,
    FRONT_RUN,
    MARKET_BENCHMARK,
    MIN_SEASONS_FLAG,
    MIN_SEASONS_MEANINGFUL,
    NFL_SEASON,
    N_PERMUTATIONS,
    RANDOM_SEED,
    TRADING_DAYS_PER_YEAR,
    Window,
)
from .stats_tests import (
    benjamini_hochberg,
    bonferroni,
    mean_difference,
    permutation_pvalue,
)
from .windows import count_full_seasons, in_window, season_bounds

MONTH_NAMES = [calendar.month_abbr[m] for m in range(1, 13)]


# --------------------------------------------------------------------------
# Returns
# --------------------------------------------------------------------------

def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns from adjusted closes.

    Each column is differenced on its *own* observed dates before being
    aligned. The panel index is a union of trading calendars -- FLTR.L trades
    on US holidays and vice versa -- so differencing the panel directly would
    hand every US ticker a NaN on LSE-only days and then compute the next
    day's return off that hole. Per-column differencing avoids it.
    """
    prices = prices.sort_index()
    return pd.DataFrame(
        {col: prices[col].dropna().pct_change() for col in prices.columns}
    ).sort_index()


def excess_daily_returns(returns: pd.DataFrame, benchmark: str = MARKET_BENCHMARK) -> pd.DataFrame:
    """Return minus benchmark return, day by day.

    A plain difference, not a beta-adjusted alpha. These names run betas well
    above 1, so in a rising market the raw difference flatters them; that is a
    level effect and it lands in both the in-season and off-season buckets, so
    the in-minus-off *difference* is largely insulated from it. See the beta
    caveat in the report.
    """
    if benchmark not in returns.columns:
        raise KeyError(f"benchmark {benchmark} missing from returns")
    bench = returns[benchmark]
    return returns.drop(columns=[benchmark], errors="ignore").sub(bench, axis=0)


def monthly_returns(daily: pd.DataFrame) -> pd.DataFrame:
    """Compound daily returns within each calendar month."""
    return (1 + daily).resample("ME").prod(min_count=15) - 1


def monthly_excess(prices: pd.DataFrame, benchmark: str = MARKET_BENCHMARK) -> pd.DataFrame:
    """Monthly ticker return minus monthly benchmark return."""
    monthly = monthly_returns(daily_returns(prices))
    bench = monthly[benchmark]
    return monthly.drop(columns=[benchmark], errors="ignore").sub(bench, axis=0)


# --------------------------------------------------------------------------
# 1 & 2. Monthly statistics
# --------------------------------------------------------------------------

def monthly_stats(monthly: pd.DataFrame) -> pd.DataFrame:
    """Mean / median / std / hit rate / n by ticker and calendar month."""
    rows = []
    for ticker in monthly.columns:
        series = monthly[ticker].dropna()
        for month in range(1, 13):
            vals = series[series.index.month == month]
            rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "month_name": MONTH_NAMES[month - 1],
                    "n": len(vals),
                    "mean": vals.mean() if len(vals) else np.nan,
                    "median": vals.median() if len(vals) else np.nan,
                    "std": vals.std(ddof=1) if len(vals) > 1 else np.nan,
                    "hit_rate": (vals > 0).mean() if len(vals) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def monthly_significance(monthly_exc: pd.DataFrame) -> pd.DataFrame:
    """One-sample t-test of monthly excess return vs zero, per ticker-month.

    This is the 9 x 12 = 108 test family the multiplicity correction applies
    to. Raw and corrected p-values are both returned.
    """
    from scipy import stats as sps

    rows = []
    for ticker in monthly_exc.columns:
        series = monthly_exc[ticker].dropna()
        for month in range(1, 13):
            vals = series[series.index.month == month]
            if len(vals) >= 3:
                t, p = sps.ttest_1samp(vals, 0.0)
                t, p = float(t), float(p)
            else:
                t, p = np.nan, np.nan
            rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "month_name": MONTH_NAMES[month - 1],
                    "n": len(vals),
                    "mean_excess": vals.mean() if len(vals) else np.nan,
                    "t_stat": t,
                    "p_raw": p,
                }
            )
    frame = pd.DataFrame(rows)
    frame["p_bonferroni"] = bonferroni(frame["p_raw"].to_numpy())
    frame["p_bh"] = benjamini_hochberg(frame["p_raw"].to_numpy())
    frame["n_tests"] = int(frame["p_raw"].notna().sum())
    return frame


# --------------------------------------------------------------------------
# 3 & 4. In-season vs off-season, with permutation test
# --------------------------------------------------------------------------

def window_comparison(
    daily_exc: pd.DataFrame,
    window: Window = NFL_SEASON,
    n_permutations: int = N_PERMUTATIONS,
    seed: int = RANDOM_SEED,
    run_permutation: bool = True,
) -> pd.DataFrame:
    """Per-ticker in-window vs out-of-window daily excess return.

    Reports the difference in bps/day, both t-stats, and the permutation
    p-values under both null schemes.
    """
    rows = []
    for i, ticker in enumerate(daily_exc.columns):
        series = daily_exc[ticker].dropna()
        if series.empty:
            continue
        mask = in_window(series.index, window).to_numpy()
        md = mean_difference(series.to_numpy(), mask)

        p_rotate = p_shuffle = np.nan
        if run_permutation:
            p_rotate, _, _ = permutation_pvalue(
                series.to_numpy(), mask, n_permutations, seed + i, scheme="rotate"
            )
            p_shuffle, _, _ = permutation_pvalue(
                series.to_numpy(), mask, n_permutations, seed + 5000 + i, scheme="shuffle"
            )

        rows.append(
            {
                "ticker": ticker,
                "window": window.name,
                "n_seasons": count_full_seasons(series.index),
                "n_days_in": md.n_in,
                "n_days_out": md.n_out,
                "in_bps_day": md.mean_in * 1e4,
                "off_bps_day": md.mean_out * 1e4,
                "diff_bps_day": md.diff * 1e4,
                "in_annualised_pct": md.mean_in * TRADING_DAYS_PER_YEAR * 100,
                "diff_annualised_pct": md.diff * TRADING_DAYS_PER_YEAR * 100,
                "t_welch": md.t_welch,
                "p_welch": md.p_welch,
                "t_hac": md.t_hac,
                "p_hac": md.p_hac,
                "p_perm_rotate": p_rotate,
                "p_perm_shuffle": p_shuffle,
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    for col, source in (("p_hac_bh", "p_hac"), ("p_perm_bh", "p_perm_rotate")):
        frame[col] = benjamini_hochberg(frame[source].to_numpy())
    for col, source in (("p_hac_bonf", "p_hac"), ("p_perm_bonf", "p_perm_rotate")):
        frame[col] = bonferroni(frame[source].to_numpy())
    frame["meaningful"] = frame["n_seasons"] >= MIN_SEASONS_MEANINGFUL
    frame["thin_history"] = frame["n_seasons"] < MIN_SEASONS_FLAG
    return frame.sort_values("in_bps_day", ascending=False).reset_index(drop=True)


def pooled_comparison(
    daily_exc: pd.DataFrame,
    window: Window = NFL_SEASON,
    n_permutations: int = N_PERMUTATIONS,
    seed: int = RANDOM_SEED,
) -> dict[str, float]:
    """The same test on the equal-weight basket -- one test, not nine.

    The basket is the honest headline: it asks whether *the sector* has a
    season effect, without paying a nine-fold multiplicity tax.
    """
    basket = daily_exc.mean(axis=1, skipna=True).dropna()
    if basket.empty:
        return {}
    mask = in_window(basket.index, window).to_numpy()
    md = mean_difference(basket.to_numpy(), mask)
    p_rotate, observed, _ = permutation_pvalue(
        basket.to_numpy(), mask, n_permutations, seed, scheme="rotate"
    )
    p_shuffle, _, _ = permutation_pvalue(
        basket.to_numpy(), mask, n_permutations, seed + 1, scheme="shuffle"
    )
    return {
        "window": window.name,
        "n_days_in": md.n_in,
        "n_days_out": md.n_out,
        "in_bps_day": md.mean_in * 1e4,
        "off_bps_day": md.mean_out * 1e4,
        "diff_bps_day": md.diff * 1e4,
        "diff_annualised_pct": md.diff * TRADING_DAYS_PER_YEAR * 100,
        "t_welch": md.t_welch,
        "p_welch": md.p_welch,
        "t_hac": md.t_hac,
        "p_hac": md.p_hac,
        "p_perm_rotate": p_rotate,
        "p_perm_shuffle": p_shuffle,
        "observed_diff": observed,
    }


# --------------------------------------------------------------------------
# Controls
# --------------------------------------------------------------------------

def coverage_table(prices: pd.DataFrame) -> pd.DataFrame:
    """Start date, end date, observation count and season count per symbol."""
    rows = []
    for symbol in prices.columns:
        series = prices[symbol].dropna()
        n_seasons = count_full_seasons(series.index)
        rows.append(
            {
                "symbol": symbol,
                "start": series.index.min().date() if len(series) else None,
                "end": series.index.max().date() if len(series) else None,
                "n_obs": len(series),
                "n_full_seasons": n_seasons,
                "flag_lt_5_seasons": n_seasons < MIN_SEASONS_FLAG,
                "flag_not_meaningful": n_seasons < MIN_SEASONS_MEANINGFUL,
            }
        )
    return pd.DataFrame(rows).sort_values("n_full_seasons", ascending=False).reset_index(drop=True)


def season_coverage_detail(prices: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for symbol in prices.columns:
        series = prices[symbol].dropna()
        bounds = season_bounds(series.index)
        if bounds.empty:
            continue
        bounds.insert(0, "symbol", symbol)
        frames.append(bounds)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def drop_earnings_windows(
    daily_exc: pd.DataFrame,
    earnings: dict[str, pd.DatetimeIndex],
    pad: int = EARNINGS_EXCLUSION_TRADING_DAYS,
) -> pd.DataFrame:
    """Blank out +/- ``pad`` trading days around each earnings date.

    Q3 (late Oct / early Nov) and Q4 (Feb) reports land squarely inside the
    NFL window, so an apparent season effect could just be an earnings-drift
    effect wearing a jersey.
    """
    out = daily_exc.copy()
    index = out.index
    positions = pd.Series(np.arange(len(index)), index=index)
    for ticker in out.columns:
        dates = earnings.get(ticker)
        if dates is None or len(dates) == 0:
            continue
        blocked: set[int] = set()
        for date in dates:
            # Snap to the next trading day at or after the report date.
            loc = index.searchsorted(date)
            if loc >= len(index):
                continue
            centre = int(positions.iloc[loc])
            blocked.update(range(max(0, centre - pad), min(len(index), centre + pad + 1)))
        if blocked:
            out.iloc[sorted(blocked), out.columns.get_loc(ticker)] = np.nan
    return out


def exclude_years(frame: pd.DataFrame, years: tuple[int, ...]) -> pd.DataFrame:
    return frame[~frame.index.year.isin(years)]


def month_heatmap_matrix(stats_frame: pd.DataFrame, value: str = "mean") -> pd.DataFrame:
    """Ticker x month matrix for plotting."""
    matrix = stats_frame.pivot(index="ticker", columns="month", values=value)
    matrix.columns = [MONTH_NAMES[m - 1] for m in matrix.columns]
    return matrix


def front_run_comparison(daily_exc: pd.DataFrame, **kwargs) -> pd.DataFrame:
    return window_comparison(daily_exc, window=FRONT_RUN, **kwargs)
