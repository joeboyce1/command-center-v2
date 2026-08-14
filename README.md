# command-center-v2

## PEAD backtest — CRWV (CoreWeave)

**Thesis under test:** when the first full session after earnings moves *past*
the options-implied move, does the stock keep drifting in that direction over
the following 30–60 days?

The signal is the announcement move measured against what the straddle priced
in, not the fundamental surprise. Direction comes from the sign of the break;
the trade fires only when `|reaction| >= threshold x implied_move`.

### Result: 4 confirm, 1 contradict, 1 still open

| Quarter | Event day | Reaction | Implied | Multiple | Drift 30–60d | Thesis |
|---|---|---|---|---|---|---|
| Q1 FY2025 | 2025-05-15 | **+21.1%** | 15.1% | 1.40x | Positive — ATH $187 on 6/20 | ✅ |
| Q2 FY2025 | 2025-08-13 | -20.8% | ~12.5% | 1.67x | Negative — ~-15% more by mid-Sept | ✅ |
| Q3 FY2025 | 2025-11-11 | -16.3% | 12.2% | 1.34x | Negative — kept sliding | ✅ |
| Q4 FY2025 | 2026-02-27 | -18.5% | 15.2% | 1.22x | **Positive** — ~$80 to ~$141 by 5/7 | ❌ |
| Q1 FY2026 | 2026-05-08 | -11.4% | 9.8% | 1.16x | Negative — ~$125 to $90.32 | ✅ |
| Q2 FY2026 | 2026-08-12 | +19.3% | 15.5% | 1.25x | Two sessions of data | ⏳ |

Read that as encouraging but not established. Four for five is what you would
expect to see roughly 19% of the time from a coin, so this sample cannot
separate a real effect from luck.

### The three things that actually matter here

**1. The filter barely filters.** CRWV has exceeded its implied move in every
one of the six quarters, at multiples from 1.16x to 1.67x. Its average absolute
post-earnings move over the last four quarters is about 16.8% against implied
moves that have run 9.8–15.5%. So on this name the "blew past implied" condition
is close to always-true, and the strategy collapses into plain
trade-the-reaction. If you want the filter to select rather than pass
everything, the threshold has to go higher — `--implied-threshold 1.3` cuts the
sample to Q1 FY2025, Q2 FY2025 and Q3 FY2025, which happen to be three of the
four confirmations. That is also the kind of after-the-fact threshold choice
that manufactures backtest results, so treat it as a hypothesis, not a finding.

**2. The one failure is the one that matters.** Q4 FY2025 broke 1.22x implied to
the downside and then round-tripped from roughly $80 to $141 inside ten weeks.
A short taken on that signal and held 60 days would have lost more than the
other three winners made. Mean signed drift on this sample is dominated by that
single event, which is exactly the fragility a six-event backtest cannot resolve.

**3. Direction is not symmetric in this sample.** Both upside breaks (Q1 FY2025,
Q2 FY2026) came on prints the market read as a structural change — the first
post-IPO report and the first evidence of operating leverage. Both drifted or
are drifting up. The downside breaks were guidance and capex driven, and those
mean-reverted twice out of four. If there is a real effect, it may be an upside
phenomenon on this name rather than a two-sided one, but two upside events is
not a basis for that claim.

### Caveats you should weigh before trading this

* **n = 6, one ticker, one 17-month regime** that happens to cover the sharpest
  part of the AI-infrastructure cycle. No t-stat computed here means anything.
* **The environment this ran in has no market-data egress** — Yahoo, stooq, SEC
  and the rest are all blocked at the proxy — so the reactions, implied moves
  and drift directions come from news and options-preview coverage rather than
  from recomputed daily bars. They are not benchmark-adjusted. Per-source
  confidence is tracked in `data/crwv_observed_reactions.csv`; the Q2 FY2025
  implied move is the weakest entry, attributed to that quarter with low
  confidence.
* **Drift direction is qualitative here, not a measured CAR.** "Positive" and
  "negative" come from anchor prices in reporting, not from a 30- or 60-session
  cumulative abnormal return. Running the code against real price data replaces
  every one of those cells with a number.

### Where the fundamental-surprise version lands

Worth keeping separate from your thesis, because it fails cleanly: CRWV beat
revenue consensus in all six quarters and the stock *fell* on five of the six
announcements. Signing drift by the revenue surprise gets the direction wrong
almost every time. The market has not been trading the reported quarter at all
— it has been trading guidance, capex and interest expense. That is also why
your reaction-based definition is the better-specified one for this name: the
announcement move contains the surprise, and the reported beat does not.

## Running it

```bash
pip install pandas numpy yfinance
python run_backtest.py --ticker CRWV --benchmark QQQ --implied-threshold 1.0
```

With network access the script pulls daily bars via `yfinance` and caches them
under `data/prices/`. Without it, drop a CSV with `date,close` columns at
`data/prices/CRWV.csv` (and one for the benchmark) and re-run — that path needs
no network. If no price series is available it prints the event table and the
reported reactions instead of failing, which is what it does in this repo today.

Output is a per-event table of raw and abnormal announcement moves, the implied
multiple, and cumulative abnormal drift at +1/+5/+10/+21/+42/+63 sessions, then
signed-drift summaries for four signal definitions: excess-move (yours),
reaction sign, revenue surprise and EPS surprise.

`--implied-threshold` sets how far past the implied move the reaction must go
before the signal fires. 1.0 means any break; 1.3 means 30% beyond.

## Method

* **Horizons are trading sessions.** 21 sessions is about 30 calendar days and
  42 is about 60, so those two columns are the ones your thesis is about.
* **Event day** is the first session that can price the release: the next
  session for an after-market-close announcement, the same session for a
  before-open one. This matters more than it sounds — CRWV's Q1 FY2025 print
  was down about 5% after hours and closed the next session **up 21.1%**. An
  after-hours quote would have given that event the wrong sign entirely.
* **Drift excludes the announcement session.** CAR windows start at t+1, so the
  move you are conditioning on is never also counted as drift.
* **The implied-move filter uses the raw move; drift uses abnormal returns.**
  A straddle prices the stock's total move, not its move net of the benchmark,
  so the filter compares like with like. Drift is then measured as abnormal
  return from a market model (`alpha + beta * market`) estimated over sessions
  t-140 to t-11, falling back to a plain excess return when there is too little
  pre-event history — the case for the first post-IPO report.
* **EPS surprise handles negative numbers correctly.** CRWV's actuals and
  consensus are both losses throughout, so the surprise divides by
  `abs(consensus)`: a smaller loss than expected reads as positive.

## Layout

```
pead/data.py         price/event loading, caching, surprise calculations
pead/eventstudy.py   event alignment, market model, CAR windows, signals
run_backtest.py      CLI
data/crwv_earnings.csv            event table: actuals, consensus, implied moves
data/crwv_observed_reactions.csv  reactions vs implied, with per-row confidence
tests/               synthetic checks on alignment, CAR math and signal firing
```

`pytest tests/ -q` — 12 tests covering AMC/BMO alignment, exclusion of the
announcement day from the drift window, recovery of a known injected drift, beta
estimation and benchmark netting, the excess-move threshold and its use of raw
rather than abnormal returns, and the negative-EPS sign convention.
