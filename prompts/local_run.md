# Local run prompt

For a fresh Claude Code session on your own machine, where there is network
access and an earnings-dates API already configured. Fill in the two bracketed
fields and paste the whole block.

---

```text
Clone https://github.com/joeboyce1/command-center-v2 at branch
claude/pead-backtest-crwv-o1jvaa and run the PEAD study in it. Read its README
first — the methodology is already decided and is not up for redesign.

UNIVERSE:  [your tickers, e.g. NVDA AMD MU SMCI DELL AVGO MRVL ...]
BENCHMARK: QQQ
EARNINGS:  [name your API, e.g. "FMP, key in $FMP_API_KEY"]

WHAT I WANT
A table of every earnings event: ticker, how much the stock moved on the
session after the release, and how it moved over the following 30 and 60 days.
Then whether that survives the statistical checks the repo already implements.

STEPS

1. Set up: pip install pandas numpy yfinance, then `pytest tests/ -q` to confirm
   the harness is intact before trusting anything it prints.

2. Build the events file at data/universe.csv with exactly these columns:
       ticker,fiscal_quarter,announce_date,timing
   `timing` must be `amc` or `bmo`. Optional extra columns the tools read:
   eps_actual, eps_consensus, implied_move_pct.

   Pull the dates from my API. For `timing`:
     - If the API returns an explicit bmo/amc field, use it, then spot-check
       three rows against reality.
     - If it returns a timestamp, import infer_timing from fetch_events.py and
       use that. Do NOT hand-roll the rule and do NOT guess: a release marked
       on the wrong side of the close shifts the event a full session, which is
       the error that once inverted the sign of the largest event in this repo.
     - If a row is ambiguous, drop it and tell me. Do not fill it in.

   fetch_events.py already does all of this against yfinance. If my API turns
   out to be more trouble than it is worth, just use that instead and say so.

3. Get prices. Each ticker needs history starting at least ONE YEAR before its
   first earnings event — otherwise the volatility estimate cannot be computed,
   the signal silently never fires for those events, and the sample is quietly
   smaller than it looks. The run warns about this; do not ignore the warning.
   Pull the benchmark too.

4. Run it:
       python run_backtest.py --events data/universe.csv --benchmark QQQ \
         --signal sigma_move --report report.html

PRE-REGISTERED — fix these now, before seeing any output:
  - Signal: sigma_move at 3.0 (a move larger than 3 standard deviations of that
    stock's own daily volatility)
  - Horizons: 21 sessions (~30 days) and 42 sessions (~60 days)
  Do not try a second threshold to improve the result. If you want to explore
  others, say so explicitly and label it exploratory — it is a new hypothesis,
  not this one.

RULES
  - Every figure you report must come from run_backtest.py output. Do not
    recall, estimate, or web-search a return, and do not retype numbers from
    the run into prose — the page is the record.
  - Never pass --no-strict. If the run withholds the verdict, that is the
    answer, and I want to hear it plainly.
  - Report failures before successes.

DELIVERABLE
  1. Publish report.html as an artifact and give me the link.
  2. In chat, paste the verdict line and the data-quality findings verbatim.
  3. Tell me: the fire rate (what fraction of events cleared 3 sigma), the
     worst single event, where the earnings dates and timing came from and how
     confident you are in them, and anything you could not verify.

Do not give me a buy or sell recommendation. The question is whether the effect
survives measurement.
```

---

## What to expect

**A withheld verdict is likely on a first run** and is not a bug. The harness
computes the smallest effect your sample could tell apart from zero and refuses
to report an aggregate when that exceeds 5% per event. Fewer than roughly 20
tickers over several years will usually not clear it. The event table still
prints, which is the part you asked to see.

**Watch the fire rate.** If 3 sigma fires on more than about 70% of events it is
not selecting anything, and the study collapses into "trade every earnings
reaction". Between 30% and 50% is a filter doing real work.

**Watch the per-ticker coverage.** If one name supplies most of the fired
signals, the pooled result is that name's result wearing a universe costume.
