# command-center-v2

## PEAD backtest — CRWV (CoreWeave)

Does post-earnings announcement drift show up in CoreWeave?

### Short answer

**Not in the classic form, and the single-name sample is too small to call either way.**

Two things are true and they point in opposite directions:

* **On the fundamental surprise, the drift is inverted.** CRWV has beaten
  revenue consensus in all six quarters since its March 2025 IPO, and the stock
  *fell* on the announcement in five of those six. Classic PEAD says a positive
  surprise should be followed by positive drift. Here the sign is consistently
  wrong. Buying CRWV on a revenue beat has been a losing trade every quarter
  except the most recent one.
* **On the reaction sign, it is close to a coin flip.** Trading in the direction
  of the announcement-day move — the version of PEAD that usually survives best
  in single names — worked after Q2 FY25, Q3 FY25 and Q1 FY26, and failed badly
  after Q1 FY25 and Q4 FY25, where the stock reversed hard within three months.
  Three out of five is noise, not an edge.

The reason the fundamental version breaks is not subtle: for CRWV the market has
not been trading the reported quarter at all. Every selloff was driven by
forward guidance, capex, interest expense or margin compression — Q3 FY25 cut
FY25 revenue guidance, Q4 FY25 guided Q1 operating income to roughly zero and
announced $30–35B of 2026 capex, Q1 FY26 guided Q2 light. The reported revenue
beat is close to irrelevant as a surprise variable, so it has no drift to
predict. Any PEAD signal for this name would have to be built on guidance
revisions, not on the headline beat.

The one break in the pattern is Q2 FY26 (2026-08-11), the first print that
showed operating leverage: the stock rose about 19% instead of falling. There
are only two sessions of post-event data as of this writing, so its drift is not
yet measurable.

### The sample

| Quarter | Announced | Revenue surprise | Announcement reaction | Drift after the reaction |
|---|---|---|---|---|
| Q1 FY2025 | 2025-05-14 (AMC) | +15.1% | ~-5% | Positive — rallied to a $187 ATH by 2025-06-20 |
| Q2 FY2025 | 2025-08-12 (AMC) | +12.5% | -20.8% | Negative — ~-15% further into mid-September |
| Q3 FY2025 | 2025-11-10 (AMC) | +5.4% | -16.3% | Negative — kept sliding |
| Q4 FY2025 | 2026-02-26 (AMC) | +3.0% | -18.5% | Positive — ~$80 to ~$141 by early May |
| Q1 FY2026 | 2026-05-07 (AMC) | beat | -11.4% | Negative — ~$125 to $90.32 by 2026-08-11 |
| Q2 FY2026 | 2026-08-11 (AMC) | +0.6% | +19.3% | Too recent to measure |

### Caveats that matter

* **n = 6.** CRWV has only been public since March 2025. PEAD is a
  cross-sectional effect measured over thousands of firm-quarters; six events
  from one stock cannot establish or refute it, and no t-stat computed on this
  sample should be taken seriously.
* **The reaction and drift figures above come from news reporting, not from a
  price series.** The environment this was run in blocks outbound access to
  every market-data host, so the numbers were not recomputed from daily bars and
  are not benchmark-adjusted. Treat them as approximate and re-run the code
  below against real data before relying on any of it.
* **Horizon changes the answer.** The drift looks more consistently negative
  over about a month and much less so over three, because two of the events
  reversed sharply in between. The table above uses whatever horizon the source
  reported, which is not a uniform window.

## Running it

```bash
pip install pandas numpy yfinance
python run_backtest.py --ticker CRWV --benchmark QQQ
```

With network access the script pulls daily bars via `yfinance` and caches them
under `data/prices/`. Without it, drop a CSV with `date,close` columns at
`data/prices/CRWV.csv` (and one for the benchmark) and re-run — that path needs
no network. If no price series is available at all it prints the event table and
the reported reactions instead of failing.

Output is a per-event table of announcement abnormal returns and cumulative
abnormal drift at +1/+3/+5/+10/+21/+42/+63 sessions, then signed-drift summaries
for three signal definitions: announcement-reaction sign, revenue-surprise sign
and EPS-surprise sign.

## Method

* **Event day** is the first session that can price the release: the next
  session for an after-market-close announcement, the same session for a
  before-open one. Getting this wrong by a day is the most common way an
  earnings event study silently breaks, so `timing` is explicit per event.
* **Drift excludes the announcement session.** CAR windows start at t+1. The
  move on the event day is the market pricing the news, not drift — including it
  would just be measuring the reaction twice.
* **Returns are abnormal, not raw**, from a market model (`alpha + beta *
  market`) estimated over sessions t-140 to t-11 so neither the event nor
  pre-announcement positioning contaminates the beta. When there is not enough
  pre-event history — which is the case for CRWV's first report after the IPO —
  it falls back to a plain excess return over the benchmark.
* **EPS surprise handles negative numbers correctly.** CRWV's actuals and
  consensus are both losses throughout, so the surprise is divided by
  `abs(consensus)`: a smaller loss than expected counts as a positive surprise.

## Layout

```
pead/data.py         price/event loading, caching, surprise calculations
pead/eventstudy.py   event alignment, market model, CAR windows, aggregation
run_backtest.py      CLI
data/crwv_earnings.csv            event table with actuals and consensus
data/crwv_observed_reactions.csv  reported reactions, with sources
tests/               synthetic checks on alignment and CAR math
```

`pytest tests/ -q` — 8 tests covering AMC/BMO alignment, exclusion of the
announcement day from the drift window, recovery of a known injected drift,
beta estimation and benchmark netting, and the negative-EPS sign convention.
