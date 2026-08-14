"""Price and event data loading for the PEAD study.

Two sources are supported:

* ``yfinance`` - used when the machine running the study has outbound network
  access to Yahoo Finance.
* local CSV - used when it does not, or when you want a frozen, reviewable
  copy of the series the numbers were computed from.

Downloads are cached under ``data/prices/`` so a study is reproducible after
the fact and so re-runs do not re-hit the network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICE_CACHE = os.path.join(REPO_ROOT, "data", "prices")


class DataUnavailable(RuntimeError):
    """Raised when a price series cannot be obtained from any source."""


def _cache_path(ticker: str) -> str:
    return os.path.join(PRICE_CACHE, f"{ticker.upper()}.csv")


def load_prices(ticker: str, start: str, end: str, allow_download: bool = True) -> pd.Series:
    """Return a daily close series for ``ticker`` indexed by date.

    The cache is consulted first. Prices are split/dividend adjusted, which
    matters here only for the benchmark - CRWV has paid no dividend and has
    not split since its March 2025 IPO.
    """
    cached = _cache_path(ticker)
    if os.path.exists(cached):
        frame = pd.read_csv(cached, parse_dates=["date"]).set_index("date")
        series = frame["close"].astype(float)
        window = series.loc[start:end]
        if not window.empty:
            return window

    if not allow_download:
        raise DataUnavailable(
            f"no cached prices for {ticker} at {cached} and downloads are disabled"
        )

    series = _download(ticker, start, end)
    os.makedirs(PRICE_CACHE, exist_ok=True)
    series.rename("close").rename_axis("date").to_frame().to_csv(cached)
    return series


def _download(ticker: str, start: str, end: str) -> pd.Series:
    try:
        import yfinance
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise DataUnavailable(
            "yfinance is not installed; `pip install yfinance` or drop a CSV "
            f"with date,close columns at {_cache_path(ticker)}"
        ) from exc

    frame = yfinance.download(
        ticker, start=start, end=end, auto_adjust=True, progress=False
    )
    if frame is None or frame.empty:
        raise DataUnavailable(
            f"yfinance returned no rows for {ticker}. If this machine is behind "
            "an egress proxy that blocks Yahoo Finance, fetch the series "
            f"elsewhere and save it to {_cache_path(ticker)}"
        )
    close = frame["Close"]
    if isinstance(close, pd.DataFrame):  # yfinance returns a frame for 1 ticker
        close = close.iloc[:, 0]
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close.astype(float)


@dataclass(frozen=True)
class EarningsEvent:
    """One earnings announcement.

    ``timing`` is ``amc`` (after market close) or ``bmo`` (before market open)
    and decides which session first prices the news - the single most common
    way an event study gets silently misaligned by a day.
    """

    ticker: str
    fiscal_quarter: str
    announce_date: pd.Timestamp
    timing: str
    revenue_actual: float | None = None
    revenue_consensus: float | None = None
    eps_actual: float | None = None
    eps_consensus: float | None = None
    note: str = ""

    @property
    def revenue_surprise_pct(self) -> float | None:
        if not self.revenue_actual or not self.revenue_consensus:
            return None
        return (self.revenue_actual - self.revenue_consensus) / abs(self.revenue_consensus)

    @property
    def eps_surprise_pct(self) -> float | None:
        """Percentage EPS surprise.

        Both CRWV actuals and consensus are negative through the sample, so the
        sign convention matters: a smaller loss than expected is a positive
        surprise. Dividing by ``abs(consensus)`` gives that.
        """
        if self.eps_actual is None or not self.eps_consensus:
            return None
        return (self.eps_actual - self.eps_consensus) / abs(self.eps_consensus)


def load_events(path: str) -> list[EarningsEvent]:
    frame = pd.read_csv(path, parse_dates=["announce_date"])
    events: list[EarningsEvent] = []
    for row in frame.to_dict("records"):
        events.append(
            EarningsEvent(
                ticker=row["ticker"],
                fiscal_quarter=row["fiscal_quarter"],
                announce_date=pd.Timestamp(row["announce_date"]),
                timing=str(row["timing"]).lower(),
                revenue_actual=_opt(row.get("revenue_actual")),
                revenue_consensus=_opt(row.get("revenue_consensus")),
                eps_actual=_opt(row.get("eps_actual")),
                eps_consensus=_opt(row.get("eps_consensus")),
                note=str(row.get("note") or ""),
            )
        )
    return sorted(events, key=lambda e: e.announce_date)


def _opt(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
