"""Turn the raw per-book line rows + schedules into one row per game.

The raw odds file has one row per (game, market, sportsbook, side). This script

  1. works out which side of each row is the home team (ESPN abbreviation ->
     ESPN team_id, checked against the row's home_team_id / away_team_id),
  2. collapses the books into a consensus number per game (median across books,
     with moneyline/spread prices averaged in decimal space so that the median
     is well behaved across the +100 / -100 boundary),
  3. joins the game result, conference, division, neutral-site and
     conference-game flags from the schedule files,
  4. labels the underdog and writes data/processed/games.csv.

Sign convention: ``spread_home`` is quoted from the home team's point of view,
so a negative number means the home team is favoured. ``dog_line`` is always
the positive number of points the underdog receives.

Usage:  python cfb_underdog_backtest/build_dataset.py
"""

from __future__ import annotations

import collections
import csv
import datetime
import gzip
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "games.csv"


def american_to_decimal(odds: float) -> float:
    """American price -> net decimal payout per unit staked."""
    return odds / 100.0 if odds > 0 else 100.0 / -odds


def decimal_to_american(dec: float) -> float:
    return round(100.0 * dec, 1) if dec >= 1.0 else round(-100.0 / dec, 1)


def median_price(prices: list[float]) -> float | None:
    """Median of American prices, taken in decimal space."""
    # A handful of source rows carry a price of 0, which is not a real quote.
    prices = [p for p in prices if p not in (0.0, None) and abs(p) >= 100]
    if not prices:
        return None
    return decimal_to_american(statistics.median(american_to_decimal(p) for p in prices))


