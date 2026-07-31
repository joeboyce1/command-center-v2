# Betting every college football underdog, 2006-2025

Backtest of two strategies over 20 seasons of FBS games:

1. **Moneyline** — back the underdog to win outright.
2. **Spread (ATS)** — back the underdog plus the points.

Flat $100 a game at the consensus closing line. 12,625 games have a closing
spread, 11,775 have a closing moneyline.

## The headline: both strategies lose, ATS loses less

| Strategy | Bets | Record | Win % | P&L | ROI | t |
|---|---|---|---|---|---|---|
| Underdog moneyline | 11,775 | 3,030-8,745 | 25.7% | **-$113,774** | **-9.7%** | -4.45 |
| Underdog ATS | 12,625 | 6,240-6,170-215 | 50.3% | **-$48,638** | **-3.9%** | -4.57 |

Blind underdog betting is a losing strategy in both markets, and the two lose
for different reasons.

**ATS loses to the vig, and only to the vig.** Underdogs cover 50.3% of the
time — statistically indistinguishable from a coin flip. Break-even at -110 is
52.4%. The -3.9% ROI is essentially the house edge, and it is remarkably
stable: no season better than +0.9%, none worse than -12.4%, and the number
barely moves whether you price every bet at a flat -110 (-3.94%) or use the
actual quoted closing prices (-3.85%).

**The moneyline loses to the favourite-longshot bias**, and it loses about
2.5x as much. Bettors systematically overpay for big underdogs:

| Dog line | Bets | Won outright | ROI |
|---|---|---|---|
| +0.5 to +3 | 2,204 | 47.6% | **+2.9%** |
| +3.5 to +7 | 2,969 | 35.0% | -0.8% |
| +7.5 to +10 | 1,461 | 25.0% | -6.6% |
| +10.5 to +14 | 1,645 | 19.5% | -7.8% |
| +14.5 to +21 | 1,905 | 10.2% | **-26.5%** |
| +21.5 to +28 | 1,009 | 5.2% | **-31.9%** |
| +28.5 or more | 580 | 1.7% | -21.5% |

The decline is monotonic and enormous. Small dogs are roughly fairly priced;
dogs of two touchdowns or more are priced as if they win two to three times as
often as they do. Restricting to dogs priced +500 or shorter lifts the overall
moneyline ROI from -9.7% to -2.9% — most of the loss lives in the tail.

The tail is also where the data is thinnest and the P&L most fragile. The five
biggest winning tickets in 20 seasons account for $31,475; drop them and the
moneyline ROI falls from -9.7% to -12.3%.

## Patterns

### 1. Small road dogs on the moneyline are the one profitable cut

| | Bets | Won outright | ROI | t |
|---|---|---|---|---|
| Road dog of +3 or less, ML | 1,108 | 49.9% | **+8.0%** | 2.46 |
| Home dog of +3 or less, ML | 955 | 43.8% | -5.0% | -1.44 |

Profitable in 15 of 19 seasons, and it holds in both halves: +9.8% ROI on 642
bets in 2006-2018, +5.6% on 466 bets in 2019-2025. Median price +117.

This is the only cut in the study that survives an out-of-sample split with a
positive ROI, and the mechanism is coherent: a home dog and a road dog at the
same number should win outright at the same rate, but road dogs of +3 or less
win 49.9% of the time against 43.8% for home dogs at the same line. The market
prices home-field into the moneyline more aggressively than results justify.

Treat the size with caution. Recomputed from a completely independent source
(sportsbookreviewsonline closing lines, 2014-2019), the same cut returns
**+3.7%** rather than the +11.8% our data shows over those same seasons — same
sign, roughly a third of the magnitude. The honest read is a small positive
edge of a few percent, not 8%.

### 2. Big home underdogs are the worst ATS bet in the sport

| | Bets | Covered | ROI | t |
|---|---|---|---|---|
| Home dog of +14.5 or more, ATS | 956 | 46.3% | **-11.3%** | -3.70 |
| Road dog of +14.5 or more, ATS | 2,829 | 50.3% | -4.0% | -2.23 |

Profitable in only 4 of 20 seasons, and it is stable out of sample: -10.6% in
2006-2018, -12.5% in 2019-2025. This is the strongest negative pattern in the
data, and it is strong enough that the other side of it clears the vig: laying
those favourites went 505-436-15 (53.7%) for +2.4% ROI at -110.

More generally, home underdogs are worse than road underdogs ATS across the
board (-5.9% vs -3.0%). The old "always take the home dog" heuristic is
inverted in this sample.

