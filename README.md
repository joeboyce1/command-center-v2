# command-center-v2

## College football underdog backtest

Does betting college football underdogs make money? Twenty seasons (2006-2025),
both markets, priced at the closing line.

**Short answer: no.** Underdogs against the spread lose 3.9% of every dollar
risked — they cover 50.3% of the time and the entire loss is the vig.
Underdogs on the moneyline lose 9.7%, because bettors badly overpay for big
dogs: dogs of +14.5 or more return -26% to -32%, while dogs of +3 or less are
roughly fairly priced.

The one cut that made money: **road underdogs of +3 or less on the moneyline**,
+8% ROI over 1,108 bets, profitable in 15 of 19 seasons and positive in both
halves of the sample. An independent dataset puts the same edge at +3.7%, so
call it a few percent rather than eight.

The closest thing to a free bye-week angle: an **underdog off a bye** is the
only ATS cut in the study that does not lose money (52.5% cover, +0.3% ROI,
positive in both halves of the sample). A rested *favourite* is worth nothing.

Full write-up with all the segment breakdowns: **[RESULTS.md](RESULTS.md)**

### Layout

| path | what |
|---|---|
| `cfb_underdog_backtest/fetch_data.py` | downloads the raw sources |
| `cfb_underdog_backtest/build_dataset.py` | per-book lines + schedules -> one row per game |
| `cfb_underdog_backtest/validate_lines.py` | cross-checks the lines against a second source |
| `cfb_underdog_backtest/backtest.py` | the backtest and the segment tables |
| `cfb_underdog_backtest/bye_analysis.py` | the bye-week study |
| `data/processed/games.csv` | 16,599 games with a consensus closing line and result |
| `results/` | generated reports and the segment table as CSV |

### Running it

```
python cfb_underdog_backtest/fetch_data.py
python cfb_underdog_backtest/build_dataset.py
python cfb_underdog_backtest/validate_lines.py
python cfb_underdog_backtest/backtest.py                  # FBS vs FBS (default)
python cfb_underdog_backtest/backtest.py --all-divisions  # include FCS opponents
python cfb_underdog_backtest/bye_analysis.py
```

No third-party dependencies — standard library only. `data/processed/games.csv`
is committed, so the backtest runs without re-downloading anything.

### Data

| source | used for |
|---|---|
| [sportsdataverse/cfbfastR-data](https://github.com/sportsdataverse/cfbfastR-data) `betting/csv/cfb_line_odds.csv.gz` | per-book spreads and moneylines from the ESPN odds feed, 2006-2025 |
| [sportsdataverse/cfbfastR-data](https://github.com/sportsdataverse/cfbfastR-data) `schedules/csv/` | scores, conferences, division, neutral-site and conference-game flags |
| [jackschooley/cfb-betting](https://github.com/jackschooley/cfb-betting) `data/cfb odds *.csv` | sportsbookreviewsonline closing lines, 2014-2019, used only for validation |

Validation against the second source: the favourite side agrees on 98.9% of
2,837 matched games, 91.7% of spreads are within half a point, and the mean
difference is -0.07 points.
