"""Seasonal-rotation backtest vs buy-and-hold vs SPY."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    CASH_ANNUAL_YIELD,
    INITIAL_CAPITAL,
    MARKET_BENCHMARK,
    NFL_SEASON,
    TRADING_DAYS_PER_YEAR,
    TRANSACTION_COST_BPS,
    Window,
)
from .windows import in_window


def equal_weight_basket(returns: pd.DataFrame, tickers: list[str]) -> pd.Series:
    """Daily return of an equal-weight, daily-rebalanced basket.

    Names are included from the day they start trading, so basket membership
    grows over time. Intra-basket rebalancing turnover is NOT charged -- only
    season entry and exit are (see the cost caveat in the report).
    """
    cols = [t for t in tickers if t in returns.columns]
    if not cols:
        raise ValueError("no basket constituents present in returns")
    return returns[cols].mean(axis=1, skipna=True).dropna()


def run_backtest(
    returns: pd.DataFrame,
    tickers: list[str],
    window: Window = NFL_SEASON,
    initial_capital: float = INITIAL_CAPITAL,
    cost_bps: float = TRANSACTION_COST_BPS,
    cash_yield: float = CASH_ANNUAL_YIELD,
    benchmark: str = MARKET_BENCHMARK,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (equity curves, performance summary).

    Three sleeves:
      * ``seasonal``  -- equal-weight basket held only inside ``window``,
                         cash otherwise. Costs charged on every switch.
      * ``buy_hold``  -- the same basket, held always.
      * ``spy``       -- the market benchmark, held always.
    """
    basket = equal_weight_basket(returns, tickers)
    mask = in_window(basket.index, window)

    daily_cash = (1 + cash_yield) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    gross = np.where(mask.to_numpy(), basket.to_numpy(), daily_cash)

    # A switch happens on any day the exposure differs from the prior day.
    # Charge on both legs of the round trip: exit costs and entry costs.
    prev = mask.shift(1).fillna(False).to_numpy()
    switches = mask.to_numpy() != prev
    cost = switches * (cost_bps / 1e4)
    seasonal = pd.Series(gross - cost, index=basket.index, name="seasonal")

    curves = pd.DataFrame(
        {
            "seasonal": initial_capital * (1 + seasonal).cumprod(),
            "buy_hold": initial_capital * (1 + basket).cumprod(),
        }
    )
    if benchmark in returns.columns:
        spy = returns[benchmark].reindex(basket.index).fillna(0.0)
        curves["spy"] = initial_capital * (1 + spy).cumprod()

    sleeves = {
        "seasonal": seasonal,
        "buy_hold": basket,
    }
    if benchmark in returns.columns:
        sleeves["spy"] = returns[benchmark].reindex(basket.index).fillna(0.0)

    summary = pd.DataFrame(
        {name: performance_stats(series, curves[name]) for name, series in sleeves.items()}
    ).T
    # n_switches is what costs are actually charged on (the initial buy-in is
    # one of them); round trips are just the friendlier way to read it.
    summary["n_switches"] = int(switches.sum())
    summary["n_round_trips"] = int(switches.sum()) // 2
    always_on = ["buy_hold"] + (["spy"] if "spy" in summary.index else [])
    summary.loc[always_on, ["n_switches", "n_round_trips"]] = 0
    summary["time_in_market_pct"] = 100.0
    summary.loc["seasonal", "time_in_market_pct"] = float(mask.mean() * 100)
    return curves, summary


def performance_stats(returns: pd.Series, curve: pd.Series) -> pd.Series:
    """CAGR, vol, Sharpe, max drawdown, final value."""
    returns = returns.dropna()
    if returns.empty:
        return pd.Series(dtype=float)
    years = len(returns) / TRADING_DAYS_PER_YEAR
    total = float(curve.iloc[-1] / curve.iloc[0])
    cagr = total ** (1 / years) - 1 if years > 0 else np.nan
    vol = float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
    sharpe = float(returns.mean() / returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)) if returns.std(ddof=1) else np.nan
    drawdown = float((curve / curve.cummax() - 1).min())
    return pd.Series(
        {
            "final_value": float(curve.iloc[-1]),
            "total_return_pct": (total - 1) * 100,
            "cagr_pct": cagr * 100,
            "vol_pct": vol * 100,
            "sharpe": sharpe,
            "max_drawdown_pct": drawdown * 100,
        }
    )