def to_float(value: str) -> float | None:
    value = (value or "").strip()
    if not value or value.upper() in {"NA", "NULL", "NAN"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def letters(text: str) -> str:
    return "".join(ch for ch in text.upper() if ch.isalpha())


def lcs_length(a: str, b: str) -> int:
    prev = [0] * (len(b) + 1)
    for ch_a in a:
        cur = [0]
        for j, ch_b in enumerate(b):
            cur.append(prev[j] + 1 if ch_a == ch_b else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def side_from_abbr(abbr: str, away_name: str, home_name: str) -> str | None:
    """Decide whether a sportsbook's team code refers to the home or away team.

    The book codes are their own shorthand ("UTH" for Utah, "KNT" for Kent
    State), so they do not join to any ESPN abbreviation. But each row carries
    the matchup as "Away@Home", which turns this into a two-way choice: score
    the code against both names by longest common subsequence and take the
    better fit, breaking ties on the tighter (shorter-name) match.
    """
    code = letters(abbr)
    if not code:
        return None
    scores = {}
    for side, name in (("away", away_name), ("home", home_name)):
        target = letters(name)
        if not target:
            return None
        hit = lcs_length(code, target)
        scores[side] = (hit, hit / len(target))
    if scores["home"] == scores["away"]:
        return None
    return "home" if scores["home"] > scores["away"] else "away"


def load_schedules() -> dict[str, dict]:
    games = {}
    for path in sorted((RAW / "schedules").glob("*.csv")):
        with open(path, newline="", encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                games[row["game_id"].strip()] = row
    return games


Side = collections.namedtuple("Side", "home away")


def collect_lines() -> tuple[dict, collections.Counter]:
    """game_id -> {market: {"home": [(line, price)], "away": [...]}} + diagnostics."""
    per_game: dict[str, dict[str, dict[str, list]]] = collections.defaultdict(
        lambda: collections.defaultdict(lambda: {"home": [], "away": []})
    )
    stats = collections.Counter()
    seen: set[tuple] = set()
    quotes: dict[tuple, list] = collections.defaultdict(list)
    side_cache: dict[tuple, str | None] = {}

    with gzip.open(RAW / "cfb_line_odds.csv.gz", "rt", newline="") as handle:
        for row in csv.DictReader(handle):
            market = row["market_type"]
            if market not in ("spread", "money_line"):
                continue
            key = (
                row["game_id"], market, row["book"], row["abbr"],
                row["lines"], row["odds"],
            )
            if key in seen:  # the source file contains exact duplicate rows
                stats["duplicate_rows"] += 1
                continue
            seen.add(key)

            desc = row["game_desc"]
            if "@" not in desc:  # all-star exhibitions, no real home/away
                stats["no_matchup_desc"] += 1
                continue
            away_name, home_name = desc.split("@", 1)

            cache_key = (row["abbr"], desc)
            if cache_key not in side_cache:
                side_cache[cache_key] = side_from_abbr(row["abbr"], away_name, home_name)
            side = side_cache[cache_key]

            quotes[(row["game_id"], market, row["book"])].append(
                (side, to_float(row["lines"]), to_float(row["odds"]),
                 to_float(row["opening_lines"]))
            )

    for (game_id, market, _book), rows in quotes.items():
        sides = {side for side, _, _, _ in rows if side}
        if len(rows) == 2 and len(sides) == 1:
            # Both quotes matched the same team name: infer the other from it.
            known = sides.pop()
            other = "home" if known == "away" else "away"
            rows = [(side or other, line, price, opener)
                    for side, line, price, opener in rows]
            first, second = rows
            if first[0] == second[0]:  # genuinely ambiguous, drop this book
                stats["ambiguous_book_quote"] += 2
                continue
        for side, line, price, opener in rows:
            if side is None:
                stats["unresolved_side"] += 1
                continue
            stats["resolved_rows"] += 1
            per_game[game_id][market][side].append((line, price, opener))

    return per_game, stats


def rest_days(schedule: dict[str, dict]) -> dict[tuple[str, str], int]:
    """(game_id, 'home'|'away') -> days since that team's previous game."""
    by_team: dict[tuple, list] = collections.defaultdict(list)
    for game_id, game in schedule.items():
        date = game["start_date"][:10]
        if len(date) != 10:
            continue
        for side in ("home", "away"):
            by_team[(game["season"], game[f"{side}_team"])].append((date, game_id, side))

    out: dict[tuple[str, str], int] = {}
    for entries in by_team.values():
        entries.sort()
        for index in range(1, len(entries)):
            prev_date = datetime.date.fromisoformat(entries[index - 1][0])
            this_date = datetime.date.fromisoformat(entries[index][0])
            out[(entries[index][1], entries[index][2])] = (this_date - prev_date).days
    return out


def consensus(per_game: dict) -> dict[str, dict]:
    out = {}
    for game_id, markets in per_game.items():
        rec: dict[str, float | int | None] = {}

        spread = markets.get("spread")
        if spread:
            # pool both sides into a home-perspective view
            home_view = [v for v, _, _ in spread["home"] if v is not None]
            home_view += [-v for v, _, _ in spread["away"] if v is not None]
            if home_view:
                rec["spread_home"] = statistics.median(home_view)
                rec["n_books_spread"] = len(home_view)
                for side in ("home", "away"):
                    prices = [p for _, p, _ in spread[side] if p is not None]
                    rec[f"spread_price_{side}"] = median_price(prices)
            open_view = [o for _, _, o in spread["home"] if o is not None]
            open_view += [-o for _, _, o in spread["away"] if o is not None]
            if open_view:
                rec["spread_home_open"] = statistics.median(open_view)

        moneyline = markets.get("money_line")
        if moneyline:
            for side in ("home", "away"):
                prices = [p for _, p, _ in moneyline[side] if p is not None]
                rec[f"ml_{side}"] = median_price(prices)
            rec["n_books_ml"] = min(len(moneyline["home"]), len(moneyline["away"]))

        if rec:
            out[game_id] = rec
    return out


FIELDS = [
    "game_id", "season", "week", "season_type", "date", "neutral_site",
    "conference_game", "home_team", "away_team", "home_conference",
    "away_conference", "home_division", "away_division", "home_points",
    "away_points", "spread_home", "n_books_spread", "ml_home", "ml_away",
    "n_books_ml", "dog", "dog_team", "fav_team", "dog_conference",
    "fav_conference", "dog_line", "dog_line_open", "dog_spread_price", "dog_ml",
    "fav_ml", "dog_source", "dog_margin", "dog_rest", "fav_rest",
]


def main() -> int:
    per_game, stats = collect_lines()
    lines = consensus(per_game)
    schedule = load_schedules()
    rest = rest_days(schedule)

    print(f"line rows resolved to a side : {stats['resolved_rows']:,}")
    print(f"line rows with unmatched side: {stats['unresolved_side']:,}")
    print(f"ambiguous book quotes dropped: {stats['ambiguous_book_quote']:,}")
    print(f"exact duplicate rows skipped : {stats['duplicate_rows']:,}")
    print(f"games with any consensus line: {len(lines):,}")

    written = 0
    skipped = collections.Counter()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8", errors="replace") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()

        for game_id, rec in sorted(lines.items()):
            game = schedule.get(game_id)
            if game is None:
                skipped["no_schedule_row"] += 1
                continue
            hp, ap = to_float(game["home_points"]), to_float(game["away_points"])
            if hp is None or ap is None:
                skipped["not_completed"] += 1
                continue

            spread_home = rec.get("spread_home")
            ml_home, ml_away = rec.get("ml_home"), rec.get("ml_away")

            # Who is the underdog? The spread decides it; the moneyline is the
            # tie-breaker for pick'ems and for games with no spread on file.
            if spread_home is not None and spread_home != 0:
                dog = "home" if spread_home > 0 else "away"
                source = "spread"
            elif ml_home is not None and ml_away is not None and ml_home != ml_away:
                dog = "home" if ml_home > ml_away else "away"
                source = "moneyline"
            else:
                skipped["pickem_or_no_line"] += 1
                continue

            fav = "away" if dog == "home" else "home"
            dog_margin = (hp - ap) if dog == "home" else (ap - hp)

            writer.writerow({
                "game_id": game_id,
                "season": int(float(game["season"])),
                "week": game["week"],
                "season_type": game["season_type"].strip('"'),
                "date": game["start_date"][:10],
                "neutral_site": game["neutral_site"],
                "conference_game": game["conference_game"],
                "home_team": game["home_team"],
                "away_team": game["away_team"],
                "home_conference": game["home_conference"],
                "away_conference": game["away_conference"],
                "home_division": game["home_division"],
                "away_division": game["away_division"],
                "home_points": int(hp),
                "away_points": int(ap),
                "spread_home": spread_home,
                "n_books_spread": rec.get("n_books_spread"),
                "ml_home": ml_home,
                "ml_away": ml_away,
                "n_books_ml": rec.get("n_books_ml"),
                "dog": dog,
                "dog_team": game[f"{dog}_team"],
                "fav_team": game[f"{fav}_team"],
                "dog_conference": game[f"{dog}_conference"],
                "fav_conference": game[f"{fav}_conference"],
                "dog_line": abs(spread_home) if spread_home is not None else "",
                "dog_line_open": (
                    abs(rec["spread_home_open"])
                    if rec.get("spread_home_open") is not None
                    # only meaningful when the dog did not flip between open and close
                    and (rec["spread_home_open"] > 0) == (spread_home > 0)
                    else ""
                ) if spread_home else "",
                "dog_rest": rest.get((game_id, dog), ""),
                "fav_rest": rest.get((game_id, fav), ""),
                "dog_spread_price": rec.get(f"spread_price_{dog}"),
                "dog_ml": rec.get(f"ml_{dog}"),
                "fav_ml": rec.get(f"ml_{fav}"),
                "dog_source": source,
                "dog_margin": dog_margin,
            })
            written += 1

    print(f"games written                : {written:,}")
    for reason, count in skipped.most_common():
        print(f"  dropped {reason:<20} {count:,}")
    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
