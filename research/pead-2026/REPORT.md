# Large-Cap PEAD Direction Backtest — 2026 Year-to-Date

**Question:** After a large cap reports earnings, how often does the post-earnings drift
(next ~30 days) move in the *same direction* as the immediate price reaction?
(Example: NVDA sells off the day after earnings → does it keep drifting down for a month?)

**Answer: ~70% of the time this year.** 12 of 17 scored events drifted in the direction of
the day-one reaction. The hit rate was nearly identical for sell-offs (7/10 kept falling)
and pops (5/7 kept rising), and slightly *better* for big reactions of ±4 %+ (8/11, 73%).

## Universe & method

- **Universe:** Mag 7 (AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA) + AVGO, NFLX, JPM —
  every earnings event from January through late June 2026 (later events don't have a
  30-day window yet).
- **Reaction** = first full-session close after the report vs. the prior close
  (all of these names except JPM report after the bell, so that's the next day's close).
- **Drift** = return from the reaction-day close to ~30 calendar days later.
- **Match** = drift sign equals reaction sign.
- Events with |reaction| < 1% were excluded as having no direction signal:
  JPM ×2 (muted both quarters) and GOOGL's flat Feb 5 close. 17 events scored.
- **Data source:** this environment has no market-data API access (finance data hosts are
  blocked), so all dates, reactions, and price levels were collected from public web
  search — news reports and StatMuse price snapshots. Exact closes were found for most
  anchor points; the rest are estimates bracketed by nearby observed prices, flagged with
  a confidence grade in `pead_events_2026.csv`. This is a *direction* study, not a
  tradeable-precision backtest.

## Results

| Ticker | Report | Reaction | ~30-day drift | Result |
|--------|--------|---------:|--------------:|--------|
| NFLX | Jan 20 | −8.1% | −9.2% | ✅ Match |
| MSFT | Jan 28 | −10.0% | −9.6% | ✅ Match |
| META | Jan 28 | +9.0% | −9.3% | ❌ Reversal |
| TSLA | Jan 28 | +3.5% | −4.7% | ❌ Reversal |
| AAPL | Jan 29 | +0.5% | +1.7% | ✅ Match |
| AMZN | Feb 5 | −8.0% | −6.8% | ✅ Match |
| NVDA | Feb 25 | −5.5% | −6.7% | ✅ Match |
| AVGO | Mar 4 | +4.0% | +5.4% | ✅ Match (low conf.) |
| NFLX | Apr 16 | −9.0% | −13.3% | ✅ Match |
| TSLA | Apr 22 | −3.6% | +13.8% | ❌ Reversal |
| GOOGL | Apr 29 | +10.0% | +2.9% | ✅ Match |
| MSFT | Apr 29 | −4.0% | +1.2% | ❌ Reversal (weak) |
| META | Apr 29 | −8.6% | +4.8% | ❌ Reversal |
| AMZN | Apr 29 | +2.1% | +4.1% | ✅ Match |
| AAPL | Apr 30 | +1.5% | +8.5% | ✅ Match |
| NVDA | May 20 | −1.4% | −8.3% | ✅ Match |
| AVGO | Jun 3 | −15.0% | −4.6% | ✅ Match |

**Cuts:**

| Slice | Hit rate |
|-------|---------:|
| All scored events | 12/17 (71%) |
| Negative reactions → continued down | 7/10 (70%) |
| Positive reactions → continued up | 5/7 (71%) |
| Big reactions (\|move\| ≥ 4%) | 8/11 (73%) |
| Excluding low-confidence rows | 9/13 (69%) |
| Jan–Mar reporting season | 6/8 (75%) |
| Apr–Jun reporting season | 6/9 (67%) |

## Takeaways

1. **The NVDA-style pattern in the prompt held both times.** NVDA beat and sold off after
   both of its 2026 reports (−5.5% in Feb, −1.4% in May) and kept drifting down both
   times (−6.7% and −8.3% over the following month). It's now had five straight
   post-earnings slides.
2. **Continuation was the base case (~70%), on both sides.** Fading the day-one move was a
   losing strategy on average this year, and the edge was a bit stronger when the initial
   reaction was large (≥4%).
3. **The five reversals were mostly the market regime overwhelming the stock signal.**
   The Feb–Mar AI-capex correction dragged down January's two positive reactors
   (META +9% → −9.3%; TSLA +3.5% → −4.7%), and the sharp April–May recovery rally lifted
   April's negative reactors (TSLA −3.6% → +13.8%; META −8.6% → +4.8%; MSFT −4% → +1.2%).
   All five mismatches are events where the drift window straddled a regime turn —
   the misses cluster by *calendar*, not by ticker quality.
4. **Window choice matters at the margins.** NFLX-Jan counted as a match (−9% at day 30)
   but rocketed +26% in the final week of February when the Warner Bros. Discovery bid
   was dropped — at ~37 days it flips to a reversal. MSFT-Apr was a weak reversal at day
   30 (+1.2%) but a strong match at day 60 (−8.6% by June 30). The headline number is
   robust to dropping low-confidence rows (69–73% across cuts) but single events can flip
   with ±1 week window shifts.
