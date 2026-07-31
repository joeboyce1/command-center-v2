"""Does a bye week beat the number?

Two questions, kept separate:

  1. The underdog angle -- how do underdogs do when they are off a bye, and
     when the favourite is off a bye?
  2. The side-agnostic angle -- back whichever team is off a bye, favourite or
     underdog, and see whether that beats the closing line.

A "bye" here is 12-16 days since the team's previous game. The rest-day
distribution is cleanly bimodal (6-9 days for a normal week, 13-15 for a bye),
so the threshold is not a judgement call. Layoffs over 16 days are bowls and
other oddities and are reported separately rather than mixed in.

Usage:  python cfb_underdog_backtest/bye_analysis.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from backtest import (  # noqa: E402
    DEFAULT_SPREAD_PRICE, STAKE, Cell, headline, load, payout, render,
    tabulate, tier, venue,
)

BYE_MIN, BYE_MAX = 12, 16
NORMAL_MIN, NORMAL_MAX = 5, 9


def rest_state(days: float | None) -> str | None:
    if days is None:
        return None
    if NORMAL_MIN <= days <= NORMAL_MAX:
        return "normal"
    if BYE_MIN <= days <= BYE_MAX:
        return "bye"
    if days < NORMAL_MIN:
        return "short"
    if days <= 11:
        return "extra"
    return "layoff"


def dog_state(game: dict) -> str | None:
    return rest_state(game["dog_rest"])


def fav_state(game: dict) -> str | None:
    return rest_state(game["fav_rest"])


def matchup(game: dict) -> str | None:
    """The rest matchup, restricted to the clean bye-vs-normal comparisons."""
    dog, fav = dog_state(game), fav_state(game)
    if dog is None or fav is None:
        return None
    if dog == "bye" and fav == "normal":
        return "a. dog off a bye, fav normal"
    if dog == "normal" and fav == "bye":
        return "b. fav off a bye, dog normal"
    if dog == "bye" and fav == "bye":
        return "c. both off a bye"
    if dog == "normal" and fav == "normal":
        return "d. neither off a bye"
    return None


# --- side-agnostic bets: back whichever team is off the bye ----------------

def bye_team_ats(game: dict) -> tuple[float, str] | None:
    """Back the team off a bye against the spread, dog or favourite."""
    dog, fav = dog_state(game), fav_state(game)
    if game["dog_line"] is None or game["dog_source"] != "spread":
        return None
    if dog == "bye" and fav == "normal":
        margin, line, price = game["dog_margin"], game["dog_line"], game["dog_spread_price"]
    elif fav == "bye" and dog == "normal":
        margin, line, price = -game["dog_margin"], -game["dog_line"], game["fav_spread_price"]
    else:
        return None
    if price is None or abs(price) < 100:
        price = DEFAULT_SPREAD_PRICE
    result = margin + line
    if result > 0:
        return payout(price), "win"
    if result < 0:
        return -STAKE, "loss"
    return 0.0, "push"


def bye_team_ml(game: dict) -> tuple[float, str] | None:
    """Back the team off a bye to win outright."""
    dog, fav = dog_state(game), fav_state(game)
    if game["n_books_ml"] < 1:
        return None
    if dog == "bye" and fav == "normal":
        price, margin = game["dog_ml"], game["dog_margin"]
    elif fav == "bye" and dog == "normal":
        price, margin = game["fav_ml"], -game["dog_margin"]
    else:
        return None
    price = float(price) if price not in (None, "") else None
    if price is None:
        return None
    if margin > 0:
        return payout(price), "win"
    if margin < 0:
        return -STAKE, "loss"
    return 0.0, "push"


def bye_side(game: dict) -> str | None:
    dog, fav = dog_state(game), fav_state(game)
    if dog == "bye" and fav == "normal":
        return "underdog off the bye"
    if fav == "bye" and dog == "normal":
        return "favourite off the bye"
    return None


def bye_venue(game: dict) -> str | None:
    """Was the bye team at home or on the road?"""
    side = bye_side(game)
    if side is None:
        return None
    if game["neutral"]:
        return "bye team at a neutral site"
    dog_at_home = game["dog"] == "home"
    bye_at_home = dog_at_home if side.startswith("underdog") else not dog_at_home
    return "bye team at home" if bye_at_home else "bye team on the road"


def bye_line_bucket(game: dict) -> str | None:
    if bye_side(game) is None or game["dog_line"] is None:
        return None
    line = game["dog_line"]
    tag = "getting" if bye_side(game).startswith("underdog") else "laying"
    for hi, label in ((3.0, "0-3"), (7.0, "3.5-7"), (14.0, "7.5-14")):
        if line <= hi:
            return f"bye team {tag} {label}"
    return f"bye team {tag} 14+"


def season_table(games: list[dict], bet, title: str) -> None:
    print()
    print(title)
    print(f"{'season':<10}{'bets':>7}{'W-L-P':>14}{'win%':>8}{'P&L $':>11}{'ROI':>9}")
    print("-" * 87)
    subset = [g for g in games if bet(g)]
    winning = seasons = 0
    for season in sorted({g["season"] for g in subset}):
        cell = headline([g for g in subset if g["season"] == season], bet)
        if not cell.n:
            continue
        seasons += 1
        winning += cell.pnl > 0
        print(f"{season:<10}{cell.n:>7}{f'{cell.win}-{cell.loss}-{cell.push}':>14}"
              f"{cell.win_pct:>7.1%}{cell.pnl:>11,.0f}{cell.roi:>9.1%}")
    total = headline(subset, bet)
    print(f"{'ALL':<10}{total.n:>7}{f'{total.win}-{total.loss}-{total.push}':>14}"
          f"{total.win_pct:>7.1%}{total.pnl:>11,.0f}{total.roi:>9.1%}   t={total.tstat:.2f}")
    print(f"profitable in {winning} of {seasons} seasons")


def split(games: list[dict], bet, label: str, cutoff: int = 2019) -> None:
    early = headline([g for g in games if g["season"] < cutoff], bet)
    late = headline([g for g in games if g["season"] >= cutoff], bet)
    print(f"{label:<40}{early.n:>7,}{early.roi:>9.1%}{late.n:>9,}{late.roi:>9.1%}")


def main() -> int:
    from backtest import ats_bet, ml_bet

    games = load(1, fbs_only=True)
    byes = sum(1 for g in games if dog_state(g) == "bye" or fav_state(g) == "bye")
    print("bye = 12-16 days since the team's last game; normal = 5-9 days")
    print(f"FBS games in the sample          : {len(games):,}")
    print(f"  with at least one team off a bye: {byes:,}")

    print()
    print("=" * 87)
    print("  1. THE UNDERDOG ANGLE: betting the dog, split by who was rested")
    print("=" * 87)
    order = sorted(tabulate(games, ats_bet, matchup))
    render("underdog ATS, by rest matchup", tabulate(games, ats_bet, matchup), order=order)
    render("underdog moneyline, by rest matchup", tabulate(games, ml_bet, matchup),
           order=sorted(tabulate(games, ml_bet, matchup)))

    print()
    print("=" * 87)
    print("  2. THE SIDE-AGNOSTIC ANGLE: back whoever is off the bye")
    print("=" * 87)
    total = headline(games, bye_team_ats)
    print(f"\nteam off a bye, ATS: {total.n:,} bets, "
          f"{total.win}-{total.loss}-{total.push} ({total.win_pct:.1%}), "
          f"${total.pnl:,.0f}, ROI {total.roi:.1%}, t={total.tstat:.2f}")
    total_ml = headline(games, bye_team_ml)
    print(f"team off a bye, ML : {total_ml.n:,} bets, "
          f"{total_ml.win}-{total_ml.loss}-{total_ml.push} ({total_ml.win_pct:.1%}), "
          f"${total_ml.pnl:,.0f}, ROI {total_ml.roi:.1%}, t={total_ml.tstat:.2f}")

    for title, key in (
        ("bye team ATS, favourite or underdog", bye_side),
        ("bye team ATS, by venue", bye_venue),
        ("bye team ATS, by size of the line", bye_line_bucket),
        ("bye team ATS, by tier", lambda g: (
            f"bye team is {tier(g['dog_conference'] if bye_side(g).startswith('underdog') else g['fav_conference'])}"
            if bye_side(g) else None)),
        ("bye team ATS, by conference", lambda g: (
            g["dog_conference"] if bye_side(g).startswith("underdog") else g["fav_conference"]
        ) if bye_side(g) else None),
    ):
        render(title, tabulate(games, bye_team_ats, key),
               order=sorted(tabulate(games, bye_team_ats, key)) if "conference" not in title else None,
               min_n=60 if "conference" in title else 0)

    render("bye team moneyline, favourite or underdog",
           tabulate(games, bye_team_ml, bye_side), order=sorted(["underdog off the bye", "favourite off the bye"]))

    print()
    print("=" * 87)
    print("  3. DOES IT HOLD UP?")
    print("=" * 87)
    season_table(games, bye_team_ats, "backing the team off a bye, ATS, season by season")

    print()
    print(f"{'cut':<40}{'2006-18 n':>7}{'ROI':>9}{'2019-25 n':>9}{'ROI':>9}")
    print("-" * 87)
    split(games, bye_team_ats, "team off a bye, ATS")
    split(games, bye_team_ml, "team off a bye, ML")
    split(games, lambda g: bye_team_ats(g) if bye_side(g) == "underdog off the bye" else None,
          "underdog off a bye, ATS")
    split(games, lambda g: bye_team_ats(g) if bye_side(g) == "favourite off the bye" else None,
          "favourite off a bye, ATS")
    split(games, ats_bet, "every underdog, ATS (baseline)")

    print()
    print("=" * 87)
    print("  4. INSIDE THE ONE CELL THAT BREAKS EVEN: underdog off a bye")
    print("=" * 87)
    dog_bye = [g for g in games if bye_side(g) == "underdog off the bye"]
    print(f"{'sub-cut':<34}{'bets':>6}{'cover%':>9}{'P&L $':>10}{'ROI':>9}{'t':>7}")
    print("-" * 87)
    subcuts = [
        ("all", lambda g: True),
        ("at home", lambda g: venue(g) == "home dog"),
        ("on the road", lambda g: venue(g) == "road dog"),
        ("getting +0.5 to +3", lambda g: g["dog_line"] and g["dog_line"] <= 3),
        ("getting +3.5 to +7", lambda g: g["dog_line"] and 3.5 <= g["dog_line"] <= 7),
        ("getting +7.5 to +14", lambda g: g["dog_line"] and 7.5 <= g["dog_line"] <= 14),
        ("getting +14.5 or more", lambda g: g["dog_line"] and g["dog_line"] >= 14.5),
        ("P5 underdog", lambda g: tier(g["dog_conference"]) == "P5"),
        ("G5 underdog", lambda g: tier(g["dog_conference"]) == "G5"),
        ("conference game", lambda g: g["conf_game"]),
        ("non-conference game", lambda g: not g["conf_game"]),
    ]
    for label, pred in subcuts:
        cell = headline([g for g in dog_bye if pred(g)], bye_team_ats)
        if not cell.n:
            continue
        print(f"{label:<34}{cell.n:>6}{cell.win_pct:>9.1%}{cell.pnl:>10,.0f}"
              f"{cell.roi:>9.1%}{cell.tstat:>7.2f}")

    print()
    print("long layoffs (17+ days, mostly bowls) are excluded above:")
    long_dog = [g for g in games if dog_state(g) == "layoff"]
    cell = headline(long_dog, ats_bet)
    print(f"  underdog off a 17+ day layoff, ATS: {cell.n} bets, "
          f"{cell.win_pct:.1%} cover, ROI {cell.roi:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
