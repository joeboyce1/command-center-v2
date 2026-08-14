"""Data-quality gates that run before any verdict is produced.

The point of this module is to make "unreliable" a machine-detectable state
rather than something the reader is trusted to infer from a caveat paragraph.
A study that cannot support a conclusion should say so loudly and refuse,
because the failure mode in this kind of work is not a wrong number - it is a
plausible-looking number nobody checked.

Checks return `Finding`s at three levels:

* ``FAIL`` - the study must not report a verdict.
* ``WARN`` - the result stands but is qualified.
* ``PASS`` - checked and clean.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import EarningsEvent

FAIL, WARN, PASS = "FAIL", "WARN", "PASS"

# Largest per-event effect that is plausible for post-earnings drift. If the
# sample can only detect something bigger than this, it cannot detect PEAD.
MAX_PLAUSIBLE_EFFECT = 0.05
TARGET_T = 2.0


@dataclass
class Finding:
    level: str
    check: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.check}: {self.detail}"


def check_prices(ticker: str, prices: pd.Series, max_gap_days: int = 5) -> list[Finding]:
    out: list[Finding] = []
    if prices.empty:
        return [Finding(FAIL, f"{ticker} prices", "series is empty")]

    if prices.index.has_duplicates:
        dupes = int(prices.index.duplicated().sum())
        out.append(Finding(FAIL, f"{ticker} prices", f"{dupes} duplicate dates"))

    if not prices.index.is_monotonic_increasing:
        out.append(Finding(FAIL, f"{ticker} prices", "dates are not sorted"))

    bad = prices[(prices <= 0) | (~np.isfinite(prices))]
    if len(bad):
        out.append(Finding(FAIL, f"{ticker} prices", f"{len(bad)} non-positive or non-finite closes"))

    gaps = prices.index.to_series().diff().dt.days
    big = gaps[gaps > max_gap_days]
    if len(big):
        worst = big.max()
        out.append(
            Finding(
                WARN,
                f"{ticker} prices",
                f"{len(big)} gaps over {max_gap_days} days (largest {int(worst)}); "
                "holidays are normal, halts and missing data are not",
            )
        )

    # A repeated close usually means a stale feed rather than a quiet stock.
    runs = (prices.diff() == 0).astype(int).groupby((prices.diff() != 0).cumsum()).sum()
    if len(runs) and runs.max() >= 4:
        out.append(
            Finding(WARN, f"{ticker} prices", f"{int(runs.max())} consecutive unchanged closes (stale feed?)")
        )

    if not any(f.level == FAIL for f in out):
        out.append(Finding(PASS, f"{ticker} prices", f"{len(prices)} sessions, {prices.index[0].date()} to {prices.index[-1].date()}"))
    return out


def check_events(
    events: list[EarningsEvent], prices: pd.Series, max_horizon: int
) -> list[Finding]:
    out: list[Finding] = []
    if not events:
        return [Finding(FAIL, "events", "no events supplied")]

    sessions = prices.index
    for event in events:
        tag = f"{event.ticker} {event.fiscal_quarter}"

        if event.timing not in ("amc", "bmo"):
            out.append(Finding(FAIL, tag, f"timing must be amc or bmo, got {event.timing!r}"))
            continue

        if not (sessions[0] <= event.announce_date <= sessions[-1]):
            out.append(Finding(FAIL, tag, f"announce date {event.announce_date.date()} outside the price series"))
            continue

        later = sessions[sessions > event.announce_date]
        if len(later) < max_horizon + 1:
            out.append(
                Finding(
                    WARN,
                    tag,
                    f"only {len(later)} sessions after the event; the +{max_horizon} "
                    "horizon will be dropped for this event",
                )
            )

        implied = event.implied_move_pct
        if implied is not None and not 0.01 <= implied <= 0.60:
            out.append(Finding(FAIL, tag, f"implied move of {implied:.1%} is outside a believable range"))

    dates = [e.announce_date for e in events]
    label = f"{events[0].ticker} events"
    if len(set(dates)) != len(dates):
        out.append(Finding(FAIL, label, "duplicate announcement dates"))

    if not any(f.level == FAIL for f in out):
        out.append(Finding(PASS, label, f"{len(events)} events aligned to the price series"))
    return out


def check_implied_coverage(events: list[EarningsEvent]) -> list[Finding]:
    """Report missing implied moves once for the whole run, not once per ticker.

    Called on the full event list rather than inside the per-ticker checks, so
    the count is the true one and a universe run does not print the same
    warning once per name.
    """
    missing = [e for e in events if e.implied_move_pct is None]
    if not missing:
        return [Finding(PASS, "implied moves", f"present for all {len(events)} events")]
    return [
        Finding(
            WARN,
            "implied moves",
            f"{len(missing)}/{len(events)} events have none; the excess_move "
            "signal is unavailable. Use --signal sigma_move or abs_move",
        )
    ]


def min_detectable_effect(dispersion: float, n: int, target_t: float = TARGET_T) -> float:
    """Smallest per-event effect this sample could distinguish from zero."""
    if n < 2:
        return float("inf")
    return target_t * dispersion / np.sqrt(n)


def check_power(
    signed_returns: list[float], label: str, effective_n: float | None = None
) -> list[Finding]:
    """Refuse a verdict the sample cannot support.

    ``effective_n`` lets the caller pass a clustering-adjusted sample size; the
    nominal count overstates power when events share earnings-season shocks.
    """
    n = len(signed_returns)
    if n < 2:
        return [Finding(FAIL, f"power ({label})", f"{n} usable events; no verdict possible")]

    dispersion = float(np.std(signed_returns, ddof=1))
    n_eff = effective_n if effective_n is not None else n
    mde = min_detectable_effect(dispersion, n_eff)

    detail = (
        f"n={n}"
        + (f" (effective {n_eff:.0f})" if effective_n is not None else "")
        + f", per-event sd {dispersion:.1%}, smallest detectable effect {mde:.1%}"
    )

    if mde > MAX_PLAUSIBLE_EFFECT:
        return [
            Finding(
                FAIL,
                f"power ({label})",
                detail
                + f" - above the {MAX_PLAUSIBLE_EFFECT:.0%} ceiling for a real PEAD "
                f"effect, so this sample cannot detect one. Report the events, not a verdict.",
            )
        ]
    return [Finding(PASS, f"power ({label})", detail)]


def effective_sample_size(event_days: list[pd.Timestamp], intra_cluster_corr: float = 0.15) -> float:
    """Shrink the sample for events landing in the same earnings week.

    Same-week events share macro and sector shocks, so they are not independent
    draws. Uses the standard design effect, 1 + (m - 1) * rho.
    """
    if not event_days:
        return 0.0
    weeks = pd.Series([d.to_period("W") for d in event_days])
    sizes = weeks.value_counts()
    avg_cluster = float(sizes.mean())
    design_effect = 1 + (avg_cluster - 1) * intra_cluster_corr
    return len(event_days) / design_effect


def report(findings: list[Finding], strict: bool = True, max_passes: int = 6) -> bool:
    """Print findings. Returns True when it is safe to report a verdict."""
    fails = [f for f in findings if f.level == FAIL]
    warns = [f for f in findings if f.level == WARN]
    passes = [f for f in findings if f.level == PASS]

    print("Data quality\n")
    for finding in fails + warns:
        print(f"  {finding}")

    # Passing checks are per-ticker and uninteresting individually; at universe
    # scale printing them all buries the failures they exist to surface.
    if len(passes) > max_passes:
        print(f"  [PASS] {len(passes)} other checks clean (prices, events, alignment)")
    else:
        for finding in passes:
            print(f"  {finding}")

    print(f"\n  {len(passes)} passed, {len(warns)} warnings, {len(fails)} failures")

    if fails and strict:
        print(
            "\nVERDICT SUPPRESSED. The checks above must be cleared before this "
            "study reports a conclusion. Per-event numbers are still shown; the "
            "aggregate claim is not."
        )
        return False
    return True
