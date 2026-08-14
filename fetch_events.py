#!/usr/bin/env python3
"""Build an events CSV of earnings dates, with AMC/BMO timing.

    python fetch_events.py NVDA AMD MU --out data/universe_earnings.csv

Requires network access and `yfinance`; it cannot run in a sandbox with no
egress. Timing is inferred from the announcement timestamp rather than trusted
from a vendor label: an after-hours release priced on the wrong session is the
single most damaging error in this study, so it is derived from the clock.

Coverage caveat: Yahoo's earnings history is shallow, often only a couple of
years. For a longer backtest, prefer Financial Modeling Prep's earnings
endpoint (it carries an explicit bmo/amc field) or SEC EDGAR 8-K Item 2.02
filings, whose acceptance timestamp gives the same information for free.
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

# US equity regular session, Eastern.
MARKET_OPEN_HOUR = 9
MARKET_CLOSE_HOUR = 16


def infer_timing(stamp: pd.Timestamp) -> str | None:
    """Classify an announcement timestamp as before-open or after-close.

    Returns None when the timestamp lands inside the regular session, which
    usually means the vendor recorded a placeholder time rather than a real
    one. Guessing there would silently misalign the event by a full session,
    so it is left for the caller to resolve.
    """
    if stamp is None or pd.isna(stamp):
        return None
    if stamp.hour == 0 and stamp.minute == 0:
        return None  # midnight is a placeholder, not an announcement time
    if stamp.hour >= MARKET_CLOSE_HOUR:
        return "amc"
    if stamp.hour < MARKET_OPEN_HOUR or (stamp.hour == MARKET_OPEN_HOUR and stamp.minute < 30):
        return "bmo"
    return None


def frame_to_events(ticker: str, frame: pd.DataFrame) -> tuple[list[dict], list[str]]:
    """Convert a yfinance earnings-dates frame into event rows.

    Returns the rows plus a list of human-readable problems, so the caller can
    report what needs filling in by hand instead of writing a plausible file
    with silent holes in it.
    """
    rows: list[dict] = []
    problems: list[str] = []

    for stamp, record in frame.iterrows():
        stamp = pd.Timestamp(stamp)
        timing = infer_timing(stamp)
        local = stamp.tz_localize(None) if stamp.tzinfo else stamp

        if timing is None:
            problems.append(
                f"{ticker} {local.date()}: ambiguous announcement time "
                f"({local.time()}); set timing by hand"
            )
            continue

        rows.append(
            {
                "ticker": ticker,
                "fiscal_quarter": f"{local.year}Q{(local.month - 1) // 3 + 1}",
                "announce_date": local.date().isoformat(),
                "timing": timing,
                "eps_actual": _opt(record.get("Reported EPS")),
                "eps_consensus": _opt(record.get("EPS Estimate")),
                "implied_move_pct": "",
                "note": "",
            }
        )
    return rows, problems


def _opt(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def fetch(tickers: list[str], limit: int) -> tuple[list[dict], list[str]]:
    try:
        import yfinance
    except ImportError:
        raise SystemExit("yfinance is not installed: pip install yfinance")

    rows: list[dict] = []
    problems: list[str] = []
    for ticker in tickers:
        try:
            frame = yfinance.Ticker(ticker).get_earnings_dates(limit=limit)
        except Exception as exc:  # network, rate limit, delisted symbol
            problems.append(f"{ticker}: fetch failed ({exc})")
            continue

        if frame is None or frame.empty:
            problems.append(f"{ticker}: no earnings dates returned")
            continue

        got, issues = frame_to_events(ticker, frame)
        rows.extend(got)
        problems.extend(issues)
    return rows, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=40, help="events per ticker")
    args = parser.parse_args()

    rows, problems = fetch(args.tickers, args.limit)

    for problem in problems:
        print(f"  [needs attention] {problem}", file=sys.stderr)

    if not rows:
        print("No usable events. Nothing written.", file=sys.stderr)
        return 1

    frame = pd.DataFrame(rows).sort_values(["ticker", "announce_date"])
    # Future-dated rows come back from Yahoo alongside history.
    today = pd.Timestamp.today().normalize()
    future = pd.to_datetime(frame["announce_date"]) > today
    if future.any():
        print(f"  Dropped {int(future.sum())} not-yet-reported dates.", file=sys.stderr)
        frame = frame[~future]

    frame.to_csv(args.out, index=False)
    print(
        f"Wrote {len(frame)} events across {frame.ticker.nunique()} tickers to {args.out}"
        + (f" ({len(problems)} need attention)" if problems else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
