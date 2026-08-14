"""Event-study machinery for post-earnings announcement drift.

PEAD is the claim that a stock keeps moving in the direction of its earnings
surprise *after* the announcement has been priced. Two design choices decide
whether you are actually measuring that or something else:

1. The announcement return must be excluded from the drift window. The move on
   the first session after the release is the market pricing the news, not
   drift. Drift is measured from t+1 onward.
2. Returns must be abnormal, not raw. A stock that fell 15% in a month when its
   sector fell 15% has not drifted. Abnormal returns here come from a market
   model estimated on a pre-event window, which keeps the event itself out of
   the beta estimate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import EarningsEvent

# Market-model estimation window, in trading days relative to the event day.
# It stops 11 days before the event so pre-announcement positioning does not
# contaminate the beta.
EST_START, EST_END = -140, -11
MIN_EST_OBS = 40


@dataclass
class EventResult:
    event: EarningsEvent
    event_day: pd.Timestamp
    beta: float
    alpha: float
    beta_source: str
    announcement_ar: float
    drift: dict[int, float] = field(default_factory=dict)
    raw_drift: dict[int, float] = field(default_factory=dict)

    def signal(self, mode: str) -> float | None:
        """Direction the PEAD trade would take, per signal definition."""
        if mode == "reaction":
            return np.sign(self.announcement_ar)
        if mode == "revenue":
            surprise = self.event.revenue_surprise_pct
            return None if surprise is None else np.sign(surprise)
        if mode == "eps":
            surprise = self.event.eps_surprise_pct
            return None if surprise is None else np.sign(surprise)
        raise ValueError(f"unknown signal mode: {mode}")


def _event_day(announce_date: pd.Timestamp, timing: str, sessions: pd.DatetimeIndex) -> pd.Timestamp:
    """First session that can price the announcement."""
    if timing == "amc":
        later = sessions[sessions > announce_date]
    elif timing == "bmo":
        later = sessions[sessions >= announce_date]
    else:
        raise ValueError(f"timing must be 'amc' or 'bmo', got {timing!r}")
    if len(later) == 0:
        raise ValueError(f"no trading session on or after {announce_date.date()}")
    return later[0]


def _market_model(
    stock: pd.Series, market: pd.Series, event_idx: int
) -> tuple[float, float, str]:
    """OLS of stock returns on market returns over the pre-event window.

    Falls back to a beta of 1 when there is not enough pre-event history, which
    is the common case for the first earnings report after an IPO.
    """
    lo = max(0, event_idx + EST_START)
    hi = event_idx + EST_END
    if hi <= lo:
        return 1.0, 0.0, "excess-return fallback (no estimation window)"

    y = stock.iloc[lo:hi].to_numpy()
    x = market.iloc[lo:hi].to_numpy()
    mask = np.isfinite(y) & np.isfinite(x)
    if mask.sum() < MIN_EST_OBS:
        return 1.0, 0.0, f"excess-return fallback ({int(mask.sum())} obs < {MIN_EST_OBS})"

    y, x = y[mask], x[mask]
    variance = x.var()
    if not np.isfinite(variance) or variance < 1e-12:
        # Degenerate window (e.g. a halted or synthetic benchmark). Regressing
        # on it would be singular, so fall back to a plain excess return.
        return 1.0, 0.0, "excess-return fallback (no benchmark variance)"

    beta = float(np.cov(y, x, ddof=0)[0, 1] / variance)
    alpha = float(y.mean() - beta * x.mean())
    return beta, alpha, f"market model ({len(y)} obs)"


def run_event_study(
    events: list[EarningsEvent],
    prices: pd.Series,
    benchmark: pd.Series,
    horizons: tuple[int, ...] = (1, 3, 5, 10, 21, 42, 63),
) -> list[EventResult]:
    """Compute the announcement reaction and post-announcement drift per event."""
    aligned = pd.concat({"stock": prices, "market": benchmark}, axis=1).dropna()
    stock_ret = aligned["stock"].pct_change()
    market_ret = aligned["market"].pct_change()
    sessions = aligned.index

    results: list[EventResult] = []
    for event in events:
        try:
            day = _event_day(event.announce_date, event.timing, sessions)
        except ValueError:
            continue
        idx = sessions.get_loc(day)

        beta, alpha, source = _market_model(stock_ret, market_ret, idx)
        abnormal = stock_ret - (alpha + beta * market_ret)

        result = EventResult(
            event=event,
            event_day=day,
            beta=beta,
            alpha=alpha,
            beta_source=source,
            announcement_ar=float(abnormal.iloc[idx]),
        )

        # Drift starts the session *after* the announcement is priced.
        for horizon in horizons:
            lo, hi = idx + 1, idx + 1 + horizon
            if hi > len(sessions):
                continue
            window = abnormal.iloc[lo:hi]
            if window.isna().any() or window.empty:
                continue
            result.drift[horizon] = float(window.sum())
            result.raw_drift[horizon] = float((1 + stock_ret.iloc[lo:hi]).prod() - 1)
        results.append(result)

    return results


def summarize(results: list[EventResult], signal_mode: str, horizons: tuple[int, ...]) -> pd.DataFrame:
    """Aggregate signed drift across events for one signal definition.

    The signed drift is what a PEAD trader would earn: go long after a positive
    surprise, short after a negative one. Positive, statistically reliable mean
    signed drift is the evidence PEAD exists.
    """
    rows = []
    for horizon in horizons:
        signed, hit = [], []
        for result in results:
            direction = result.signal(signal_mode)
            if direction is None or horizon not in result.drift or direction == 0:
                continue
            value = direction * result.drift[horizon]
            signed.append(value)
            hit.append(value > 0)
        if not signed:
            continue
        arr = np.array(signed)
        n = len(arr)
        stderr = arr.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
        rows.append(
            {
                "horizon_days": horizon,
                "n_events": n,
                "mean_signed_car": arr.mean(),
                "median_signed_car": float(np.median(arr)),
                "stdev": arr.std(ddof=1) if n > 1 else np.nan,
                "t_stat": arr.mean() / stderr if stderr and np.isfinite(stderr) else np.nan,
                "hit_rate": float(np.mean(hit)),
            }
        )
    return pd.DataFrame(rows)