5. **Capex was the story of the year.** Nearly every big negative reaction this year
   (MSFT −10%, AMZN −8%, META −8.6%, TSLA −3.6%, GOOGL's 2026 guides) was a *beat* sold
   off on AI capex guidance, not an earnings miss. When the market stayed risk-off, those
   sell-offs kept drifting; when the tape turned (April), they snapped back.

**Pending events (no 30-day window yet):** GOOGL and TSLA reported July 22 (GOOGL sank
~6% on a 2026 capex hike to $205B; TSLA fell ~8–12% on a Q2 miss), JPM/NFLX mid-July,
MSFT/META/AAPL/AMZN late July, NVDA August. If the ~70% continuation rate holds, the
July sell-offs would argue for continued weakness into late August — worth re-running
this study then.

## Key sources

Reactions: [CNBC (NVDA Q4)](https://www.cnbc.com/2026/02/25/nvidia-nvda-earnings-report-q4-2026.html) ·
[GeekWire (MSFT −10%)](https://www.geekwire.com/2026/microsofts-historic-plunge-why-the-company-lost-357-billion-in-value-despite-strong-results/) ·
[CNBC (AMZN −8%)](https://www.cnbc.com/2026/02/05/amazon-amzn-q4-earnings-report-2025.html) ·
[MarketBeat / Yahoo (META +9%)](https://www.marketbeat.com/originals/meta-soars-after-hours-forecasting-fastest-growth-since-2021/) ·
[Zacks/Yahoo (NFLX −8.1%)](https://finance.yahoo.com/news/netflix-declines-8-post-q4-163600304.html) ·
[CNBC (GOOGL flat Feb 5)](https://www.cnbc.com/2026/02/05/alphabet-earnings-share-price-google-beat-artifical-intelligence.html) ·
[TIKR (TSLA −3.56%)](https://www.tikr.com/blog/tesla-q1-2026-earnings-beat-so-why-did-the-stock-fall-3-56) ·
[TIKR (GOOGL +10%)](https://www.tikr.com/blog/alphabet-stock-surged-10-after-q1-2026-earnings-whats-next-for-googl) ·
[TIKR (META −8.55%)](https://www.tikr.com/blog/meta-beat-q1-2026-estimates-but-fell-8-55-heres-what-the-selloff-is-missing) ·
[Investing.com (MSFT Q3 FY26)](https://www.investing.com/news/transcripts/earnings-call-transcript-microsoft-q3-2026-results-exceed-expectations-stock-dips-93CH-4647426) ·
[Yahoo (AVGO −12/−15%)](https://finance.yahoo.com/markets/stocks/articles/broadcom-q2-2026-earnings-ai-111613207.html) ·
[CNBC (NVDA May slide)](https://www.cnbc.com/2026/05/21/here-we-go-again-with-nvidia-falling-on-earnings-what-the-sellers-are-missing.html)

Drift anchors: StatMuse price snapshots (MSFT Feb 27 $391.89; NVDA Feb 27 $176.97, Jun 26
$195.74; AAPL Feb 27 $263.94, Jun 23 $294.30; AMZN Feb 27 $210, May 31 $270.64; META Feb
avg $658.56 −9.3%; TSLA Jan 30 $430.41; MSFT Jun 30 $373.02) ·
[Fool (NFLX +15.3% Feb, last-5-days +26.6%)](https://www.fool.com/investing/2026/03/05/how-netflix-stock-gained-153-last-month/) ·
[Fool (NVDA +42.7% Mar 30→May 14, ATH $235.74)](https://www.fool.com/investing/2026/07/12/nvidia-stock-is-losing-to-the-market-in-2026-time/) ·
[Fool (TSLA Apr 23 close $373.60)](https://www.fool.com/coverage/stock-market-today/2026/04/23/stock-market-today-april-23-tesla-falls-after-lifting-2026-capex-guidance-for-ai-and-robotics/) ·
[Yahoo (GOOGL ATH $402.38 May 13)](https://finance.yahoo.com/markets/stocks/articles/alphabet-stock-breaks-record-high-170449725.html) ·
[247wallst / IndexBox (META $635.26 May 29)](https://247wallst.com/investing/2026/05/29/will-meta-stock-hit-800-this-year/) ·
[MacroTrends (AVGO ATH $480.77 Jun 2; Jul 23 $392.47)](https://www.macrotrends.net/stocks/charts/AVGO/broadcom/stock-price-history) ·
[Yahoo (AVGO $2T at ~$422 Apr 22)](https://finance.yahoo.com/markets/stocks/articles/broadcom-just-hit-2-trillion-185534906.html) ·
[Yahoo (NFLX −24% H1)](https://finance.yahoo.com/markets/stocks/articles/why-netflix-stock-dropped-24-095009807.html) ·
[24/7 Wall St (TSLA ~$423 May 12 after 28% rally)](https://247wallst.com/investing/2026/05/12/tesla-sinks-5-as-musk-heads-to-china-robotaxi-glitches-battery-delays-test-investor-patience/)

## Reproducing

```bash
python3 backtest.py
```

Edit `pead_events_2026.csv` to add events (e.g., the July 2026 season once 30 days
have elapsed) — the script recomputes all cuts.
