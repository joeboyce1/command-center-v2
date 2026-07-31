"""Backtest: bet every college football underdog, on the moneyline and ATS.

Flat $100 a game, priced at the consensus closing line built by
build_dataset.py. Spread bets use the consensus closing price where the books
published one and -110 otherwise; moneyline bets use the consensus closing
price. Pushes return the stake.

ROI is profit divided by total amount risked. The t-stat is on the mean return
per bet; with this many slices, treat anything under ~2.5 as noise.

Usage:  python cfb_underdog_backtest/backtest.py [--min-books N] [--csv out.csv]
"""

from __future__ import annotations

import argparse
import collections
import csv
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GAMES = ROOT / "data" / "processed" / "games.csv"
STAKE = 100.0
DEFAULT_SPREAD_PRICE = -110.0

POWER = {"ACC", "Big Ten", "Big 12", "Pac-12", "SEC", "FBS Independents"}
GROUP_OF_FIVE = {
    "American Athletic", "Conference USA", "Mid-American", "Mountain West",
    "Sun Belt", "Western Athletic",
}


def payout(odds: float) -> float:
    """Net profit on a winning STAKE-sized bet at an American price."""
    return STAKE * (odds / 100.0 if odds > 0 else 100.0 / -odds)


def num(value: str) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load(min_books: int = 1, fbs_only: bool = False, max_ml: float | None = None) -> list[dict]:
    games = []
    with open(GAMES, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if fbs_only and not (row["home_division"] == "fbs" and row["away_division"] == "fbs"):
                continue
            if max_ml is not None:
                dog_ml = num(row["dog_ml"])
                if dog_ml is not None and dog_ml > max_ml:
                    row["dog_ml"] = ""  # too long to be a real, bettable price
            row["season"] = int(row["season"])
            row["dog_margin"] = float(row["dog_margin"])
            row["dog_line"] = num(row["dog_line"])
            row["dog_ml"] = num(row["dog_ml"])
            row["dog_spread_price"] = num(row["dog_spread_price"])
            row["fav_spread_price"] = num(row["fav_spread_price"])
            row["dog_line_open"] = num(row["dog_line_open"])
            row["dog_rest"] = num(row["dog_rest"])
            row["fav_rest"] = num(row["fav_rest"])
            row["n_books_spread"] = int(num(row["n_books_spread"]) or 0)
            row["n_books_ml"] = int(num(row["n_books_ml"]) or 0)
            row["neutral"] = row["neutral_site"].upper() == "TRUE"
            row["conf_game"] = row["conference_game"].upper() == "TRUE"
            row["dog_division"] = row[f"{row['dog']}_division"]
            row["fav_division"] = row["away_division"] if row["dog"] == "home" else row["home_division"]
            row["min_books"] = max(row["n_books_spread"], row["n_books_ml"])
            if row["min_books"] < min_books:
                continue
            games.append(row)
    return games


def ats_bet(game: dict) -> tuple[float, str] | None:
    """Take the underdog plus the points. Returns (profit, outcome)."""
    if game["dog_line"] is None or game["dog_source"] != "spread":
        return None
    result = game["dog_margin"] + game["dog_line"]
    price = game["dog_spread_price"]
    if price is None or abs(price) < 100:
        price = DEFAULT_SPREAD_PRICE
    if result > 0:
        return payout(price), "win"
    if result < 0:
        return -STAKE, "loss"
    return 0.0, "push"


def ml_bet(game: dict) -> tuple[float, str] | None:
    """Take the underdog to win outright."""
    if game["dog_ml"] is None or game["n_books_ml"] < 1:
        return None
    if game["dog_margin"] > 0:
        return payout(game["dog_ml"]), "win"
    if game["dog_margin"] < 0:
        return -STAKE, "loss"
    return 0.0, "push"  # ties are effectively extinct in modern CFB


class Cell:
    __slots__ = ("n", "win", "loss", "push", "pnl", "sq")

    def __init__(self) -> None:
        self.n = self.win = self.loss = self.push = 0
        self.pnl = self.sq = 0.0

    def add(self, profit: float, outcome: str) -> None:
        self.n += 1
        self.pnl += profit
        self.sq += profit * profit
        setattr(self, outcome, getattr(self, outcome) + 1)

    @property
    def roi(self) -> float:
        return self.pnl / (STAKE * self.n) if self.n else 0.0

    @property
    def win_pct(self) -> float:
        decided = self.win + self.loss
        return self.win / decided if decided else 0.0

    @property
    def tstat(self) -> float:
        if self.n < 2:
            return 0.0
        mean = self.pnl / self.n
        var = (self.sq - self.n * mean * mean) / (self.n - 1)
        if var <= 0:
            return 0.0
        return mean / math.sqrt(var / self.n)


def tabulate(games: list[dict], bet, key) -> dict[str, Cell]:
    cells: dict[str, Cell] = collections.defaultdict(Cell)
    for game in games:
        outcome = bet(game)
        if outcome is None:
            continue
        label = key(game)
        if label is None:
            continue
        labels = label if isinstance(label, list) else [label]
        for item in labels:
            cells[item].add(*outcome)
    return cells


def render(title: str, cells: dict[str, Cell], order=None, min_n: int = 0,
           rows_out: list | None = None, market: str = "") -> None:
    print()
    print(title)
    print(f"{'segment':<28}{'bets':>7}{'W-L-P':>16}{'win%':>8}{'P&L $':>12}{'ROI':>9}{'t':>7}")
    print("-" * 87)
    keys = order or sorted(cells, key=lambda k: -cells[k].n)
    for key in keys:
        cell = cells.get(key)
        if cell is None or cell.n < min_n:
            continue
        record = f"{cell.win}-{cell.loss}-{cell.push}"
        print(f"{str(key)[:27]:<28}{cell.n:>7}{record:>16}{cell.win_pct:>7.1%}"
              f"{cell.pnl:>12,.0f}{cell.roi:>8.1%}{cell.tstat:>7.2f}")
        if rows_out is not None:
            rows_out.append({
                "market": market, "cut": title, "segment": key, "bets": cell.n,
                "wins": cell.win, "losses": cell.loss, "pushes": cell.push,
                "win_pct": round(cell.win_pct, 4), "pnl": round(cell.pnl, 2),
                "roi": round(cell.roi, 4), "t_stat": round(cell.tstat, 2),
            })


def line_bucket(game: dict) -> str | None:
    line = game["dog_line"]
    if line is None:
        return None
    for hi, label in ((3.0, "a. +0.5 to +3"), (7.0, "b. +3.5 to +7"),
                      (10.0, "c. +7.5 to +10"), (14.0, "d. +10.5 to +14"),
                      (21.0, "e. +14.5 to +21"), (28.0, "f. +21.5 to +28"),
                      (35.0, "g. +28.5 to +35")):
        if line <= hi:
            return label
    return "h. +35 or more"


def tier(conference: str) -> str:
    if conference in POWER:
        return "P5"
    if conference in GROUP_OF_FIVE:
        return "G5"
    return "FCS/other"


def venue(game: dict) -> str:
    if game["neutral"]:
        return "neutral site"
    return "home dog" if game["dog"] == "home" else "road dog"


def week_bucket(game: dict) -> str:
    if game["season_type"] != "regular":
        return "e. bowls / playoff"
    try:
        week = int(float(game["week"]))
    except (TypeError, ValueError):
        return "d. week 11+"
    if week <= 2:
        return "a. weeks 1-2"
    if week <= 5:
        return "b. weeks 3-5"
    if week <= 10:
        return "c. weeks 6-10"
    return "d. week 11+"


def rest_bucket(game: dict) -> str | None:
    """Rest advantage: a dog off a bye against a favourite on a short week."""
    dog, fav = game["dog_rest"], game["fav_rest"]
    if dog is None or fav is None:
        return None
    edge = dog - fav
    if edge >= 5:
        return "a. dog rested 5+ more days"
    if edge >= 1:
        return "b. dog rested 1-4 more days"
    if edge == 0:
        return "c. equal rest"
    if edge >= -4:
        return "d. favourite rested 1-4 more"
    return "e. favourite rested 5+ more"


def move_bucket(game: dict) -> str | None:
    """Did the closing line give the dog more points than the opener did?"""
    if game["dog_line"] is None or game["dog_line_open"] is None:
        return None
    move = game["dog_line"] - game["dog_line_open"]
    if move <= -1:
        return "a. dog gave back 1+ pts (bet on dog)"
    if move < 0:
        return "b. dog gave back 0.5 pt"
    if move == 0:
        return "c. line never moved"
    if move < 1:
        return "d. dog gained 0.5 pt"
    return "e. dog gained 1+ pts (bet on fav)"


def headline(games: list[dict], bet) -> Cell:
    total = Cell()
    for game in games:
        outcome = bet(game)
        if outcome is not None:
            total.add(*outcome)
    return total


def robustness(all_games: list[dict]) -> None:
    """The moneyline P&L is long-tailed, so show how it moves with the universe."""
    print()
    print("=" * 87)
    print("  ROBUSTNESS: how the headline moves with the sample")
    print("=" * 87)
    print(f"{'universe':<40}{'ML bets':>9}{'ML ROI':>9}{'ATS bets':>10}{'ATS ROI':>9}")
    print("-" * 87)
    universes = [
        ("everything with a closing line", load(1)),
        ("FBS vs FBS only", load(1, fbs_only=True)),
        ("FBS vs FBS, 4+ book quotes", load(4, fbs_only=True)),
        ("FBS vs FBS, dog priced +1000 or shorter", load(1, fbs_only=True, max_ml=1000)),
        ("FBS vs FBS, dog priced +500 or shorter", load(1, fbs_only=True, max_ml=500)),
    ]
    for label, subset in universes:
        ml, ats = headline(subset, ml_bet), headline(subset, ats_bet)
        print(f"{label:<40}{ml.n:>9,}{ml.roi:>9.1%}{ats.n:>10,}{ats.roi:>9.1%}")

    # How much of the moneyline P&L rides on a handful of tickets?
    print()
    print("moneyline P&L concentration (FBS vs FBS):")
    fbs = load(1, fbs_only=True)
    profits = sorted(((ml_bet(g)[0], g) for g in fbs if ml_bet(g)), key=lambda pair: pair[0])
    total = sum(p for p, _ in profits)
    top5 = sum(p for p, _ in profits[-5:])
    print(f"  total P&L over {len(profits):,} bets          : ${total:,.0f}")
    print(f"  P&L from the 5 biggest winners      : ${top5:,.0f}")
    print(f"  P&L with those 5 removed            : ${total - top5:,.0f}"
          f"  (ROI {(total - top5) / (STAKE * (len(profits) - 5)):.1%})")
    print("  the five:")
    for profit, game in reversed(profits[-5:]):
        print(f"    {game['season']} {game['dog_team'][:20]:<20} +{game['dog_line'] or 0:<5.1f}"
              f" at +{game['dog_ml']:<7.0f} -> ${profit:,.0f} ({game['n_books_ml']} books)")


def out_of_sample(games: list[dict], bet, key, title: str, split: int = 2019) -> None:
    early = [g for g in games if g["season"] < split]
    late = [g for g in games if g["season"] >= split]
    cells_early = tabulate(early, bet, key)
    cells_late = tabulate(late, bet, key)
    print()
    print(title)
    print(f"{'segment':<28}{'2006-2018 n':>13}{'ROI':>9}{'2019-2025 n':>14}{'ROI':>9}")
    print("-" * 87)
    for label in sorted(set(cells_early) | set(cells_late)):
        a, b = cells_early.get(label, Cell()), cells_late.get(label, Cell())
        if a.n + b.n < 100:
            continue
        print(f"{str(label)[:27]:<28}{a.n:>13,}{a.roi:>9.1%}{b.n:>14,}{b.roi:>9.1%}")


def fav_ml_bet(game: dict) -> tuple[float, str] | None:
    """The mirror of ml_bet: lay the favourite. Shown only for context."""
    price = num(str(game["fav_ml"])) if game["fav_ml"] else None
    if price is None or game["n_books_ml"] < 1:
        return None
    if game["dog_margin"] < 0:
        return payout(price), "win"
    if game["dog_margin"] > 0:
        return -STAKE, "loss"
    return 0.0, "push"


def spotlight(games: list[dict], bet, predicate, title: str) -> None:
    """Season-by-season view of one cut, to see whether it is a real edge."""
    subset = [g for g in games if predicate(g)]
    print()
    print(title)
    print(f"{'season':<10}{'bets':>7}{'W-L-P':>14}{'win%':>8}{'P&L $':>11}{'ROI':>9}")
    print("-" * 87)
    winning_seasons = seasons = 0
    for season in sorted({g["season"] for g in subset}):
        cell = headline([g for g in subset if g["season"] == season], bet)
        if not cell.n:
            continue
        seasons += 1
        winning_seasons += cell.pnl > 0
        record = f"{cell.win}-{cell.loss}-{cell.push}"
        print(f"{season:<10}{cell.n:>7}{record:>14}{cell.win_pct:>7.1%}"
              f"{cell.pnl:>11,.0f}{cell.roi:>9.1%}")
    total = headline(subset, bet)
    record = f"{total.win}-{total.loss}-{total.push}"
    print(f"{'ALL':<10}{total.n:>7}{record:>14}{total.win_pct:>7.1%}"
          f"{total.pnl:>11,.0f}{total.roi:>9.1%}   t={total.tstat:.2f}")
    print(f"profitable in {winning_seasons} of {seasons} seasons")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-books", type=int, default=1,
                        help="require at least this many book quotes per game")
    parser.add_argument("--fbs-only", action="store_true", default=True)
    parser.add_argument("--all-divisions", dest="fbs_only", action="store_false",
                        help="include FBS-vs-FCS and FCS-vs-FCS games")
    parser.add_argument("--max-ml", type=float, default=None,
                        help="ignore moneylines longer than this American price")
    parser.add_argument("--csv", type=pathlib.Path, default=ROOT / "results" / "segments.csv")
    args = parser.parse_args()

    games = load(args.min_books, fbs_only=args.fbs_only, max_ml=args.max_ml)
    seasons = sorted({g["season"] for g in games})
    print(f"universe                         : "
          f"{'FBS vs FBS' if args.fbs_only else 'all divisions'}"
          f"{'' if args.max_ml is None else f', dog ML capped at +{args.max_ml:.0f}'}")
    print(f"games with a usable closing line : {len(games):,}  ({seasons[0]}-{seasons[-1]})")
    print(f"  ... with a moneyline           : {sum(1 for g in games if ml_bet(g)):,}")
    print(f"  ... with a spread              : {sum(1 for g in games if ats_bet(g)):,}")
    print(f"flat stake per bet               : ${STAKE:,.0f}")

    rows: list[dict] = []
    cuts = [
        ("every underdog", lambda g: "all underdogs"),
        ("by season", lambda g: g["season"]),
        ("by size of the underdog line", line_bucket),
        ("home / road / neutral", venue),
        ("by underdog's conference", lambda g: g["dog_conference"] or "(none)"),
        ("by favourite's conference", lambda g: g["fav_conference"] or "(none)"),
        ("by tier matchup (dog vs fav)", lambda g: f"{tier(g['dog_conference'])} dog vs {tier(g['fav_conference'])} fav"),
        ("conference vs non-conference", lambda g: "conference game" if g["conf_game"] else "non-conference"),
        ("by week", week_bucket),
        ("venue x line size", lambda g: f"{venue(g)} {line_bucket(g)}" if line_bucket(g) else None),
        ("rest advantage", rest_bucket),
        ("opening -> closing line move", move_bucket),
    ]

    for market, bet in (("MONEYLINE", ml_bet), ("SPREAD (ATS)", ats_bet)):
        print()
        print("=" * 87)
        print(f"  {market}: back the underdog")
        print("=" * 87)
        for title, key in cuts:
            order = None
            if title in ("by season", "by size of the underdog line", "by week",
                         "venue x line size", "rest advantage",
                         "opening -> closing line move"):
                order = sorted(tabulate(games, bet, key))
            render(title, tabulate(games, bet, key), order=order,
                   min_n=30 if "conference" in title or "tier" in title else 0,
                   rows_out=rows, market=market)

    print()
    print("=" * 87)
    print("  OUT OF SAMPLE: does a cut hold up in the second half of the sample?")
    print("=" * 87)
    out_of_sample(games, ats_bet, venue, "ATS, by venue")
    out_of_sample(games, ats_bet, line_bucket, "ATS, by line size")
    out_of_sample(games, ats_bet, lambda g: g["dog_conference"] or "(none)",
                  "ATS, by underdog conference")
    out_of_sample(games, ml_bet, venue, "Moneyline, by venue")
    out_of_sample(games, ml_bet, line_bucket, "Moneyline, by line size")
    out_of_sample(games, ats_bet, rest_bucket, "ATS, by rest advantage")

    print()
    print("=" * 87)
    print("  SPOTLIGHT: the cuts worth a second look, season by season")
    print("=" * 87)
    spotlight(games, ml_bet,
              lambda g: venue(g) == "road dog" and g["dog_line"] and g["dog_line"] <= 3,
              "Moneyline: road underdogs of +3 or less")
    spotlight(games, ats_bet,
              lambda g: venue(g) == "home dog" and g["dog_line"] and g["dog_line"] >= 14.5,
              "ATS: home underdogs of +14.5 or more")
    spotlight(games, ats_bet,
              lambda g: g["dog_rest"] is not None and g["fav_rest"] is not None
              and 1 <= g["fav_rest"] - g["dog_rest"] <= 4,
              "ATS: underdogs whose opponent had 1-4 days more rest")

    print()
    print("=" * 87)
    print("  MIRROR: what laying the favourite on the moneyline would have paid")
    print("=" * 87)
    render("favourite moneyline, by underdog line size",
           tabulate(games, fav_ml_bet, line_bucket),
           order=sorted(tabulate(games, fav_ml_bet, line_bucket)),
           rows_out=rows, market="FAVOURITE MONEYLINE")

    robustness(games)

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with open(args.csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nsegment table -> {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
