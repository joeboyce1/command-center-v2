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
from pead.eventstudy import DEFAULT_THRESHOLDS, run_event_study, summarize
from pead.validate import (
    check_events,
    check_implied_coverage,
    check_power,
    check_prices,
    effective_sample_size,
    report,
)

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
HORIZONS = (1, 3, 5, 10, 21, 42, 63)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        help="tickers to include. Defaults to every ticker in the events file, "
        "so a universe run needs no flag at all",
    )
    parser.add_argument("--benchmark", default="QQQ", help="market proxy for abnormal returns")
    parser.add_argument("--events", default=os.path.join(REPO_ROOT, "data", "crwv_earnings.csv"))
    parser.add_argument("--start", default="2025-03-28", help="CRWV IPO date")
    parser.add_argument("--end", default=None, help="defaults to today")
    parser.add_argument("--offline", action="store_true", help="never hit the network")
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="how big the reaction must be for the signal to fire. Units depend "
        "on --signal: multiples of the implied move (excess_move, default 1.0), "
        "multiples of the stock's average past earnings move (earnings_vol_move, "
        "default 1.0), standard deviations (sigma_move, default 3.0), or a raw "
        "decimal fraction (abs_move, default 0.10 = 10%%)",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="print aggregate results even when the data-quality gates fail "
        "(for exploration only - the gates exist because a plausible-looking "
        "aggregate is the failure mode)",
    )
    parser.add_argument(
        "--signal",
        default="sigma_move",
        choices=(
            "excess_move",
            "sigma_move",
            "earnings_vol_move",
            "abs_move",
            "reaction",
            "revenue",
            "eps",
        ),
        help="which signal the verdict is gated on. sigma_move is the default "
        "because it needs no options data and stays comparable across tickers",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    end = args.end or pd.Timestamp.today().strftime("%Y-%m-%d")
    events = load_events(args.events)

    # The events file is the source of truth for the universe unless the
    # caller narrows it, so adding a ticker means adding its rows, not
    # remembering to pass another flag.
    universe = args.tickers or sorted({e.ticker for e in events})
    print(
        f"Loaded {len(events)} events across {len(universe)} tickers: "
        f"{', '.join(universe)}\n"
    )

    try:
        benchmark = load_prices(args.benchmark, args.start, end, allow_download=not args.offline)
    except DataUnavailable as exc:
        print(f"Benchmark unavailable: {exc}\n", file=sys.stderr)
        return report_qualitative(events)

    findings = check_prices(args.benchmark, benchmark) + check_implied_coverage(events)
    results, skipped = [], []

    for ticker in universe:
        ticker_events = [e for e in events if e.ticker == ticker]
        if not ticker_events:
            skipped.append(f"{ticker}: no events in {os.path.basename(args.events)}")
            continue
        try:
            prices = load_prices(ticker, args.start, end, allow_download=not args.offline)
        except DataUnavailable as exc:
            # One missing series must not abort a universe run.
            skipped.append(f"{ticker}: {exc}")
            continue

        findings += check_prices(ticker, prices)
        findings += check_events(ticker_events, prices, max(HORIZONS))
        results += run_event_study(ticker_events, prices, benchmark, HORIZONS)

    for problem in skipped:
        print(f"  [skipped] {problem}\n", file=sys.stderr)

    if not results:
        if len(universe) == 1:
            print("No usable price data.\n", file=sys.stderr)
            return report_qualitative(events)
        print("No events fell inside any price series.", file=sys.stderr)
        return 1

    # Power is judged on the horizon the thesis is about (~60 calendar days),
    # using a clustering-adjusted sample size. Pooling tickers is what makes
    # this check passable - and also what makes the clustering penalty real,
    # since names report in the same crowded weeks.
    verdict_horizon = 42
    signed = [
        r.signal(args.signal, args.threshold) * r.drift[verdict_horizon]
        for r in results
        if r.signal(args.signal, args.threshold)
        and verdict_horizon in r.drift
    ]
    n_eff = effective_sample_size([r.event_day for r in results])
    findings += check_power(signed, f"{args.signal} @ +{verdict_horizon}d", n_eff)

    can_conclude = report(findings, strict=not args.no_strict)
    print()

    if len(universe) > 1:
        print(f"Per-ticker coverage (signal: {args.signal})\n")
        print(_coverage(results, args).to_string(index=False))
        print()

    print("Per-event announcement reaction and drift (abnormal, vs "
          f"{args.benchmark})\n")
    per_event = pd.DataFrame(
        [
            {
                "ticker": r.event.ticker,
                "quarter": r.event.fiscal_quarter,
                "event_day": r.event_day.date(),
                "beta": round(r.beta, 2),
                "announce_raw": f"{r.announcement_raw:+.2%}",
                "announce_ar": f"{r.announcement_ar:+.2%}",
                "implied": (
                    f"{r.event.implied_move_pct:.1%}" if r.event.implied_move_pct else "n/a"
                ),
                "x_implied": (
                    f"{r.implied_multiple:.2f}x" if r.implied_multiple is not None else "n/a"
                ),
                "sigma": (
                    f"{r.sigma_multiple:.1f}sd" if r.sigma_multiple is not None else "n/a"
                ),
                "x_earn_vol": (
                    f"{r.earnings_vol_multiple:.2f}x"
                    if r.earnings_vol_multiple is not None
                    else "n/a"
                ),
                **{f"car_+{h}d": f"{r.drift[h]:+.2%}" for h in HORIZONS if h in r.drift},
            }
            for r in results
        ]
    )
    print(per_event.to_string(index=False))

    if not can_conclude:
        return 2

    for mode, label in (
        ("excess_move", "Signal = reaction broke the options-implied move"),
        ("sigma_move", "Signal = reaction in SDs of the stock's own daily vol"),
        ("earnings_vol_move", "Signal = reaction vs the stock's average past earnings move"),
        ("abs_move", "Signal = reaction past a fixed percentage"),
        ("reaction", "Signal = sign of the announcement-day move (earnings momentum)"),
        ("revenue", "Signal = sign of the revenue surprise"),
        ("eps", "Signal = sign of the EPS surprise"),
    ):
        # --threshold is expressed in the selected signal's units, so it must
        # not leak into the others: 3.0 means 3 sigma, but 300% to abs_move.
        threshold = args.threshold if mode == args.signal else None
        table = summarize(results, mode, HORIZONS, threshold)
        if table.empty:
            continue
        used = threshold if threshold is not None else DEFAULT_THRESHOLDS.get(mode)
        suffix = f"  [fires at {used:g}]" if used is not None else ""
        print(f"\n{label}{suffix}")
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


def _coverage(results, args) -> pd.DataFrame:
    """How many events each ticker contributed, and how many fired the signal.

    Worth seeing before any aggregate: if one name supplies most of the firing
    events, the pooled result is that name's result wearing a universe costume.
    """
    rows = {}
    for result in results:
        row = rows.setdefault(
            result.event.ticker, {"ticker": result.event.ticker, "events": 0, "fired": 0}
        )
        row["events"] += 1
        if result.signal(args.signal, args.threshold):
            row["fired"] += 1

    frame = pd.DataFrame(rows.values()).sort_values("fired", ascending=False)
    total = frame["fired"].sum()
    frame["share_of_signals"] = (
        frame["fired"].map(lambda f: f"{f / total:.0%}") if total else "n/a"
    )
    return frame


def report_qualitative(events) -> int:
    """Fallback: show the event table and the reported reactions."""
    path = os.path.join(REPO_ROOT, "data", "crwv_observed_reactions.csv")
    print("Falling back to the reported-reaction table (no benchmark adjustment).\n")
    frame = pd.read_csv(path, comment="#")
    columns = [
        "fiscal_quarter",
        "event_day",
        "reaction_1d_pct",
        "implied_move_pct",
        "implied_multiple",
        "drift_30_60d_direction",
        "confirms_thesis",
        "confidence",
    ]
    print(frame[columns].to_string(index=False))

    verdict = frame["confirms_thesis"].value_counts()
    print(
        f"\nExcess-move thesis: {verdict.get('yes', 0)} confirm, "
        f"{verdict.get('no', 0)} contradict, {verdict.get('pending', 0)} pending."
    )

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
