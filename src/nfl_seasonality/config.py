"""Tickers, window definitions, and run-wide constants."""

from __future__ import annotations

from dataclasses import dataclass

# Gambling / sportsbook universe under test.
TICKERS: list[str] = [
    "DKNG",  # DraftKings
    "FLUT",  # Flutter Entertainment (US listing, Jan 2024)
    "PENN",  # PENN Entertainment
    "RSI",   # Rush Street Interactive
    "CZR",   # Caesars Entertainment
    "MGM",   # MGM Resorts
    "BYD",   # Boyd Gaming
    "GENI",  # Genius Sports
    "CHDN",  # Churchill Downs
]

MARKET_BENCHMARK = "SPY"
SECTOR_BENCHMARK = "XLY"
BENCHMARKS: list[str] = [MARKET_BENCHMARK, SECTOR_BENCHMARK]

# Longer-history proxy for FLUT. Flutter's primary listing was Dublin/London
# before the Jan 2024 US listing. Prices are in GBp (FLTR.L) or EUR (FLTR.IR),
# so returns are local-currency and carry an FX component vs. a USD investor.
FLUT_LONG_HISTORY_PROXY = "FLTR.L"

ALL_SYMBOLS: list[str] = TICKERS + BENCHMARKS + [FLUT_LONG_HISTORY_PROXY]


@dataclass(frozen=True)
class Window:
    """A calendar window defined by (month, day) start and end.

    ``wraps`` is True when the window crosses a year boundary, in which case a
    date matches if it is on/after the start OR on/before the end.
    """

    name: str
    start_month: int
    start_day: int
    end_month: int
    end_day: int

    @property
    def wraps(self) -> bool:
        return (self.end_month, self.end_day) < (self.start_month, self.start_day)


# NFL season: regular season kickoff through the Super Bowl.
NFL_SEASON = Window("in_season", 9, 1, 2, 15)
# Everything else.
OFF_SEASON = Window("off_season", 2, 16, 8, 31)
# "Front-run" hypothesis: the market prices the season in before kickoff.
FRONT_RUN = Window("front_run", 8, 1, 12, 31)

# Backtest settings.
INITIAL_CAPITAL = 10_000.0
TRANSACTION_COST_BPS = 5.0
CASH_ANNUAL_YIELD = 0.0  # Cash earns nothing; see README caveats.

# Statistics.
N_PERMUTATIONS = 10_000
RANDOM_SEED = 20260807
EARNINGS_EXCLUSION_TRADING_DAYS = 3  # +/- 3 trading days == a ~1 week blackout.

# Years dropped in the robustness rerun (COVID crash + meme/stimulus melt-up).
ROBUSTNESS_EXCLUDE_YEARS: tuple[int, ...] = (2020, 2021)

# Minimum full NFL seasons before a ticker is flagged as thin.
MIN_SEASONS_FLAG = 5
# Below this, the per-ticker result is reported as not statistically meaningful.
MIN_SEASONS_MEANINGFUL = 10

TRADING_DAYS_PER_YEAR = 252

# Sportsbook / regional-casino peers that no longer trade as independent US
# equities. Their absence biases the surviving sample upward (survivorship).
DELISTED_OR_ACQUIRED_PEERS: list[tuple[str, str]] = [
    ("SGMS / LNW", "Scientific Games sold its sports-betting unit (2021); reorganised as Light & Wonder."),
    ("WYNN sports JV", "Wynn Interactive's SPAC merger (Austerlitz) was cancelled in Nov 2021 -- never traded."),
    ("GAN", "GAN Ltd -- B2B sportsbook platform, acquired by Sega Sammy, closed 2025."),
    ("BETZ constituents", "Several small-cap operators (e.g. Elys Game Technology, Esports Entertainment) collapsed or were delisted."),
    ("WMGI / William Hill", "William Hill plc acquired by Caesars (2021); its UK-listed history stops there."),
    ("Golden Nugget Online (GNOG)", "Acquired by DraftKings in May 2022."),
    ("Bally's (BALY)", "Taken private in 2025; US-listed history ends mid-sample."),
    ("Score Media (SCR)", "theScore acquired by Penn National, Oct 2021."),
]
