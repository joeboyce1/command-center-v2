"""Sanity-check the ESPN-derived consensus lines against a second source.

The ESPN odds feed does not label its numbers "closing" -- it stores the last
line each book had up. To check that this really is the closing number (and
that the home/away side resolution in build_dataset.py is correct), compare
against sportsbookreviewsonline.com closing lines for 2014-2019, mirrored in
jackschooley/cfb-betting.

Games are matched on (season, month-day, home score, away score), which avoids
having to reconcile two different sets of team-name spellings. Only unique
matches are used.

Usage:  python cfb_underdog_backtest/validate_lines.py
"""

from __future__ import annotations

import collections
import csv
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
GAMES = ROOT / "data" / "processed" / "games.csv"


def load_ours() -> dict[tuple, dict]:
    index = collections.defaultdict(list)
    with open(GAMES, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (
                int(row["season"]),
                row["date"][5:7] + row["date"][8:10],
                int(row["home_points"]),
                int(row["away_points"]),
            )
            index[key].append(row)
    return index


def load_sbr(year: int) -> list[dict]:
    with open(RAW / "sbr" / f"{year}.csv", newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    ours = load_ours()
    spread_diffs: list[float] = []
    ml_diffs: list[float] = []
    matched = exact_spread = side_agree = 0
    unmatched = ambiguous = 0

    for year in range(2014, 2020):
        for row in load_sbr(year):
            try:
                date = row["date"].zfill(4)
                key = (year, date, int(row["home_score"]), int(row["away_score"]))
            except (ValueError, KeyError):
                continue
            hits = ours.get(key, [])
            if not hits:
                unmatched += 1
                continue
            if len(hits) > 1:
                ambiguous += 1
                continue
            mine = hits[0]
            if not mine["spread_home"]:
                continue
            try:
                sbr_spread = float(row["spread"])
            except (TypeError, ValueError):
                continue

            matched += 1
            # SBR quotes a positive number when the home team is favoured;
            # build_dataset.py quotes the home side, so the signs are opposite.
            mine_spread = float(mine["spread_home"])
            diff = mine_spread - (-sbr_spread)
            spread_diffs.append(diff)
            if abs(diff) < 1e-9:
                exact_spread += 1
            if (mine_spread < 0) == (sbr_spread > 0):
                side_agree += 1

            dog_side_ml = row["home_ml"] if mine["dog"] == "home" else row["away_ml"]
            if mine["dog_ml"] and dog_side_ml:
                try:
                    a, b = float(mine["dog_ml"]), float(dog_side_ml)
                except ValueError:
                    continue
                # longshot quotes above +2000 are noisy in both files and would
                # swamp the average, so compare only bettable prices
                if abs(a) <= 2000 and abs(b) <= 2000:
                    ml_diffs.append(a - b)

    print(f"SBR games matched to our dataset : {matched:,}")
    print(f"  no score/date match            : {unmatched:,}")
    print(f"  ambiguous (same date+score)    : {ambiguous:,}")
    if not matched:
        return 1

    print()
    print(f"favourite side agrees            : {side_agree / matched:6.2%}")
    print(f"spread identical to the decimal  : {exact_spread / matched:6.2%}")
    within = lambda t: sum(abs(d) <= t for d in spread_diffs) / len(spread_diffs)
    print(f"spread within 0.5 pt             : {within(0.5):6.2%}")
    print(f"spread within 1.0 pt             : {within(1.0):6.2%}")
    print(f"mean signed spread difference    : {statistics.mean(spread_diffs):+.3f} pts")
    print(f"median abs spread difference     : {statistics.median(abs(d) for d in spread_diffs):.3f} pts")

    if ml_diffs:
        print()
        print(f"underdog moneylines compared     : {len(ml_diffs):,}")
        print(f"median abs difference            : {statistics.median(abs(d) for d in ml_diffs):.0f} cents")
        print(f"within 20 cents                  : {sum(abs(d) <= 20 for d in ml_diffs) / len(ml_diffs):6.2%}")
        print(f"mean signed difference           : {statistics.mean(ml_diffs):+.1f} cents "
              f"(positive = our price is more generous)")

    replicate_small_dogs()
    return 0


def replicate_small_dogs() -> None:
    """Re-run the headline moneyline cut on the raw SBR file alone.

    The strongest result in the backtest -- small road underdogs on the
    moneyline -- depends on getting home/away right. SBR labels home and away
    explicitly, so recomputing the cut straight from that file is an
    independent check on both the side resolution and the result itself.
    """
    cells: dict[str, list] = collections.defaultdict(lambda: [0, 0, 0.0])
    for year in range(2014, 2020):
        for row in load_sbr(year):
            try:
                spread = float(row["spread"])
                home_score, away_score = int(row["home_score"]), int(row["away_score"])
                home_ml, away_ml = float(row["home_ml"]), float(row["away_ml"])
            except (TypeError, ValueError):
                continue
            if spread == 0 or abs(spread) > 3:
                continue
            dog_is_home = spread < 0  # SBR quotes a positive number when home is favoured
            price = home_ml if dog_is_home else away_ml
            won = (home_score > away_score) if dog_is_home else (away_score > home_score)
            cell = cells["home dog of +3 or less" if dog_is_home else "road dog of +3 or less"]
            cell[0] += 1
            cell[1] += won
            cell[2] += 100.0 * (price / 100.0 if price > 0 else 100.0 / -price) if won else -100.0

    print()
    print("independent replication from the SBR file alone (2014-2019, moneyline):")
    for label, (n, wins, pnl) in sorted(cells.items()):
        print(f"  {label:<24}{n:>5} bets{wins / n:>8.1%} won{pnl:>10,.0f}{pnl / (100 * n):>8.1%} ROI")


if __name__ == "__main__":
    sys.exit(main())
