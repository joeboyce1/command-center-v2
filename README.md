# command-center-v2

## Backtest: betting the largest NFL underdog each week

Bet a flat $100 on the biggest point-spread underdog of every regular-season
week, 2021 through 2025 (90 weeks). Settled two ways: on the **moneyline**
(the dog wins outright) and **against the spread** (the dog covers).

```
python3 backtest/nfl_underdog.py            # uses the cached data
python3 backtest/nfl_underdog.py --refresh  # re-pull from nflverse
```

### Results

| | Moneyline | Against the spread |
|---|---|---|
| Record | 13-91 (12.5%) | 51-52-1 (49.5%) |
| Staked | $9,000 | $9,000 |
| Net profit | **-$3,622.83** | **-$923.70** |
| ROI | **-40.25%** | **-10.26%** |
| Max drawdown | -$4,110 | -$1,080 |
| Longest losing run | 37 bets | 5 bets |

By season, moneyline:

| Season | Record | Profit | ROI |
|---|---|---|---|
| 2021 | 2-17 | -$324.00 | -18.0% |
| 2022 | 5-19 | +$11.17 | +0.6% |
| 2023 | 1-17 | -$1,290.00 | -71.7% |
| 2024 | 5-16 | -$220.00 | -12.2% |
| 2025 | 0-22 | -$1,800.00 | -100.0% |

The strategy loses in both markets. The moneyline version is the more brutal
of the two: one season out of five finished ahead, and then by $11. It went
0-22 in 2025, and its worst stretch was 37 consecutive losing bets spanning
late 2022 into 2023.

The interesting part is *why* it loses on the moneyline. These dogs were
priced at an average implied win probability of 17.2% and actually won 12.5%
of the time. The loss is not merely the bookmaker's margin — the biggest
underdog of the week underperformed even the generous price it was offered
at. Against the spread the picks were close to a coin flip (49.5%), which is
roughly what an efficient market should produce; there the -10.3% ROI is
mostly just the vig on -110 odds.

### Method

Data is `games.csv` from [nflverse/nfldata](https://github.com/nflverse/nfldata),
which carries closing lines for every game. All 1,359 regular-season games in
the window have complete lines and results — nothing was dropped or imputed.

- **Underdog identification.** `spread_line > 0` means the home team is
  favored, so the dog is the away team, and vice versa. Verified against the
  moneylines: across all 379 games with a spread of 7+, the spread and the
  moneyline never disagree about which side is the underdog.
- **Ties for biggest dog.** Happened in 12 of 90 weeks (20 weeks had two tied
  games, 6 had three). The $100 weekly stake is split evenly among them, so
  exactly one unit is risked per week. Betting a full $100 on each tied dog
  instead barely moves the result (-40.80% ML ROI), so the conclusion does not
  hinge on this choice.
- **Settlement.** American-odds payouts. An NFL tie is a push on the
  moneyline; a spread landing exactly on the number is a push. There were no
  tie games among the picks and one spread push.
- **Closing lines, not opening lines.** A bettor placing these bets earlier in
  the week would have gotten different prices.

Per-bet ledgers are written to `backtest/results/`.
