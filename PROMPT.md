# Reusable prompt: post-earnings day-after moves for any ticker

Replace `<TICKER>` (and the company name) and paste. Everything else is written to
work unchanged.

---

Build the history of `<TICKER>`'s day-after earnings price move, going as far back as
the data allows, and give me the same treatment as the CSCO analysis on the
`claude/csco-earnings-price-moves-0jpjls` branch of this repo — read
`README.md`, `scripts/csco_earnings_moves.py` and `data/csco_earnings_moves.csv`
there first and follow that structure.

**The measure.** For each quarterly report: close on the session the release landed
against the next session's close. Check whether `<TICKER>` reports before the open
(BMO) or after the close (AMC) and say which — for a BMO reporter the reaction is
the *same* session's close vs. the prior close, not the next day's, so get this
right before computing anything.

**Getting the data.** Try the normal market-data hosts first, but note this
environment's egress policy blocks nearly all of them (Stooq, Yahoo, Nasdaq, SEC,
FRED, stockanalysis, MarketChameleon — 403 at the proxy, via both curl and
WebFetch). GitHub raw/clone, PyPI, npm and Wikipedia are reachable. Probe quickly,
don't grind: if no source works, say so plainly and tell me what to drop in
(`Date,Open,High,Low,Close,Volume` CSV) rather than burning the session hunting.

**Finding the earnings dates.** If the price file has no dates, derive them from the
tape rather than from memory: determine the company's four reporting months, then
within each take the highest-volume session as the reaction day and the one before it
as the release. Report a `volume_vs_median` ratio (reaction volume ÷ median of the
previous 20 sessions) for every row so each detection is auditable, guard against a
trailing partial month producing a spurious final row, and sanity-check the output —
dates should cluster on the same weekday pattern, and the largest moves should match
reactions that actually happened. Flag any row where the volume ratio is weak or the
date looks off-pattern.

**Never fabricate a number.** Every percentage in the output must come from the price
file. If part of the range can't be computed, leave the gap, state exactly which
quarters are missing and why, and don't fill it from recalled press coverage.

**Deliverables**

1. `data/<ticker>_earnings_moves.csv` — one row per report: fiscal quarter, release
   date, next session, close before, close after, move %, volume ratio, weekday.
2. A script that re-derives everything from any longer CSV it's handed, so extending
   the series later needs no hand-maintained dates. Generalize
   `scripts/csco_earnings_moves.py` rather than forking it if that's clean — its
   reporting months and quarter labels are currently hardcoded to Cisco's July
   fiscal year end.
3. A README section: headline stats, the detection method, the adjustment caveat
   (split/dividend-adjusted closes differ from raw prints across ex-dividend dates),
   and any coverage gap.
4. Commit and push to the working branch.
5. An artifact, published, with the URL in your reply.

**The artifact.** Utilitarian-polished document, not a flashy landing page. Serif
display face over system sans, monospace for all figures with `tabular-nums`. Cool
near-black ink, an off-white plane, neutrals biased slightly toward the accent —
avoid the cream/serif/terracotta and purple-gradient defaults. Full three-state
theming: complete light palette on bare `:root`, tokens redefined under both
`@media (prefers-color-scheme: dark)` guarded with `:root:not([data-theme="light"])`
and `:root[data-theme="dark"]`, explicit token background on `body`, and no color
defined only inside a media or `[data-theme]` block.

Structure it as: stat band (n, mean, mean absolute move, hit rate, best, worst) →
a diverging bar chart of every reaction over time, zero baseline, blue up / red down,
year ticks, hover tooltip with both closes and the volume ratio, direct labels on the
three or four extremes → breakdowns by era and by fiscal quarter → the distribution
of absolute moves → the full sortable table of every report → a method section that
states plainly how release dates were found and what the caveats are. Load the
`dataviz` skill before writing chart code and run its palette validator on the
diverging pair for both light and dark surfaces. Then screenshot the rendered page in
both themes and actually look at it before publishing.

Tell me the two or three things the data says that I wouldn't have guessed.
