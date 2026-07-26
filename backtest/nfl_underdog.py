"""Backtest: bet a fixed stake on the largest NFL underdog each regular-season week.

Data source: nflverse/nfldata `games.csv`, which carries closing betting lines
(`spread_line`, `away_moneyline`, `home_moneyline`) for every game since 1999.

Line conventions in that dataset, verified against known games:
  * `result`      = home_score - away_score
  * `spread_line` > 0 means the HOME team is favored by that many points,
                   < 0 means the AWAY team is favored.
  So the underdog is the away team when spread_line > 0, the home team when < 0,
  and the size of the underdog is abs(spread_line).
"""

from __future__ import annotations

import argparse
import io
import os
import urllib.request
from dataclasses import dataclass

import pandas as pd

GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
CACHE = os.path.join(os.path.dirname(__file__), "data", "games_2021_2025.csv")

COLUMNS = [
    "game_id", "season", "week", "gameday", "away_team", "away_score",
    "home_team", "home_score", "result", "spread_line", "away_moneyline",
    "home_moneyline", "away_spread_odds", "home_spread_odds",
]


def american_profit(stake: float, odds: float) -> float:
    """Profit (not including returned stake) on a winning American-odds bet."""
    return stake * odds / 100.0 if odds > 0 else stake * 100.0 / abs(odds)


def load_games(seasons: range, refresh: bool = False) -> pd.DataFrame:
    """Load regular-season games, from the local cache when available."""
    if os.path.exists(CACHE) and not refresh:
        games = pd.read_csv(CACHE)
    else:
        with urllib.request.urlopen(GAMES_URL, timeout=60) as resp:
            games = pd.read_csv(io.StringIO(resp.read().decode()))
        games = games[games.game_type == "REG"]
        games = games[games.season.isin(seasons)][COLUMNS]
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        games.to_csv(CACHE, index=False)

    games = games[games.season.isin(seasons)].copy()

    # A game with no line or no final score cannot be bet or settled.
    required = ["result", "spread_line", "away_moneyline", "home_moneyline"]
    missing = games[required].isna().any(axis=1)
    if missing.any():
        raise ValueError(f"{missing.sum()} games are missing lines or results")

    games["underdog"] = games.apply(
        lambda r: r.away_team if r.spread_line > 0 else r.home_team, axis=1
    )
    games["dog_is_away"] = games.spread_line > 0
    games["dog_points"] = games.spread_line.abs()
    games["dog_moneyline"] = games.apply(
        lambda r: r.away_moneyline if r.dog_is_away else r.home_moneyline, axis=1
    )
    games["dog_spread_odds"] = games.apply(
        lambda r: r.away_spread_odds if r.dog_is_away else r.home_spread_odds, axis=1
    )
    # Margin from the underdog's point of view: positive means the dog won.
    games["dog_margin"] = games.apply(
        lambda r: -r.result if r.dog_is_away else r.result, axis=1
    )
    return games


def pick_weekly_dogs(games: pd.DataFrame, split_ties: bool = True) -> pd.DataFrame:
    """Select the biggest underdog of each week.

    When several games are tied for the largest spread, the weekly stake is
    split evenly among them so exactly one unit is risked per week. With
    `split_ties=False` each tied dog gets a full unit instead.
    """
    picks = []
    for (season, week), wk in games.groupby(["season", "week"], sort=True):
        biggest = wk[wk.dog_points == wk.dog_points.max()].copy()
        biggest["n_tied"] = len(biggest)
        biggest["stake_frac"] = 1.0 / len(biggest) if split_ties else 1.0
        picks.append(biggest)
    return pd.concat(picks).sort_values(["season", "week", "game_id"]).reset_index(drop=True)


@dataclass
class Settled:
    outcome: str   # "win", "loss", or "push"
    profit: float  # net profit on the bet, stake excluded


def settle_moneyline(row, stake: float) -> Settled:
    """Underdog wins outright. An NFL tie is a push (stake returned)."""
    if row.dog_margin > 0:
        return Settled("win", american_profit(stake, row.dog_moneyline))
    if row.dog_margin == 0:
        return Settled("push", 0.0)
    return Settled("loss", -stake)


def settle_spread(row, stake: float) -> Settled:
    """Underdog covers: its margin plus the points it is getting beats zero."""
    against_spread = row.dog_margin + row.dog_points
    if against_spread > 0:
        return Settled("win", american_profit(stake, row.dog_spread_odds))
    if against_spread == 0:
        return Settled("push", 0.0)
    return Settled("loss", -stake)


