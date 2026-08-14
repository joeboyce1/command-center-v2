"""Checks on earnings-date timing inference.

The network call cannot be tested here, but the part that decides which session
prices the news is pure logic - and it is the part that would quietly ruin a
study, so it is tested directly.
"""

from __future__ import annotations

import pandas as pd

from fetch_events import frame_to_events, infer_timing


def test_after_close_is_amc():
    assert infer_timing(pd.Timestamp("2025-08-12 16:05")) == "amc"
    assert infer_timing(pd.Timestamp("2025-08-12 17:00")) == "amc"
    assert infer_timing(pd.Timestamp("2025-08-12 20:30")) == "amc"


def test_before_open_is_bmo():
    assert infer_timing(pd.Timestamp("2025-08-12 06:00")) == "bmo"
    assert infer_timing(pd.Timestamp("2025-08-12 08:45")) == "bmo"
    assert infer_timing(pd.Timestamp("2025-08-12 09:29")) == "bmo"


def test_intraday_and_placeholder_times_are_refused():
    """Guessing here would misalign the event by a whole session."""
    assert infer_timing(pd.Timestamp("2025-08-12 09:30")) is None
    assert infer_timing(pd.Timestamp("2025-08-12 12:00")) is None
    assert infer_timing(pd.Timestamp("2025-08-12 15:59")) is None
    # Midnight is a vendor placeholder, not a real announcement time.
    assert infer_timing(pd.Timestamp("2025-08-12 00:00")) is None
    assert infer_timing(None) is None
    assert infer_timing(pd.NaT) is None


def _frame(index, **cols):
    return pd.DataFrame(cols or {"EPS Estimate": [None] * len(index)}, index=index)


def test_frame_to_events_maps_timing_and_quarter():
    frame = _frame(
        pd.to_datetime(["2025-02-26 16:20", "2025-05-07 07:00"]),
        **{"EPS Estimate": [-0.49, -0.91], "Reported EPS": [-0.56, -1.40]},
    )
    rows, problems = frame_to_events("CRWV", frame)

    assert problems == []
    assert [r["timing"] for r in rows] == ["amc", "bmo"]
    assert [r["announce_date"] for r in rows] == ["2025-02-26", "2025-05-07"]
    assert [r["fiscal_quarter"] for r in rows] == ["2025Q1", "2025Q2"]
    assert rows[0]["eps_consensus"] == "-0.49"


def test_ambiguous_rows_are_reported_not_guessed():
    frame = _frame(pd.to_datetime(["2025-02-26 12:00", "2025-05-07 16:05"]))
    rows, problems = frame_to_events("X", frame)

    assert len(rows) == 1  # only the unambiguous one survives
    assert len(problems) == 1
    assert "ambiguous" in problems[0]


def test_timezone_aware_stamps_are_handled():
    frame = _frame(pd.to_datetime(["2025-02-26 16:20"]).tz_localize("America/New_York"))
    rows, problems = frame_to_events("X", frame)

    assert problems == []
    assert rows[0]["timing"] == "amc"
    assert rows[0]["announce_date"] == "2025-02-26"


def test_missing_eps_fields_become_blank_not_nan():
    """Blank cells parse back as None; the string 'nan' would not."""
    frame = _frame(
        pd.to_datetime(["2025-02-26 16:20"]),
        **{"EPS Estimate": [float("nan")], "Reported EPS": [None]},
    )
    rows, _ = frame_to_events("X", frame)
    assert rows[0]["eps_consensus"] == ""
    assert rows[0]["eps_actual"] == ""
