"""Price and earnings-date acquisition, cached to CSV for reproducibility."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ALL_SYMBOLS, RANDOM_SEED


def _price_path(cache_dir: Path, symbol: str) -> Path:
    return cache_dir / f"prices_{symbol.replace('.', '_')}.csv"


def _earnings_path(cache_dir: Path, symbol: str) -> Path:
    return cache_dir / f"earnings_{symbol.replace('.', '_')}.csv"


def download_prices(symbol: str, cache_dir: Path, force: bool = False) -> pd.DataFrame:
    """Download max daily history for ``symbol``, caching to CSV.

    Prices are split- and dividend-adjusted (``auto_adjust=True``).
    """
    path = _price_path(cache_dir, symbol)
    if path.exists() and not force:
        return read_price_csv(path)

    import yfinance as yf

    raw = yf.download(
        symbol,
        period="max",
        interval="1d",
        auto_adjust=True,
        progress=False,
        actions=False,
    )
    if raw is None or raw.empty:
        raise RuntimeError(f"No price data returned for {symbol}")
    if isinstance(raw.columns, pd.MultiIndex):
        # yfinance returns (field, ticker) columns even for a single symbol.
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.rename(columns=str.lower)
    raw.index.name = "date"
    cache_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(path)
    return read_price_csv(path)


def read_price_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    frame.index.name = "date"
    return frame[~frame.index.duplicated(keep="last")].sort_index()


def download_earnings_dates(symbol: str, cache_dir: Path, force: bool = False) -> pd.DatetimeIndex:
    """Best-effort earnings calendar for ``symbol``, cached to CSV.

    yfinance only exposes a limited window of earnings history (broadly the
    last few years plus scheduled future dates), so the earnings-excluded
    results cover less of the sample than the headline numbers. Failures are
    swallowed and returned as an empty index -- an unavailable calendar should
    not abort the run.
    """
    path = _earnings_path(cache_dir, symbol)
    if path.exists() and not force:
        parsed = pd.read_csv(path, parse_dates=["date"])
        return pd.DatetimeIndex(parsed["date"]).tz_localize(None).normalize()

    import yfinance as yf

    dates: list[pd.Timestamp] = []
    try:
        frame = yf.Ticker(symbol).get_earnings_dates(limit=200)
        if frame is not None and not frame.empty:
            idx = pd.DatetimeIndex(frame.index)
            if idx.tz is not None:
                idx = idx.tz_convert("UTC").tz_localize(None)
            dates = list(idx.normalize())
    except Exception as exc:  # noqa: BLE001 - calendar is optional
        print(f"  ! earnings calendar unavailable for {symbol}: {exc}", file=sys.stderr)

    cache_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": sorted(set(dates))}).to_csv(path, index=False)
    return pd.DatetimeIndex(sorted(set(dates)))


def load_universe(
    cache_dir: Path,
    symbols: list[str] | None = None,
    force: bool = False,
    with_earnings: bool = True,
) -> tuple[pd.DataFrame, dict[str, pd.DatetimeIndex]]:
    """Return (close-price panel, earnings dates by symbol)."""
    symbols = symbols or ALL_SYMBOLS
    closes: dict[str, pd.Series] = {}
    earnings: dict[str, pd.DatetimeIndex] = {}

    for symbol in symbols:
        try:
            frame = download_prices(symbol, cache_dir, force=force)
        except Exception as exc:  # noqa: BLE001 - one bad ticker must not kill the run
            print(f"  ! skipping {symbol}: {exc}", file=sys.stderr)
            continue
        closes[symbol] = frame["close"]
        if with_earnings:
            earnings[symbol] = download_earnings_dates(symbol, cache_dir, force=force)

    if not closes:
        raise RuntimeError("No price data could be loaded for any symbol.")
    panel = pd.DataFrame(closes).sort_index()
    return panel, earnings


# --------------------------------------------------------------------------
# Offline self-test fixture.
# --------------------------------------------------------------------------
# NOT DATA. This exists solely so the pipeline can be exercised end to end in
# a sandbox with no market-data egress. Anything produced from it is labelled
# SYNTHETIC and must never be read as a finding about real securities.
# --------------------------------------------------------------------------

def synthetic_universe(
    cache_dir: Path,
    symbols: list[str] | None = None,
    start: str = "2012-01-03",
    end: str = "2026-08-01",
    seed: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, dict[str, pd.DatetimeIndex]]:
    """Generate fake price history with a known planted seasonal effect.

    DKNG and RSI get a genuine +8bps/day in-season excess drift; every other
    name gets none. A correct pipeline must recover exactly those two.
    """
    from .config import FLUT_LONG_HISTORY_PROXY, MARKET_BENCHMARK
    from .windows import NFL_SEASON, in_window

    symbols = symbols or ALL_SYMBOLS
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, end)
    season_mask = in_window(dates, NFL_SEASON).to_numpy()

    planted = {"DKNG": 0.0008, "RSI": 0.0008}
    listing_start = {"DKNG": "2020-04-24", "FLUT": "2024-01-29", "RSI": "2020-12-30", "GENI": "2021-04-21"}

    market = rng.normal(0.0004, 0.011, len(dates))
    closes: dict[str, pd.Series] = {}
    for symbol in symbols:
        if symbol == MARKET_BENCHMARK:
            returns = market
        else:
            beta = 1.0 if symbol == "XLY" else rng.uniform(1.1, 2.0)
            idio = rng.normal(0.0, 0.02 if symbol not in ("XLY",) else 0.006, len(dates))
            returns = beta * market + idio + planted.get(symbol, 0.0) * season_mask
        series = pd.Series(100 * np.cumprod(1 + returns), index=dates, name=symbol)
        first = listing_start.get(symbol)
        if symbol == FLUT_LONG_HISTORY_PROXY:
            first = None
        if first is not None:
            series = series.loc[series.index >= pd.Timestamp(first)]
        closes[symbol] = series

    panel = pd.DataFrame(closes).sort_index()
    cache_dir.mkdir(parents=True, exist_ok=True)
    for symbol in panel.columns:
        col = panel[symbol].dropna()
        pd.DataFrame({"close": col}).rename_axis("date").to_csv(
            _price_path(cache_dir, f"SYNTHETIC_{symbol}")
        )

    # Fake quarterly earnings, one per ticker per quarter.
    earnings = {
        symbol: pd.DatetimeIndex(
            pd.bdate_range(panel[symbol].dropna().index.min(), panel.index.max(), freq="QE")
        )
        for symbol in panel.columns
    }
    return panel, earnings
