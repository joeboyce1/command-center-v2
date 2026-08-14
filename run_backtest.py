#!/usr/bin/env python3
"""Backtest post-earnings announcement drift for a single ticker.

    python run_backtest.py --ticker CRWV --benchmark QQQ

With network access the price series is pulled via yfinance and cached under
data/prices/. Without it, drop a CSV of `date,close` at data/prices/<TICKER>.csv
and the study runs off that. If no price series is available at all the script
falls back to the qualitative event table so the sample is still visible.
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

from pead.data import DataUnavailable, load_events, load_prices
from pead.eventstudy import run_event_study, summarize

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
HORIZONS = (1, 3, 5, 10, 21, 42, 63)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default="CRWV")
    parser.add_argument("--benchmark", default="QQQ", help="market proxy for abnormal returns")
    parser.add_argument("--events", default=os.path.join(REPO_ROOT, "data", "crwv_earnings.csv"))
    parser.add_argument("--start", default="2025-03-28", help="CRWV IPO date")
    parser.add_argument("--end", default=None, help="defaults to today")
    parser.add_argument("--offline", action="store_true", help="never hit the network")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    end = args.end or pd.Timestamp.today().strftime("%Y-%m-%d")
    events = load_events(args.events)
    print(f"Loaded {len(events)} earnings events for {args.ticker}\n")

    try:
        prices = load_prices(args.ticker, args.start, end, allow_download=not args.offline)
        benchmark = load_prices(args.benchmark, args.start, end, allow_download=not args.offline)
    except DataUnavailable as exc:
        print(f"Price data unavailable: {exc}\n", file=sys.stderr)
        return report_qualitative(events)

    results = run_event_study(events, prices, benchmark, HORIZONS)
    if not results:
        print("No events fell inside the price series.", file=sys.stderr)
        return 1

    print("Per-event announcement reaction and drift (abnormal, vs "
          f"{args.benchmark})\n")
    per_event = pd.DataFrame(
        [
            {
                "quarter": r.event.fiscal_quarter,
                "event_day": r.event_day.date(),
                "beta": round(r.beta, 2),
                "announce_ar": f"{r.announcement_ar:+.2%}",
                **{f"car_+{h}d": f"{r.drift[h]:+.2%}" for h in HORIZONS if h in r.drift},
            }
            for r in results
        ]
    )
    print(per_event.to_string(index=False))

    for mode, label in (
        ("reaction", "Signal = sign of the announcement-day move (earnings momentum)"),
        ("revenue", "Signal = sign of the revenue surprise"),
        ("eps", "Signal = sign of the EPS surprise"),
    ):
        table = summarize(results, mode, HORIZONS)
        if table.empty:
            continue
        print(f"\n{label}")
        formatted = table.assign(
            mean_signed_car=lambda d: d.mean_signed_car.map("{:+.2%}".format),
            median_signed_car=lambda d: d.median_signed_car.map("{:+.2%}".format),
            stdev=lambda d: d.stdev.map("{:.2%}".format),
            t_stat=lambda d: d.t_stat.map("{:+.2f}".format),
            hit_rate=lambda d: d.hit_rate.map("{:.0%}".format),
        )
        print(formatted.to_string(index=False))

    print(
        "\nWith a handful of events, t-stats are indicative only. PEAD is a "
        "cross-sectional effect; a single ticker cannot confirm or refute it."
    )
    return 0


def report_qualitative(events) -> int:
    """Fallback: show the event table and the reported reactions."""
    path = os.path.join(REPO_ROOT, "data", "crwv_observed_reactions.csv")
    print("Falling back to the reported-reaction table (no benchmark adjustment).\n")
    frame = pd.read_csv(path, comment="#")
    print(frame[["fiscal_quarter", "event_day", "reaction_1d_pct", "drift_direction"]].to_string(index=False))

    surprises = pd.DataFrame(
        [
            {
                "quarter": e.fiscal_quarter,
                "revenue_surprise": (
                    f"{e.revenue_surprise_pct:+.1%}" if e.revenue_surprise_pct is not None else "n/a"
                ),
                "eps_surprise": (
                    f"{e.eps_surprise_pct:+.1%}" if e.eps_surprise_pct is not None else "n/a"
                ),
            }
            for e in events
        ]
    )
    print("\nFundamental surprises\n")
    print(surprises.to_string(index=False))
    print(
        "\nRe-run with a price series in data/prices/ for benchmark-adjusted "
        "CARs and t-stats."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
