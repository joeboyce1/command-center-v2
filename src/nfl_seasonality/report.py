"""Markdown report assembly and the rules-based verdict."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import (
    DELISTED_OR_ACQUIRED_PEERS,
    FLUT_LONG_HISTORY_PROXY,
    MIN_SEASONS_MEANINGFUL,
    TRANSACTION_COST_BPS,
)


def md_table(frame: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    """Render a DataFrame as a GitHub markdown table."""
    if frame is None or frame.empty:
        return "_(no rows)_\n"

    def cell(value) -> str:
        if value is None or (isinstance(value, float) and not np.isfinite(value)):
            return "n/a"
        if isinstance(value, (bool, np.bool_)):
            return "yes" if value else "no"
        if isinstance(value, (float, np.floating)):
            return floatfmt.format(value)
        return str(value)

    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    rule = "| " + " | ".join("---" for _ in frame.columns) + " |"
    body = [
        "| " + " | ".join(cell(v) for v in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([header, rule, *body]) + "\n"


@dataclass
class Verdict:
    headline: str
    strength: str  # "real" | "weak" | "nothing"
    bullets: list[str]


def build_verdict(
    pooled: dict,
    pooled_robust: dict,
    pooled_earnings: dict,
    per_ticker: pd.DataFrame,
    coverage: pd.DataFrame,
) -> Verdict:
    """Derive the verdict mechanically from the computed statistics.

    Thresholds are fixed in advance so the conclusion is not chosen after
    seeing the numbers:

    * **real**    -- basket permutation p < 0.05, positive difference, the
                     sign survives both the ex-2020/21 and earnings-excluded
                     reruns, and at least two individual names clear BH at
                     10% on a >= 10-season history.
    * **weak**    -- positive difference with basket permutation p < 0.15 and
                     a stable sign across reruns, but failing one or more of
                     the above.
    * **nothing** -- anything else.
    """
    bullets: list[str] = []
    diff = pooled.get("diff_bps_day", np.nan)
    p_perm = pooled.get("p_perm_rotate", np.nan)
    p_hac = pooled.get("p_hac", np.nan)

    if not np.isfinite(diff) or not np.isfinite(p_perm):
        return Verdict(
            "Inconclusive - the basket test could not be computed from the available data.",
            "nothing",
            ["Check data coverage; at least one benchmark or ticker series is missing."],
        )

    robust_diff = pooled_robust.get("diff_bps_day", np.nan)
    earnings_diff = pooled_earnings.get("diff_bps_day", np.nan)
    sign_stable = (
        np.isfinite(robust_diff) and np.isfinite(earnings_diff)
        and np.sign(robust_diff) == np.sign(diff)
        and np.sign(earnings_diff) == np.sign(diff)
    )

    meaningful = per_ticker[per_ticker["n_seasons"] >= MIN_SEASONS_MEANINGFUL]
    survivors = meaningful[(meaningful["p_perm_bh"] < 0.10) & (meaningful["diff_bps_day"] > 0)]
    n_survivors = len(survivors)

    if diff > 0 and p_perm < 0.05 and sign_stable and n_survivors >= 2:
        strength = "real"
        headline = (
            f"Yes - there is a real NFL-season effect. The equal-weight gambling basket earns "
            f"{diff:+.1f} bps/day more excess return over SPY in season than out "
            f"({pooled.get('diff_annualised_pct', np.nan):+.1f}% annualised), permutation p = {p_perm:.4f}, "
            f"and it survives dropping 2020-21 and stripping earnings weeks."
        )
    elif diff > 0 and p_perm < 0.15 and sign_stable:
        strength = "weak"
        headline = (
            f"Weak. The basket does tilt positive in season - {diff:+.1f} bps/day of excess return "
            f"({pooled.get('diff_annualised_pct', np.nan):+.1f}% annualised) - and the sign holds across reruns, "
            f"but at permutation p = {p_perm:.3f} it is not distinguishable from calendar noise "
            f"at conventional thresholds."
        )
    else:
        strength = "nothing"
        headline = (
            f"No. The basket's in-season excess return over SPY is {diff:+.1f} bps/day "
            f"(permutation p = {p_perm:.3f}) - indistinguishable from randomly placed calendar windows. "
            f"There is no tradeable NFL-season effect in this sample."
        )

    bullets.append(
        f"Basket in-season {pooled.get('in_bps_day', np.nan):+.2f} bps/day vs off-season "
        f"{pooled.get('off_bps_day', np.nan):+.2f} bps/day; difference {diff:+.2f} bps/day. "
        f"Welch t = {pooled.get('t_welch', np.nan):.2f}, Newey-West t = {pooled.get('t_hac', np.nan):.2f} "
        f"(HAC p = {p_hac:.3f}), permutation p = {p_perm:.4f}."
    )
    bullets.append(
        f"Read the rotation p-value, not the naive daily shuffle (which gives "
        f"p = {pooled.get('p_perm_shuffle', np.nan):.4f}). Shuffling day labels independently breaks the "
        "block structure of a five-and-a-half-month window and the serial correlation of daily returns, "
        "so its null distribution is the wrong shape for a calendar hypothesis - typically too narrow, "
        "and not trustworthy in either direction."
    )
    bullets.append(
        f"Excluding 2020-21: difference {robust_diff:+.2f} bps/day "
        f"(permutation p = {pooled_robust.get('p_perm_rotate', np.nan):.3f}). "
        f"Excluding earnings weeks: {earnings_diff:+.2f} bps/day "
        f"(permutation p = {pooled_earnings.get('p_perm_rotate', np.nan):.3f})."
    )
    thin = coverage[coverage["flag_not_meaningful"] & coverage["symbol"].isin(per_ticker["ticker"])]
    if len(thin):
        bullets.append(
            f"{len(thin)} of {len(per_ticker)} names have fewer than {MIN_SEASONS_MEANINGFUL} NFL seasons "
            f"({', '.join(thin['symbol'])}). Their individual numbers are descriptive only - not statistically meaningful."
        )
    bullets.append(
        f"{n_survivors} name(s) with a 10+ season history clear a 10% BH false-discovery threshold on the "
        "permutation p-value. Any name that only clears the raw p-value has not cleared anything: "
        "at 9 tickers x 12 months you expect around five raw hits at the 5% level by chance alone."
    )
    return Verdict(headline, strength, bullets)


def caveats_section(coverage: pd.DataFrame) -> str:
    flut = coverage[coverage["symbol"] == "FLUT"]
    flut_start = flut["start"].iloc[0] if len(flut) else "n/a"
    proxy = coverage[coverage["symbol"] == FLUT_LONG_HISTORY_PROXY]
    proxy_start = proxy["start"].iloc[0] if len(proxy) else "not retrieved"
    proxy_seasons = proxy["n_full_seasons"].iloc[0] if len(proxy) else "n/a"

    peers = "\n".join(f"- **{name}** - {note}" for name, note in DELISTED_OR_ACQUIRED_PEERS)

    return f"""## Controls and caveats

