#!/usr/bin/env python3
"""Large-cap PEAD direction backtest, 2026 YTD.

Question: after a large cap reports earnings, how often does the ~30-day
post-earnings drift move in the SAME direction as the immediate (next-day)
price reaction?

Data in pead_events_2026.csv was hand-collected from public web sources
(news reports and StatMuse price snapshots) because this environment has no
market-data API access. Prices marked in the notes as estimates carry a
confidence grade; rows with |reaction| < 1% are excluded (no direction
signal to condition on).
"""

import csv
from pathlib import Path

HERE = Path(__file__).parent


def load_events():
    with open(HERE / "pead_events_2026.csv", newline="") as f:
        return list(csv.DictReader(f))


def fmt_pct(x):
    return f"{float(x):+.1f}%"


def main():
    events = load_events()
    included = [e for e in events if e["included"] == "1"]
    excluded = [e for e in events if e["included"] == "0"]

    for e in included:
        r = float(e["reaction_pct"])
        d = float(e["drift_pct"])
        e["match"] = (r > 0) == (d > 0)

    matches = [e for e in included if e["match"]]

    print("=" * 88)
    print("LARGE-CAP PEAD DIRECTION BACKTEST - 2026 YTD (events through late June)")
    print("=" * 88)
    print(f"{'Ticker':<7}{'Report':<12}{'Reaction':>9}{'30d drift':>11}"
          f"{'Result':>10}   {'Confidence':<12}")
    print("-" * 88)
    for e in sorted(included, key=lambda x: x["report_date"]):
        res = "MATCH" if e["match"] else "REVERSAL"
        print(f"{e['ticker']:<7}{e['report_date']:<12}"
              f"{fmt_pct(e['reaction_pct']):>9}{fmt_pct(e['drift_pct']):>11}"
              f"{res:>10}   {e['confidence']:<12}")

    n, m = len(included), len(matches)
    print("-" * 88)
    print(f"\nOverall: drift matched the immediate reaction in {m}/{n} events "
          f"({100 * m / n:.0f}%)")

    neg = [e for e in included if float(e["reaction_pct"]) < 0]
    pos = [e for e in included if float(e["reaction_pct"]) > 0]
    neg_m = sum(e["match"] for e in neg)
    pos_m = sum(e["match"] for e in pos)
    print(f"  After a NEGATIVE reaction (sell-off): {neg_m}/{len(neg)} "
          f"kept drifting down ({100 * neg_m / len(neg):.0f}%)")
    print(f"  After a POSITIVE reaction (pop):      {pos_m}/{len(pos)} "
          f"kept drifting up   ({100 * pos_m / len(pos):.0f}%)")

    big = [e for e in included if abs(float(e["reaction_pct"])) >= 4.0]
    big_m = sum(e["match"] for e in big)
    print(f"  Big reactions only (|move| >= 4%):    {big_m}/{len(big)} matched "
          f"({100 * big_m / len(big):.0f}%)")

    hi = [e for e in included if e["confidence"] in ("high", "medium-high", "medium")]
    hi_m = sum(e["match"] for e in hi)
    print(f"  Excluding low-confidence rows:        {hi_m}/{len(hi)} matched "
          f"({100 * hi_m / len(hi):.0f}%)")

    jan = [e for e in included if e["report_date"] < "2026-04"]
    apr = [e for e in included if e["report_date"] >= "2026-04"]
    jan_m = sum(e["match"] for e in jan)
    apr_m = sum(e["match"] for e in apr)
    print(f"  Jan-Mar season (into Feb-Mar selloff): {jan_m}/{len(jan)} matched "
          f"({100 * jan_m / len(jan):.0f}%)")
    print(f"  Apr-Jun season (into Apr-May rally):   {apr_m}/{len(apr)} matched "
          f"({100 * apr_m / len(apr):.0f}%)")

    print(f"\nExcluded (reaction too small to define a direction, |r| < 1%): "
          f"{', '.join(e['ticker'] + ' ' + e['report_date'] for e in excluded)}")

    revs = [e for e in included if not e["match"]]
    print("\nReversals:")
    for e in sorted(revs, key=lambda x: x["report_date"]):
        print(f"  {e['ticker']} {e['report_date']}: reacted "
              f"{fmt_pct(e['reaction_pct'])}, then drifted "
              f"{fmt_pct(e['drift_pct'])} over the next ~30 days")


if __name__ == "__main__":
    main()
