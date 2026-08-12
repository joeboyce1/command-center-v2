# command-center-v2

## CSCO post-earnings day-after price moves

`data/csco_earnings_moves.csv` holds Cisco's close-to-close reaction to every
quarterly report from **May 1990 through August 2017** (110 events): Cisco reports
after the close (AMC), so each row measures `close(next session) / close(release day) - 1`.

| | |
|---|---|
| Events | 110 (May 1990 – Aug 2017) |
| Mean move | +0.63% |
| Median move | +0.52% |
| Mean absolute move | 5.68% |
| Higher next day | 57 of 110 (52%) |
| Best | +24.40% (7 May 2002) |
| Worst | −19.88% (12 May 1994) |

### How the dates are derived

The price file carries no earnings dates, so the release is located from the tape:
Cisco reports in Feb / May / Aug / Nov (fiscal year ends late July), and the session
after the release is reliably the highest-volume day of that month. The script picks
that session as `next_session`, treats the prior session as the release day, and
records `volume_vs_median` (reaction-day volume ÷ median of the previous 20 sessions)
so each detection can be judged — it runs 1.4×–13.5×, median ≈ 2.8×.

Spot checks against well-known reactions line up: 10 Nov 2010 (−16.2%),
9 Feb 2011 (−14.2%), 10 Aug 2011 (+16.0%), 17 May 2017 (−7.2%).

Caveats: prices are split- *and* dividend-adjusted, so a day-over-day change differs
from the raw price change when the pair straddles an ex-dividend date (Cisco began
paying dividends in 2011). Pre-1993 detections are the least certain — thinner tape,
and the release-time convention was less consistent.

### Coverage gap after 2017

The series stops at 2017-11-10 because that is where the source file ends, so the
Nov 2017 – May 2026 reports (36 events) are **not** included. They could not be added
from this environment: the session's egress policy blocks every market-data host
(Stooq, Nasdaq, Yahoo, stockanalysis, MarketChameleon, SEC, FRED — all 403 at the
proxy), and no reachable mirror carries CSCO daily prices past 2017.

To extend it, drop a longer daily CSV (`Date,Open,High,Low,Close,Volume`) in and rerun:

```bash
python3 scripts/csco_earnings_moves.py data/csco_daily_full.csv
```

The script re-derives every event from whatever range it is given and skips a trailing
partial month, so no dates need to be maintained by hand.

### Source

Daily OHLCV in `data/csco_daily_1990_2017.csv` is the Kaggle "Huge Stock Market Dataset"
(`Stocks/csco.us.txt`), via the
[neo-zhao mirror](https://github.com/neo-zhao/CMSC320_Final_Tutorial_Huge_Stock_Market_Dataset).
