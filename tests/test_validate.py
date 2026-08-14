"""Checks that the data-quality gates actually block bad studies.

These matter more than the event-study tests. A wrong CAR is visible; a verdict
quietly drawn from six noisy events is not.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pead.data import EarningsEvent
from pead.validate import (
    FAIL,
    Finding,
    PASS,
    WARN,
    check_events,
    check_implied_coverage,
    check_power,
    check_prices,
    effective_sample_size,
    min_detectable_effect,
    report,
)


def clean_prices(n: int = 300) -> pd.Series:
    dates = pd.bdate_range("2024-01-02", periods=n)
    rng = np.random.default_rng(0)
    return pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, n)), index=dates)


def levels(findings, level):
    return [f for f in findings if f.level == level]


def test_clean_prices_pass():
    assert levels(check_prices("X", clean_prices()), FAIL) == []


def test_empty_and_negative_prices_fail():
    assert levels(check_prices("X", pd.Series(dtype=float)), FAIL)

    prices = clean_prices()
    prices.iloc[10] = -5.0
    assert levels(check_prices("X", prices), FAIL)


def test_duplicate_and_unsorted_dates_fail():
    prices = clean_prices()
    dupe = pd.concat([prices, prices.iloc[[5]]])
    assert levels(check_prices("X", dupe), FAIL)


def test_stale_feed_warns():
    prices = clean_prices()
    prices.iloc[50:56] = prices.iloc[50]
    assert levels(check_prices("X", prices), WARN)


def test_price_gap_warns():
    prices = clean_prices()
    prices = pd.concat([prices.iloc[:100], prices.iloc[140:]])
    assert levels(check_prices("X", prices), WARN)


def test_event_outside_price_series_fails():
    prices = clean_prices()
    event = EarningsEvent("X", "Q1", pd.Timestamp("2030-01-01"), "amc", implied_move_pct=0.1)
    assert levels(check_events([event], prices, 42), FAIL)


def test_bad_timing_and_absurd_implied_move_fail():
    prices = clean_prices()
    bad_timing = EarningsEvent("X", "Q1", prices.index[50], "after-close", implied_move_pct=0.1)
    assert levels(check_events([bad_timing], prices, 42), FAIL)

    absurd = EarningsEvent("X", "Q1", prices.index[50], "amc", implied_move_pct=0.95)
    assert levels(check_events([absurd], prices, 42), FAIL)


def test_missing_implied_move_warns_but_does_not_fail():
    prices = clean_prices()
    event = EarningsEvent("X", "Q1", prices.index[50], "amc")
    # Per-ticker checks stay quiet about it; coverage is reported run-wide.
    assert levels(check_events([event], prices, 42), FAIL) == []

    findings = check_implied_coverage([event])
    assert levels(findings, WARN)
    assert levels(findings, FAIL) == []


def test_implied_coverage_counts_the_whole_run_once():
    """One aggregated line, with the true total, not one warning per ticker."""
    day = clean_prices().index[50]
    events = [
        EarningsEvent("A", "Q1", day, "amc", implied_move_pct=0.1),
        EarningsEvent("B", "Q1", day, "amc"),
        EarningsEvent("C", "Q1", day, "amc"),
    ]
    findings = check_implied_coverage(events)
    assert len(findings) == 1
    assert "2/3" in findings[0].detail

    covered = [EarningsEvent("A", "Q1", day, "amc", implied_move_pct=0.1)]
    assert levels(check_implied_coverage(covered), PASS)


def test_report_collapses_passing_checks_at_universe_scale(capsys):
    """Twenty clean tickers must not bury the one real failure."""
    findings = [Finding(PASS, f"T{i} prices", "clean") for i in range(20)]
    findings.append(Finding(FAIL, "power", "cannot detect"))

    report(findings, strict=True)
    out = capsys.readouterr().out
    assert "20 other checks clean" in out
    assert "cannot detect" in out
    assert "T5 prices" not in out


def test_event_too_close_to_the_end_warns():
    prices = clean_prices()
    event = EarningsEvent("X", "Q1", prices.index[-5], "amc", implied_move_pct=0.1)
    assert levels(check_events([event], prices, 42), WARN)


def test_duplicate_event_dates_fail():
    prices = clean_prices()
    day = prices.index[50]
    events = [
        EarningsEvent("X", "Q1", day, "amc", implied_move_pct=0.1),
        EarningsEvent("X", "Q2", day, "amc", implied_move_pct=0.1),
    ]
    assert levels(check_events(events, prices, 42), FAIL)


def test_min_detectable_effect_shrinks_with_sample_size():
    assert min_detectable_effect(0.30, 6) > min_detectable_effect(0.30, 100)
    # 2 * 0.30 / sqrt(900) = 2%
    assert min_detectable_effect(0.30, 900) == pytest.approx(0.02, abs=1e-6)
    assert min_detectable_effect(0.30, 1) == float("inf")


def test_power_gate_blocks_a_small_noisy_sample():
    """Six events at CRWV-like dispersion must never yield a verdict."""
    rng = np.random.default_rng(1)
    signed = list(rng.normal(0.05, 0.30, 6))
    findings = check_power(signed, "excess_move")
    assert levels(findings, FAIL)
    assert "cannot detect" in findings[0].detail


def test_power_gate_passes_a_large_precise_sample():
    rng = np.random.default_rng(2)
    signed = list(rng.normal(0.02, 0.15, 900))
    assert levels(check_power(signed, "excess_move"), PASS)


def test_power_gate_respects_the_clustering_adjustment():
    """The same returns can pass on nominal n and fail on effective n."""
    rng = np.random.default_rng(3)
    signed = list(rng.normal(0.02, 0.15, 500))
    # Nominal n=500 detects 1.3%; clustering down to 20 detects only 6.7%,
    # which is past the 5% ceiling.
    assert levels(check_power(signed, "s"), PASS)
    assert levels(check_power(signed, "s", effective_n=20), FAIL)


def test_effective_sample_size_penalises_clustered_events():
    same_week = [pd.Timestamp("2025-02-03") + pd.Timedelta(days=i) for i in range(5)] * 10
    spread = [pd.Timestamp("2025-01-06") + pd.Timedelta(weeks=i) for i in range(50)]

    assert effective_sample_size(same_week) < len(same_week)
    # One event per week is already independent, so no penalty.
    assert effective_sample_size(spread) == pytest.approx(len(spread), abs=1e-6)
    assert effective_sample_size([]) == 0.0


def test_report_suppresses_a_verdict_on_failure(capsys):
    prices = pd.Series(dtype=float)
    findings = check_prices("X", prices)

    assert report(findings, strict=True) is False
    assert "VERDICT SUPPRESSED" in capsys.readouterr().out

    # Non-strict mode is the explicit opt-out.
    assert report(findings, strict=False) is True
