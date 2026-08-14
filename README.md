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
everything, the threshold has to go higher — `--signal excess_move --threshold 1.3` cuts the
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

## Scaling to other stocks

Run `python power_analysis.py` for the sizing. The short version: this has to be
tested cross-sectionally, because a single name can never settle it.

At a per-event 60-day dispersion of 30% — normal for a high-volatility tech name
— detecting a 2% mean signed drift needs about **900 events**, roughly 45 names
over five years. At 20% dispersion and a 3% effect it drops to about 178. With
six events on one ticker, only an effect larger than **24% per event** would be
detectable, which is 5–15x anything PEAD actually delivers.

Then subtract the clustering penalty. Earnings land in four crowded windows a
year, so same-week events share macro and sector shocks and are not independent
draws. At 50 events a week and an intra-cluster correlation of 0.15, 400 nominal
events behave like 48. Standard errors must be clustered by event date or the
backtest will look significant when it is not — this is the single most common
way a PEAD backtest fools its author.

The binding practical constraint is **historical implied moves**. Prices and
earnings dates are cheap; a point-in-time record of the pre-earnings ATM
straddle is not. Realistic sources are OptionMetrics IvyDB (the academic
standard), ORATS, CBOE DataShop or Polygon's options history. A workable free
proxy is to estimate the expected move from the stock's own realized earnings-day
volatility, at the cost of no longer testing the thing you meant to test — the
market's ex-ante forecast.

Three other things that will quietly break a cross-sectional version:

* **Survivorship.** A universe pulled from today's index membership omits every
  delisted name. Post-earnings crashes are exactly what gets delisted, so this
  biases the downside-break results upward.
* **Point-in-time consensus.** Estimate data gets restated. Using today's record
  of what consensus was leaks information backwards.
* **Costs and borrow.** Names that break their implied move are volatile, wide
  and often hard to borrow. Half the signals in the CRWV sample are shorts. A
  gross edge of 2% per event does not survive careless execution assumptions.

Where the effect is most likely to survive, based on the published record:
smaller caps, thin analyst coverage, high idiosyncratic volatility, and the
announcement-return-conditioned version rather than the SUE version. Drift has
decayed materially in large caps since the 2000s.

## Stress-testing other tickers

`prompts/pead_stress_test.md` holds a fill-in-the-blank prompt for running this
against a new universe. Its rules are mostly prohibitions, because the realistic
failure mode is not bad reasoning about drift — it is a confident table of
half-remembered numbers. The CRWV study in this repo hit exactly that: an
after-hours quote of -5% stood in for a session close of +21.1% and inverted the
sign of the largest event in the sample.

So reliability is enforced in code rather than in wording. `pead/validate.py`
runs before any aggregate prints and blocks the verdict on price integrity
(duplicate or unsorted dates, non-positive closes, suspicious gaps, stale
repeated closes), event integrity (dates outside the series, bad AMC/BMO timing,
implied moves outside 1–60%, too little post-event history), and — the one that
matters — **statistical power**. That check computes the smallest effect the
sample could tell from zero, using a clustering-adjusted sample size, and fails
when it exceeds 5% per event.

The effect of that gate is that a single-ticker run cannot return a reassuring
answer. Twelve quarterly events at 20% dispersion detect only an 11.7% effect,
so the harness prints the per-event table and refuses the aggregate:

```
[FAIL] power (excess_move @ +42d): n=12, per-event sd 20.3%, smallest
detectable effect 11.7% - above the 5% ceiling for a real PEAD effect

VERDICT SUPPRESSED.
```

`--no-strict` overrides it and exists only for exploration. Reaching for it is
the tell that the sample is too small.

## Getting the earnings dates

```bash
python fetch_events.py NVDA AMD MU DELL --out data/universe_earnings.csv
```

Needs network access and `yfinance`. **Timing is derived from the announcement
timestamp, not taken from a vendor label** — after 16:00 ET is `amc`, before
09:30 is `bmo`. Anything landing inside the regular session, or at a midnight
placeholder, is refused rather than guessed and reported for you to fill in by
hand. Guessing there would misalign the event by a full session, which is the
error that inverted CRWV's largest event.

