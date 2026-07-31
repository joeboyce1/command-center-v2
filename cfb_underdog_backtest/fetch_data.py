"""Download the raw inputs for the college football underdog backtest.

Sources (all public, served from raw.githubusercontent.com):

  * sportsdataverse/cfbfastR-data ``betting/csv/cfb_line_odds.csv.gz``
      Per-book betting lines scraped from the ESPN odds feed, 2006-2025.
      One row per game / market / sportsbook / side, with the last recorded
      line ("lines"/"odds") and, where available, the opener.
  * sportsdataverse/cfbfastR-data ``schedules/csv/cfb_schedules_<year>.csv``
      Game results, conferences, division, neutral-site and conference-game
      flags, keyed by the same ESPN game_id used by the odds feed.
  * sportsdataverse/cfbfastR-data ``teams/teams_colors_logos.csv``
      ESPN team_id -> abbreviation map, needed to work out which side of a
      per-book line row is the home team.
  * jackschooley/cfb-betting ``data/cfb odds <year>.csv``
      Independent closing lines derived from sportsbookreviewsonline.com,
      used only to validate the ESPN lines (see validate_lines.py).

Usage:  python cfb_underdog_backtest/fetch_data.py
"""

from __future__ import annotations

import pathlib
import sys
import urllib.parse
import urllib.request

RAW = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"
CFBFASTR = "https://raw.githubusercontent.com/sportsdataverse/cfbfastR-data/main"
SBR = "https://raw.githubusercontent.com/jackschooley/cfb-betting/master/data"

FIRST_SEASON, LAST_SEASON = 2006, 2025
SBR_SEASONS = range(2014, 2020)


def download(url: str, dest: pathlib.Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  have {dest.relative_to(RAW.parent.parent)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  get  {url}")
    with urllib.request.urlopen(url, timeout=120) as resp:
        dest.write_bytes(resp.read())


def main() -> int:
    print("betting lines + team map")
    download(f"{CFBFASTR}/betting/csv/cfb_line_odds.csv.gz", RAW / "cfb_line_odds.csv.gz")
    download(f"{CFBFASTR}/teams/teams_colors_logos.csv", RAW / "teams.csv")

    print("schedules")
    for year in range(FIRST_SEASON, LAST_SEASON + 1):
        download(
            f"{CFBFASTR}/schedules/csv/cfb_schedules_{year}.csv",
            RAW / "schedules" / f"{year}.csv",
        )

    print("validation lines (sportsbookreviewsonline via jackschooley/cfb-betting)")
    for year in SBR_SEASONS:
        name = urllib.parse.quote(f"cfb odds {year}.csv")
        download(f"{SBR}/{name}", RAW / "sbr" / f"{year}.csv")

    return 0


if __name__ == "__main__":
    sys.exit(main())
