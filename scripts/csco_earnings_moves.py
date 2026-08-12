#!/usr/bin/env python3
"""Detect CSCO post-earnings day-after moves from daily OHLCV.

Cisco reports AMC in Feb / May / Aug / Nov (fiscal year ends late July).
The trading session AFTER the release is reliably the highest-volume day of
that month, so we locate it by volume and measure close(D+1)/close(D)-1,
where D is the session the release landed after.
"""
import csv, statistics, sys
from datetime import date

PATH = sys.argv[1] if len(sys.argv) > 1 else "csco_1990_2017.txt"
REPORT_MONTHS = {2: "Q2 (Jan qtr)", 5: "Q3 (Apr qtr)", 8: "Q4 (Jul qtr)", 11: "Q1 (Oct qtr)"}

rows = []
with open(PATH) as fh:
    for r in csv.DictReader(fh):
        d = date.fromisoformat(r["Date"])
        rows.append((d, float(r["Close"]), float(r["Volume"])))
rows.sort(key=lambda x: x[0])
idx_by_month = {}
for i, (d, c, v) in enumerate(rows):
    idx_by_month.setdefault((d.year, d.month), []).append(i)

LAST = rows[-1][0]

out = []
for (y, m), idxs in sorted(idx_by_month.items()):
    if m not in REPORT_MONTHS:
        continue
    # Skip a month the file only partially covers: the real release may fall
    # after the last row, and the volume argmax would then be spurious.
    if len(idxs) < 15 and (LAST.year, LAST.month) == (y, m):
        continue
    # candidate reaction days: exclude month-edge days, need a prior session
    cand = [i for i in idxs if 2 <= rows[i][0].day <= 28 and i > 0]
    if not cand:
        continue
    i = max(cand, key=lambda k: rows[k][2])          # highest-volume session
    d_after, c_after, v_after = rows[i]
    d_before, c_before, _ = rows[i - 1]
    pct = (c_after / c_before - 1) * 100
    base = [rows[k][2] for k in range(max(0, i - 21), i - 1)]
    volratio = v_after / statistics.median(base) if base else float("nan")
    out.append(dict(fq=REPORT_MONTHS[m], report=d_before, after=d_after,
                    c_before=c_before, c_after=c_after, pct=pct,
                    volratio=volratio, dow=d_after.strftime("%a")))

print(f"{'FQ reported':<14}{'Earnings (AMC)':<16}{'Next close':<14}{'Close bfr':>10}"
      f"{'Close aft':>11}{'Move %':>9}{'Vol x':>7}  {'DoW'}")
for o in out:
    print(f"{o['fq']:<14}{o['report'].isoformat():<16}{o['after'].isoformat():<14}"
          f"{o['c_before']:>10.4f}{o['c_after']:>11.4f}{o['pct']:>+9.2f}"
          f"{o['volratio']:>7.1f}  {o['dow']}")

moves = [o["pct"] for o in out]
ups = [p for p in moves if p > 0]
print(f"\nn={len(moves)}  mean={statistics.mean(moves):+.2f}%  "
      f"median={statistics.median(moves):+.2f}%  "
      f"mean|move|={statistics.mean(abs(p) for p in moves):.2f}%  "
      f"up={len(ups)} ({len(ups)/len(moves)*100:.0f}%)  "
      f"best={max(moves):+.2f}%  worst={min(moves):+.2f}%")

with open("csco_earnings_moves_computed.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["fiscal_quarter", "earnings_date_amc", "next_session",
                "close_before", "close_after", "move_pct", "volume_vs_median", "dow"])
    for o in out:
        w.writerow([o["fq"], o["report"], o["after"], f"{o['c_before']:.4f}",
                    f"{o['c_after']:.4f}", f"{o['pct']:.2f}", f"{o['volratio']:.1f}", o["dow"]])
