"""Season-window masks and NFL season-year bookkeeping."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import NFL_SEASON, Window


def in_window(index: pd.DatetimeIndex, window: Window) -> pd.Series:
    """Boolean mask: which dates fall inside ``window``."""
    md = list(zip(index.month, index.day))
    start = (window.start_month, window.start_day)
    end = (window.end_month, window.end_day)
    if window.wraps:
        mask = [(x >= start) or (x <= end) for x in md]
    else:
        mask = [start <= x <= end for x in md]
    return pd.Series(mask, index=index, name=window.name)


def season_year(index: pd.DatetimeIndex) -> pd.Series:
    """Label each date with the NFL season it belongs to.

    A season is named for the year kickoff happens in: 2023-09-10 and
    2024-02-11 (the Super Bowl) both belong to season 2023. Dates in the
    off-season get the year of the season that is about to start, but callers
    should mask on :func:`in_window` before using this for season counting.
    """
    year = pd.Series(index.year, index=index)
    month = pd.Series(index.month, index=index)
    # Jan 1 - Feb 15 belongs to the previous calendar year's season.
    return year.where(month >= 9, year - 1).where(~((month >= 3) & (month <= 8)), year)


def season_id(index: pd.DatetimeIndex) -> pd.Series:
    """Season year for in-season dates, NaN elsewhere."""
    mask = in_window(index, NFL_SEASON)
    return season_year(index).where(mask, other=np.nan)


def count_full_seasons(index: pd.DatetimeIndex) -> int:
    """Number of NFL seasons the data covers *substantially*.

    A season counts only if the ticker has data spanning at least 80% of that
    season's trading days, which keeps a ticker that IPO'd in December from
    claiming a full season of coverage.
    """
    if len(index) == 0:
        return 0
    sid = season_id(index).dropna()
    if sid.empty:
        return 0
    observed = sid.value_counts()
    # A full Sep 1 - Feb 15 window is roughly 115 trading days.
    full_season_days = 115
    return int((observed >= 0.8 * full_season_days).sum())


def season_bounds(index: pd.DatetimeIndex) -> pd.DataFrame:
    """First/last observed date and day count for each season year."""
    sid = season_id(index).dropna()
    if sid.empty:
        return pd.DataFrame(columns=["season", "start", "end", "trading_days"])
    frame = pd.DataFrame({"season": sid.astype(int), "date": sid.index})
    grouped = frame.groupby("season")["date"]
    out = pd.DataFrame(
        {
            "start": grouped.min(),
            "end": grouped.max(),
            "trading_days": grouped.count(),
        }
    ).reset_index()
    return out