### 3. Rest matters, and the spread does not fully price it

| Rest situation | Bets | Covered | ROI | t |
|---|---|---|---|---|
| Dog rested 5+ more days | 1,038 | 52.6% | +0.5% | 0.16 |
| Dog rested 1-4 more days | 1,814 | 51.4% | -1.8% | -0.81 |
| Equal rest | 6,336 | 50.5% | -3.4% | -2.82 |
| Favourite rested 1-4 more days | 1,604 | 47.5% | **-9.1%** | -3.83 |
| Favourite rested 5+ more days | 1,045 | 49.6% | -5.3% | -1.80 |

A dog whose opponent is coming off extra rest covers only 47.5% and loses 9.1%
— profitable in 2 of 20 seasons. A dog off a bye against a favourite on a
normal week breaks even, which is as close as any ATS cut gets to beating the
number. The gradient is monotonic through the middle four buckets. The bye week
specifically is broken out in the next section.

### 3b. The bye week: it helps the underdog, and only the underdog

A bye here is 12-16 days since the team's last game. The rest-day distribution
is cleanly bimodal — 6-9 days for a normal week, 13-15 for a bye — so the
threshold is not a judgement call. 2,478 of the 12,672 FBS games have at least
one team off a bye.

| Rest matchup | Bets | Dog covers | Dog ATS ROI | t |
|---|---|---|---|---|
| **Dog off a bye, favourite normal** | 975 | **52.5%** | **+0.3%** | 0.10 |
| Favourite off a bye, dog normal | 976 | 50.2% | -4.0% | -1.33 |
| Both off a bye | 434 | 48.9% | -6.3% | -1.38 |
| Neither off a bye | 8,954 | 50.2% | -4.0% | -4.01 |

**An underdog off a bye is the only ATS cut in this entire study that does not
lose money.** It covers 52.5% against a break-even of 52.4%, and it does it in
both halves of the sample: +0.1% ROI on 577 bets in 2006-2018, +0.5% on 398
bets in 2019-2025. That consistency is the point — it is not a big edge, it is
a reliable *absence* of the usual 4-point drag.

Everything else about the bye is worthless or worse:

- **A rested favourite gets no bump.** Dogs facing one still cover 50.2% and
  still lose 4.0% — identical to the no-bye baseline. Laying those favourites
  loses 4.8%.
- **Backing whoever is off the bye, regardless of side**, loses 2.2% over 1,951
  bets (t=-1.04), profitable in 9 of 20 seasons. The whole benefit sits in the
  underdog half; averaging it with the favourite half destroys it.
- **On the moneyline, a rested favourite is a bad lay**: -6.6% over 923 bets
  (t=-3.22), the worst bye-related number in the study.
- **Both teams off a bye** is the worst rest matchup for a dog (-6.3%), though
  434 bets is thin.

Note this does *not* reproduce the rest finding from the previous section. The
-9.1% cut there was favourites with **1-4 extra days** — a Thursday-to-Saturday
edge, not a bye. A full bye for the favourite is worth roughly nothing; small
scheduling edges are what the number misses.

Inside the underdog-off-a-bye cell, nothing subdivides cleanly. Road (+1.4%)
beats home (-1.6%), conference games (+2.2%) beat non-conference (-6.9%), P5
and G5 are identical, and the line-size split runs +12.6%, -15.4%, +7.3%, 0.0%
across four ~200-bet buckets. A sign pattern that alternates like that is
noise, not structure. The honest statement is the top-level one: the bye is
worth about four points of ROI to an underdog, and it stops there.

Long layoffs of 17+ days (bowls, season restarts) are excluded from all of the
above; underdogs off one went 51.9% for -0.8% on 156 bets.

### 4. Conference is mostly noise — except for who the favourite is

No underdog conference is profitable ATS. The spread across conferences is
narrow (Sun Belt dogs -0.3% at the best, Conference USA -7.7% at the worst),
and the ranking does not hold up out of sample: ACC dogs go -0.3% then -5.8%,
Sun Belt -2.0% then +1.7%, SEC -7.1% then -3.6%. That is what noise looks like.

The favourite's conference carries a bit more signal:

| Favourite's conference | Bets | Dog ATS ROI | t |
|---|---|---|---|
| Big 12 | 1,294 | -8.0% | -3.04 |
| Pac-12 | 883 | -7.1% | -2.21 |
| SEC | 1,620 | -6.7% | -2.84 |
| ACC | 1,427 | -0.2% | -0.09 |
| Sun Belt | 894 | +1.0% | 0.30 |

