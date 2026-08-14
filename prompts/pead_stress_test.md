# PEAD stress-test prompt

Paste the block below into a fresh session, filling in the four fields at the
top. It is written to be run against this repo.

Read the two notes after it before trusting anything it produces.

---

```text
Stress-test the excess-move PEAD thesis using the harness in this repo.

TICKER(S):        <e.g. NVDA, AMD, SMCI, MU, DELL>
BENCHMARK:        <e.g. QQQ>
PERIOD:           <e.g. 2019-01-01 to today>
IMPLIED-MOVE DATA: <path to CSV, or "none available">

THESIS (fixed before you look at any result — do not modify it):
  When the first full regular session after an earnings release closes past the
  options-implied move, the stock continues drifting in that direction over the
  following 30-60 days.

PRE-REGISTERED PARAMETERS (fix these now; changing them after seeing results
invalidates the test):
  - Primary horizon: 42 trading sessions (~60 calendar days)
  - Secondary horizon: 21 trading sessions (~30 calendar days)
  - Implied-move threshold: 1.0x
  - Signal: excess_move
  - Benchmark adjustment: market model, estimation window t-140 to t-11

RULES — these are the point of the exercise, not boilerplate:

1. Every number in your output must come from `run_backtest.py` executing over
   a price series on disk. Do not source any return, reaction, implied move or
   drift figure from your own knowledge, from a web search, or from a news
   article. If you cannot obtain a price series, say so and stop. A study built
   from recalled or summarised figures is worse than no study, because it looks
   the same as a real one.

2. Use the first full regular-session close-to-close move, never the after-hours
   print. These differ in sign often enough to invert a result.

3. Do not tune anything to improve the outcome. If you find yourself trying a
   second threshold, a different horizon, or a subset of names, that is a new
   hypothesis needing a fresh sample — report it as such, separately, and
   labelled exploratory.

4. Report the failures first. Lead with the events that contradicted the
   thesis and the largest single loss, then the aggregate.

5. Respect the data-quality gates. If `run_backtest.py` suppresses the verdict,
   report that it did and why. Do not pass --no-strict to get a cleaner-looking
   answer, and do not reconstruct the aggregate by hand.

6. State per-field provenance. For each input — prices, earnings dates,
   announcement timing (AMC/BMO), implied moves — say where it came from and how
   confident you are. Mark anything you could not verify.

REQUIRED OUTPUT:
  a. The data-quality report, unedited.
  b. Per-event table: event day, raw and abnormal reaction, implied move,
     multiple, CAR at +21d and +42d.
  c. Contradicting events and worst-case single-event loss.
  d. Aggregate signed drift with a date-clustered t-stat — or an explicit
     statement that the sample cannot support one.
  e. What would falsify this: the specific result that would make you abandon
     the thesis.
  f. What you could not verify.

Do not give a buy/sell recommendation. The deliverable is whether the effect
survives measurement, not what to do about it.
```

---

## Note 1: a prompt cannot make this reliable on its own

Reliability here is a property of the data and the sample size, not of the
wording. The prompt above is mostly a set of prohibitions, because the realistic
failure is not that a model reasons badly about drift — it is that it produces a
confident table of numbers it half-remembered. That is exactly what happened in
the CRWV study in this repo: an after-hours quote of -5% was used where the
session close was +21.1%, which inverted the sign of the largest event in the
sample. The correction came from a source that happened to mention the implied
move, not from any reasoning step.

So the prompt's real job is to force every figure through
`run_backtest.py`, and to make "I could not get the data" an acceptable and
expected answer.

## Note 2: the gates do the work the prompt cannot

`pead/validate.py` runs before any aggregate is printed, and blocks the verdict
on:

* **Price integrity** — duplicate or unsorted dates, non-positive closes, gaps
  beyond a holiday weekend, runs of unchanged closes that indicate a stale feed.
* **Event integrity** — announcement dates outside the price series, invalid
  AMC/BMO timing, duplicate dates, implied moves outside a believable 1-60%
  range, and events too close to the end of the series to fill the horizon.
* **Statistical power** — the gate that matters. It computes the smallest
  effect the sample could distinguish from zero, using a clustering-adjusted
  sample size, and fails when that exceeds 5% per event. Post-earnings drift
  does not deliver more than that, so a sample needing more cannot detect it.

That last check is what makes a single-ticker run honest. Twelve quarterly
events at 20% per-event dispersion can only detect an 11.7% effect, so the
harness refuses a verdict and prints the events instead. You cannot get a
reassuring answer out of a sample that does not contain one.

To get a verdict at all you need roughly the sample sizes in
`power_analysis.py` — order 400-900 events, meaning 20-45 names over five
years, not one name over six quarters. **Run the harness across a universe, not
one ticker at a time.** A per-ticker loop reproduces the CRWV problem once per
name and then invites you to eyeball the pattern across them, which is the
least reliable thing you could do with the output.
