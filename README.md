# NFL-season seasonality in gambling / sportsbook stocks

A reproducible backtest of the claim that sportsbook and casino equities outperform
during the NFL season.

## Status: code complete, not yet run on real data

**I could not fetch market data in the environment this was built in.** Every finance
host is blocked by the sandbox's egress policy:

```
fc.yahoo.com:443            403  (yfinance cookie/crumb bootstrap)
query1.finance.yahoo.com    403
query2.finance.yahoo.com    403
finance.yahoo.com           403
stooq.com                   403
```

The policy allows GitHub and package registries only. Rather than fabricate numbers,
the study is shipped as a pipeline that produces every requested table, chart, and the
written verdict the moment it runs somewhere with network access. It has been verified
end to end against a synthetic fixture and a 35-test suite.

Run it and `output/REPORT.md` is the deliverable.

## Running it

```bash
pip install -r requirements.txt
python run_study.py                     # ~1 minute at 10,000 permutations
```

Useful flags: `--permutations N`, `--seed N`, `--cost-bps N`, `--force-download`,
`--data-dir`, `--out-dir`, `--no-charts`.

Raw prices are cached as one CSV per symbol under `data/`. Re-runs read the cache, so
results are reproducible; `--force-download` refreshes it. Commit `data/` if you want
the exact sample pinned.

### Offline self-test

```bash
python run_study.py --synthetic         # fabricated prices, NOT a finding
python -m pytest tests -q
```

`--synthetic` fabricates prices with a known effect planted in two tickers so the
pipeline can be exercised with no network. Every output it writes is stamped
**SYNTHETIC**. It is a smoke test, not a result.

## What it computes

| # | Requested | Where |
|---|---|---|
| 1 | Mean / median / std / hit-rate by calendar month | `monthly_stats_raw.csv` |
| 2 | Same on excess return vs SPY | `monthly_stats_excess.csv`, heatmap |
| 3 | In-season vs off-season excess, difference + t-stat | `season_tests_by_ticker.csv` |
| 4 | Permutation test, 10,000 shuffles, empirical p | same, `permutation_null.png` |
| 5 | $10k equity curves, 5bps costs | `equity_curves.csv/png`, `backtest_summary.csv` |
| 6 | Everything rerun excluding 2020-2021 | `*_ex_2020_2021.*`, `scenario` column |

Windows: **in-season** Sep 1 – Feb 15, **off-season** Feb 16 – Aug 31, **front-run**
Aug 1 – Dec 31 (run as a fourth scenario). Universe: DKNG, FLUT, PENN, RSI, CZR, MGM,
BYD, GENI, CHDN. Benchmarks: SPY (excess-return basis) and XLY.

## Three methodology choices worth knowing about

**The permutation test rotates, it does not shuffle.** Independently shuffling daily
season labels destroys the block structure of a five-and-a-half-month window and the
serial correlation of daily returns. The resulting null is far too narrow and the
p-value is anticonservative — it will hand you significance that is not there. The
primary test instead **circularly rotates** the season mask by a random offset, which
preserves both structures and destroys only the alignment between calendar and returns.
The naive shuffle is computed too, and reported alongside, purely as a contrast.
`tests/test_pipeline.py::test_rotation_null_is_wider_than_shuffle_null_under_autocorrelation`
pins the difference.

**Two t-statistics, and the plain one is the weaker.** Welch's t-test assumes IID
observations, which daily returns are not. A Newey–West HAC t-stat (Bartlett kernel,
automatic lag selection) is reported next to it and is the one to read. Its calibration
is tested: under the null it has unit variance and a 5% rejection rate.

**The equal-weight basket is the headline, not the best ticker.** Nine tickers × twelve
months is 108 tests; roughly five will clear a raw 5% threshold on noise alone. Raw,
Bonferroni, and Benjamini–Hochberg p-values are all reported, but the honest single
number is the pre-specified basket test — one window, one p-value, no multiplicity tax.

## Verdict logic

The written verdict is generated mechanically from fixed thresholds, so the conclusion
cannot be chosen after seeing the numbers:

- **real** — basket permutation p < 0.05, positive difference, sign survives both the
  ex-2020/21 and earnings-excluded reruns, and ≥ 2 individual names with ≥ 10 seasons
  clear BH at 10%.
- **weak** — positive difference, permutation p < 0.15, stable sign, but failing one or
  more of the above.
- **nothing** — anything else.

## Caveats the report states explicitly

Sample size per ticker (anything under 10 NFL seasons is labelled not statistically
meaningful); earnings weeks inside the season window, with a rerun that strips ±3
trading days around every report date; survivorship bias from acquired and delisted
peers, whose absence biases the result *upward*; FLUT's Jan-2024 US listing and the
FLTR.L proxy's currency, trading-hours, and business-mix differences; multiple testing;
un-adjusted beta; window overlap; understated transaction costs; and a 0% cash yield.

Full text in `output/REPORT.md` under "Controls and caveats".

## Layout

```
run_study.py              entry point
src/nfl_seasonality/
  config.py               tickers, windows, constants, peer list
  windows.py              season masks, season-year bookkeeping
  data.py                 yfinance download + CSV cache + synthetic fixture
  analysis.py             returns, monthly tables, window tests, controls
  stats_tests.py          Welch, Newey-West, permutation, Bonferroni/BH
  backtest.py             seasonal rotation vs buy-and-hold vs SPY
  charts.py               heatmap, equity curves, bars, null histogram
  report.py               markdown assembly + verdict rules
  cli.py                  orchestration
tests/test_pipeline.py    35 tests
```

Chart colors come from a CVD-validated palette; categorical slots clear the all-pairs
contrast and colorblind-separation floors, and every series carries a direct label as
well as a legend entry.