Fading dogs against Big 12, Pac-12 and SEC favourites is the most consistent
conference-level effect, but even the best of these is only about 4 points of
ROI beyond the baseline, off a search over 14 conferences — it does not clear
a multiple-comparisons bar on its own.

On the moneyline the conference splits are much larger (American Athletic dogs
-23.9%, ACC dogs +0.7%), but that is mostly the line-size effect in disguise:
conferences whose dogs are usually large price into the longshot tail.

### 5. Where the tiers meet

| Matchup | Bets | ML ROI | ATS ROI |
|---|---|---|---|
| P5 dog vs P5 favourite | 5,205 / 5,598 | -6.4% | -4.5% |
| G5 dog vs G5 favourite | 4,328 / 4,622 | -9.8% | -2.6% |
| **G5 dog vs P5 favourite** | 1,442 / 1,587 | **-30.5%** | **-6.0%** |

The G5-visiting-a-P5 game is the single worst spot for an underdog bettor in
either market. Those dogs win outright 15.3% of the time and are priced as if
they win far more often. The ATS number (-6.0%, t=-2.52) says the points
themselves are also shaded against the dog, not just the moneyline.

### 6. Line movement

Dogs whose line moved a point or more *against* them between open and close —
the market taking the favourite — return -15.5% on the moneyline (2,822 bets,
t=-3.76) versus -7.8% for dogs the market moved toward. On the spread the same
split is nearly flat (-3.5% vs -3.7%), so the information in the move shows up
in outright wins rather than in covers. Note this cut only covers the 8,828
FBS games where the feed recorded an opener.

### 7. Things that turned out not to matter

- **Conference vs non-conference games**: -3.8% vs -4.1% ATS. No difference.
- **Time of season**: weeks 1-2 (-5.0%), weeks 3-5 (-2.5%), weeks 6-10 (-3.6%),
  week 11+ (-4.6%) ATS. No usable pattern.
- **Bowl games**: 134 ATS bets at -5.2%, but the odds feed only carries
  postseason lines for 2023-2025, so this is 3 seasons, not 20. Not enough to
  conclude anything.
- **Neutral sites**: +1.6% ATS on 447 bets (t=0.36) and -0.2% ML. Suggestive,
  far too few games.

## What this adds up to

The closing line in college football is close to efficient against the spread
— dogs cover 50.3% of the time, and the entire loss is transaction cost. It is
*not* efficient on the moneyline, but the inefficiency runs the wrong way for
an underdog strategy: big dogs are badly overpriced, so the market's mistake
costs the dog bettor money rather than making it.

The only place the bias runs in the underdog's favour is at the very top of the
board, where road teams getting three points or fewer win outright more often
than their price implies. That edge is real in two independent datasets but
small — somewhere between 3% and 8% ROI, on roughly 55 bets a season.

## Caveats

- **Closing lines, not available prices.** Every bet is priced at the median
  across the books the feed captured. A real bettor cannot get the median on
  demand; line shopping would help, being limited to one book would hurt.
- **Line timing.** The source stores each book's last recorded line rather than
  an explicitly timestamped close. Validation against sportsbookreviewsonline
  closing lines (2,837 games) puts 91.7% of spreads within half a point and the
  mean difference at -0.07 points, so they behave like closing numbers, but
  they are not certified as such.
- **Coverage is not the full schedule.** The feed carries 600-800 FBS games a
  season out of roughly 800-900 played, and postseason lines only from 2023.
  2020 has no moneylines at all. Which games get captured is not random.
- **Multiple comparisons.** This report tests roughly 100 segments. At a 5%
  threshold you would expect several false positives by chance, which is why
  every pattern above is also reported by season and split out of sample.
- **Sample sizes shrink fast.** Any cell under a few hundred bets — every
  neutral-site cut, every bowl cut, most conference-by-line cells — is noise
  dressed up as a finding.

## Reproducing

```
python cfb_underdog_backtest/fetch_data.py       # download raw sources
python cfb_underdog_backtest/build_dataset.py    # -> data/processed/games.csv
python cfb_underdog_backtest/validate_lines.py   # cross-check vs SBR
python cfb_underdog_backtest/backtest.py         # -> results/
```

Plus `python cfb_underdog_backtest/bye_analysis.py` for the bye-week section.

Outputs in `results/`: `report_fbs.txt` (the full FBS-vs-FBS report used
above), `report_all_divisions.txt` (including FCS opponents), `report_bye.txt`,
`segments.csv` (every segment as data), `validation.txt`.