def run(picks: pd.DataFrame, unit: float, market: str) -> pd.DataFrame:
    """Settle every pick and return the bet-by-bet ledger with an equity curve."""
    settle = settle_moneyline if market == "moneyline" else settle_spread
    rows = []
    for row in picks.itertuples():
        stake = unit * row.stake_frac
        result = settle(row, stake)
        rows.append({
            "season": row.season,
            "week": row.week,
            "gameday": row.gameday,
            "matchup": f"{row.away_team} @ {row.home_team}",
            "score": f"{int(row.away_score)}-{int(row.home_score)}",
            "underdog": row.underdog,
            "dog_points": row.dog_points,
            "odds": row.dog_moneyline if market == "moneyline" else row.dog_spread_odds,
            "n_tied": row.n_tied,
            "stake": stake,
            "outcome": result.outcome,
            "profit": result.profit,
        })
    ledger = pd.DataFrame(rows)
    ledger["cumulative_profit"] = ledger.profit.cumsum()
    return ledger


def summarize(ledger: pd.DataFrame) -> dict:
    staked = ledger.stake.sum()
    profit = ledger.profit.sum()
    wins = (ledger.outcome == "win").sum()
    losses = (ledger.outcome == "loss").sum()
    pushes = (ledger.outcome == "push").sum()

    # Worst peak-to-trough dip in the bankroll over the whole run.
    curve = ledger.cumulative_profit
    drawdown = (curve - curve.cummax()).min()

    # Longest run of consecutive losing bets; pushes do not break the streak.
    longest = streak = 0
    for outcome in ledger.outcome:
        if outcome == "loss":
            streak += 1
            longest = max(longest, streak)
        elif outcome == "win":
            streak = 0

    return {
        "bets": len(ledger),
        "weeks": ledger.groupby(["season", "week"]).ngroups,
        "record": f"{wins}-{losses}" + (f"-{pushes}" if pushes else ""),
        "win_rate": wins / (wins + losses) if wins + losses else float("nan"),
        "staked": staked,
        "profit": profit,
        "roi": profit / staked if staked else float("nan"),
        "max_drawdown": drawdown,
        "longest_losing_streak": longest,
    }


def format_report(ledgers: dict[str, pd.DataFrame], unit: float) -> str:
    out = [
        "=" * 78,
        f"Betting ${unit:,.0f} on the largest NFL underdog each week",
        "Regular seasons 2021-2025  |  closing lines from nflverse/nfldata",
        "=" * 78,
    ]

    for market, ledger in ledgers.items():
        s = summarize(ledger)
        label = "MONEYLINE (dog wins outright)" if market == "moneyline" \
            else "AGAINST THE SPREAD (dog covers)"
        out += [
            "",
            label,
            "-" * 78,
            f"  Bets placed         {s['bets']} across {s['weeks']} weeks",
            f"  Record              {s['record']}   ({s['win_rate']:.1%})",
            f"  Total staked        ${s['staked']:,.2f}",
            f"  Net profit          ${s['profit']:,.2f}",
            f"  ROI                 {s['roi']:+.2%}",
            f"  Max drawdown        ${s['max_drawdown']:,.2f}",
            f"  Longest losing run  {s['longest_losing_streak']} bets",
            "",
            "  By season:",
            f"    {'season':<8}{'record':<12}{'staked':>12}{'profit':>12}{'roi':>10}",
        ]
        for season, grp in ledger.groupby("season"):
            ss = summarize(grp)
            out.append(
                f"    {season:<8}{ss['record']:<12}${ss['staked']:>10,.0f}"
                f"{ss['profit']:>+12,.2f}{ss['roi']:>+10.1%}"
            )

    ml = ledgers["moneyline"]
    hits = ml[ml.outcome == "win"].nlargest(10, "profit")
    out += [
        "",
        "Biggest moneyline hits",
        "-" * 78,
        f"  {'season/wk':<11}{'underdog':<10}{'line':>7}{'odds':>8}  {'matchup':<12}"
        f"{'score':>9}{'profit':>11}",
    ]
    for r in hits.itertuples():
        out.append(
            f"  {str(r.season) + ' wk' + str(r.week):<11}{r.underdog:<10}"
            f"{'+' + format(r.dog_points, 'g'):>7}{'+' + str(int(r.odds)):>8}"
            f"  {r.matchup:<12}{r.score:>9}{r.profit:>+11,.2f}"
        )
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--unit", type=float, default=100.0, help="stake per week")
    p.add_argument("--start", type=int, default=2021)
    p.add_argument("--end", type=int, default=2025)
    p.add_argument("--refresh", action="store_true", help="re-download source data")
    p.add_argument("--no-split-ties", action="store_true",
                   help="bet a full unit on each tied dog instead of splitting")
    p.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "results"))
    args = p.parse_args()

    seasons = range(args.start, args.end + 1)
    games = load_games(seasons, refresh=args.refresh)
    picks = pick_weekly_dogs(games, split_ties=not args.no_split_ties)

    ledgers = {m: run(picks, args.unit, m) for m in ("moneyline", "spread")}
    report = format_report(ledgers, args.unit)
    print(report)

    os.makedirs(args.outdir, exist_ok=True)
    for market, ledger in ledgers.items():
        ledger.to_csv(os.path.join(args.outdir, f"bets_{market}.csv"), index=False)
    with open(os.path.join(args.outdir, "summary.txt"), "w") as fh:
        fh.write(report + "\n")


if __name__ == "__main__":
    main()