### Sample size
Season counts are in the coverage table above. A "full season" requires data covering at
least 80% of that season's trading days, so a December IPO does not get credit for a season.
Any ticker under {MIN_SEASONS_MEANINGFUL} seasons is marked **not statistically meaningful** -
with 6-8 seasons, a single strong autumn moves the mean enough to manufacture a t-stat, and no
correction rescues that. Read those rows as description, not evidence.

### Earnings dates inside the season window
Q3 results (late Oct / early Nov) and Q4 results (Feb) both land inside the Sep 1 - Feb 15
window, so an "NFL effect" can easily be an earnings-drift effect. The earnings-excluded
rerun blanks +/- 3 trading days around every report date. Caveat on the caveat: yfinance
only serves a few years of earnings history, so the exclusion is incomplete for the earlier
part of the sample - it removes the recent earnings weeks, not all of them.

### Survivorship
The nine tickers are the names that still trade. The ones that did not survive are missing,
and they failed disproportionately after bad seasons:

{peers}

That biases the surviving sample's in-season returns upward. This backtest therefore
*overstates* any positive effect, and the direction of the bias is known.

### FLUT / Flutter listing history
FLUT's US listing begins {flut_start}, giving it very little usable history.
The longer-history proxy {FLUT_LONG_HISTORY_PROXY} starts {proxy_start}
({proxy_seasons} seasons). Three differences make the proxy non-substitutable in the main
tables, so it is reported separately: (1) it is quoted in GBp, not USD, so its excess return
over a USD SPY carries a GBP/USD move that has nothing to do with football; (2) it trades on
UK hours, so daily returns are misaligned with SPY by several hours - a real problem for
daily differencing; (3) pre-2024 Flutter was predominantly a UK/Ireland and Australian
business, where the NFL is a marginal product, so the hypothesis barely applies to that history.

### Multiple testing
The monthly grid is 9 tickers x 12 months = 108 tests, and the per-ticker season test is a
further 9. Raw, Bonferroni-adjusted, and Benjamini-Hochberg-adjusted p-values are all reported.
Read the BH column. The single pre-specified test - the equal-weight basket, one window,
one p-value - is the honest headline number, because it does not pay a multiplicity tax at all.

### Other things that could produce a false positive
- **Beta.** Excess return here is a plain return difference, not beta-adjusted alpha. These
  names run betas well above 1, so in a rising market they out-earn SPY regardless of season.
  That inflates in-season *and* off-season excess alike, so the *difference* is mostly immune -
  but a market that happens to rally in autumn across the sample would show up here as
  seasonality. The rotation permutation test is the defence against exactly that.
- **Overlapping windows.** Sep-Feb covers 46% of the calendar. In-season and off-season
  samples are not independent draws; the HAC t-stat and the rotation test both account for it,
  the Welch t-stat does not.
- **Transaction costs.** {TRANSACTION_COST_BPS:.0f} bps is charged on each season entry and exit
  (two round trips' worth of legs a year). Intra-basket rebalancing turnover is not charged, and
  neither is the spread on the smaller names (RSI, GENI), which is wider than 5 bps in practice.
  The seasonal sleeve's costs are therefore understated.
- **Cash yield.** The strategy earns 0% while flat. Over a period with 4-5% front-end rates
  that materially understates the seasonal sleeve - it is a conservative choice, not a neutral one.
"""