Yahoo's earnings history is shallow, often only a couple of years. For a longer
backtest use Financial Modeling Prep's earnings endpoint, which carries an
explicit `bmo`/`amc` field, or SEC EDGAR 8-K Item 2.02 filings, whose acceptance
timestamp gives the same information for free.

## Defining a "big move" without options data

Historical implied moves are the expensive input, so there are three
options-free stand-ins. All of them use the raw announcement move, and all are
computed from data strictly before the event.

| `--signal` | Fires when | Default | Needs |
|---|---|---|---|
| `excess_move` | move > N x the options-implied move | 1.0 | implied moves |
| `sigma_move` | move > N standard deviations of the stock's own daily vol | 3.0 | ~70 prior sessions |
| `earnings_vol_move` | move > N x the stock's average past earnings move | 1.0 | 3 prior events |
| `abs_move` | move > a fixed percentage | 0.10 | nothing |

**`sigma_move` is the default, and a fixed percentage is the one to avoid.** A
10% move is extraordinary for a utility and a normal Tuesday for a high-beta AI
name, so a single percentage threshold applied across a universe is not a
neutral filter — it is a volatility screen in disguise. It will select almost
entirely high-volatility names, and those are exactly the names with the widest
drift dispersion, so the sample you end up measuring is the one where the
signal is hardest to detect. `test_fixed_percentage_selects_on_volatility_but_sigma_does_not`
demonstrates this: an identical 10% move fires `abs_move` for both a calm and a
wild stock, while `sigma_move` correctly separates them.

`earnings_vol_move` is the closest free proxy for the straddle, since options
are priced largely off what a stock usually does on earnings day. Its cost is a
burn-in: the first three events per ticker have no prior moves to average and
are skipped. It also has to be computed forward in time — the expected move for
event *k* averages only events before *k*. Averaging the whole sample would let
a future move set the threshold that selects a past one, which flatters the
backtest and cannot be traded.

## Running it

```bash
pip install pandas numpy
python run_backtest.py --ticker NVDA --benchmark QQQ \
  --events data/nvda_earnings.csv --signal sigma_move --threshold 3.0 --offline
```

**Yahoo Finance CSV downloads work unmodified.** Save the export to
`data/prices/<TICKER>.csv` (and one for the benchmark) and pass `--offline`; no
network or API key is needed. The loader takes Yahoo's
`Date,Open,High,Low,Close,Adj Close,Volume` layout, a plain `date,close` file,
or a Nasdaq-style export with `$` and thousands separators.

It reads **Adj Close** in preference to `Close` whenever both are present, which
matters more than it sounds: raw `Close` is not split-adjusted, so a split
inside your sample shows up as a ~50% overnight crash that this study would
happily record as an earnings reaction.

The events file needs `ticker,fiscal_quarter,announce_date,timing`, where
`timing` is `amc` or `bmo`. `implied_move_pct` is optional and only required for
`--signal excess_move`.

With network access and `yfinance` installed, dropping `--offline` pulls and
caches the bars automatically.

Output is a per-event table of raw and abnormal announcement moves, the implied
multiple, and cumulative abnormal drift at +1/+5/+10/+21/+42/+63 sessions, then
signed-drift summaries for four signal definitions: excess-move (yours),
reaction sign, revenue surprise and EPS surprise.

`--threshold` sets how far past the bar the reaction must go
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
fetch_events.py      builds an events CSV, inferring AMC/BMO from the timestamp
pead/data.py         price/event loading, caching, surprise calculations
pead/eventstudy.py   event alignment, market model, CAR windows, signals
run_backtest.py      CLI
data/crwv_earnings.csv            event table: actuals, consensus, implied moves
data/crwv_observed_reactions.csv  reactions vs implied, with per-row confidence
tests/               synthetic checks on alignment, CAR math and signal firing
```

`pytest tests/ -q` — 44 tests covering AMC/BMO alignment, exclusion of the
announcement day from the drift window, recovery of a known injected drift, beta
estimation and benchmark netting, the excess-move threshold and its use of raw
rather than abnormal returns, and the negative-EPS sign convention.
