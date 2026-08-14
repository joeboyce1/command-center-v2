"""Render a study run as a self-contained HTML report.

The report is generated from the same objects the terminal output uses, so the
figures on the page cannot drift from the figures in the study. Nothing here
recomputes a statistic; it only formats what the event study and the gates
produced.

The page is written as a fragment - no doctype or body wrapper - so it renders
both when opened directly from disk and when published as an artifact.
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field

import pandas as pd

from .validate import FAIL, PASS, WARN, Finding, collapse

# Verdict states. "Inconclusive" is a real outcome here, not a failure mode:
# the gates can pass while the effect still fails to separate from zero.
SUPPRESSED, SUPPORTED, INCONCLUSIVE = "suppressed", "supported", "inconclusive"

VERDICT_COPY = {
    SUPPRESSED: (
        "Verdict withheld",
        "The sample cannot support a conclusion. Per-event results are shown; "
        "the aggregate claim is not.",
    ),
    SUPPORTED: (
        "Drift continued in the direction of the move",
        "The signed drift separates from zero at the pre-registered horizon.",
    ),
    INCONCLUSIVE: (
        "No effect distinguishable from zero",
        "The gates passed, but the signed drift does not separate from noise "
        "at the pre-registered horizon.",
    ),
}


@dataclass
class ReportContext:
    """Everything the page needs, already computed."""

    signal: str
    threshold: float | None
    benchmark: str
    tickers: list[str]
    verdict_horizon: int
    findings: list[Finding]
    summary: pd.DataFrame  # horizons x stats, for the selected signal
    coverage: pd.DataFrame  # per-ticker events / fired
    per_event: pd.DataFrame
    can_conclude: bool
    n_events_total: int
    effective_n: float
    date_range: tuple[str, str] = ("", "")
    skipped: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if not self.can_conclude:
            return SUPPRESSED
        row = self._verdict_row()
        if row is None:
            return SUPPRESSED
        return SUPPORTED if abs(row["t_stat"]) >= 2.0 else INCONCLUSIVE

    def _verdict_row(self):
        if self.summary.empty:
            return None
        match = self.summary[self.summary.horizon_days == self.verdict_horizon]
        return None if match.empty else match.iloc[0]


CSS = """
:root {
  --ground:#f7f8fa; --surface:#ffffff; --surface-2:#f0f2f6;
  --ink:#161a22; --ink-2:#3d4757; --ink-3:#6b7688;
  --rule:#dfe3ea; --rule-2:#eceff4;
  --accent:#0e6c74; --accent-soft:rgba(14,108,116,.14);
  --good:#2f7d52; --warn:#8a5a0b; --crit:#a33a32;
  --good-bg:rgba(47,125,82,.10); --warn-bg:rgba(138,90,11,.10);
  --crit-bg:rgba(163,58,50,.10);
  --serif:'Iowan Old Style','Palatino Linotype',Palatino,Georgia,serif;
  --sans:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
  --mono:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:#12151b; --surface:#181c24; --surface-2:#1f242e;
    --ink:#e6e9ef; --ink-2:#b3bccb; --ink-3:#7f8a9c;
    --rule:#2a313d; --rule-2:#222833;
    --accent:#4fb3bd; --accent-soft:rgba(79,179,189,.18);
    --good:#5fb583; --warn:#c9964a; --crit:#d97a70;
    --good-bg:rgba(95,181,131,.14); --warn-bg:rgba(201,150,74,.14);
    --crit-bg:rgba(217,122,112,.14);
  }
}
:root[data-theme="dark"] {
  --ground:#12151b; --surface:#181c24; --surface-2:#1f242e;
  --ink:#e6e9ef; --ink-2:#b3bccb; --ink-3:#7f8a9c;
  --rule:#2a313d; --rule-2:#222833;
  --accent:#4fb3bd; --accent-soft:rgba(79,179,189,.18);
  --good:#5fb583; --warn:#c9964a; --crit:#d97a70;
  --good-bg:rgba(95,181,131,.14); --warn-bg:rgba(201,150,74,.14);
  --crit-bg:rgba(217,122,112,.14);
}
* { box-sizing:border-box; }
body {
  margin:0; background:var(--ground); color:var(--ink);
  font-family:var(--sans); line-height:1.55;
  -webkit-font-smoothing:antialiased;
}
.wrap { max-width:1060px; margin:0 auto; padding:40px 24px 72px; }
.eyebrow {
  font-family:var(--mono); font-size:11px; letter-spacing:.14em;
  text-transform:uppercase; color:var(--ink-3); margin:0 0 10px;
}
h1 { font-family:var(--serif); font-size:30px; line-height:1.2; margin:0 0 6px;
     text-wrap:balance; font-weight:600; letter-spacing:-.01em; }
h2 { font-family:var(--sans); font-size:13px; letter-spacing:.08em;
     text-transform:uppercase; color:var(--ink-3); margin:0 0 14px;
     font-weight:600; }
.sub { color:var(--ink-2); margin:0; font-size:15px; max-width:65ch; }
section { margin-top:40px; }

/* Verdict banner: severity is carried by a stripe and a label, never colour alone */
.verdict {
  display:flex; gap:18px; align-items:flex-start;
  background:var(--surface); border:1px solid var(--rule);
  border-left:4px solid var(--tone); border-radius:3px;
  padding:22px 24px; margin-top:24px;
}
.verdict-mark {
  font-family:var(--mono); font-size:11px; font-weight:700; letter-spacing:.1em;
  text-transform:uppercase; color:var(--tone); background:var(--tone-bg);
  padding:5px 9px; border-radius:3px; white-space:nowrap; flex-shrink:0;
}
.verdict h1 { font-size:24px; }
.tone-good { --tone:var(--good); --tone-bg:var(--good-bg); }
.tone-warn { --tone:var(--warn); --tone-bg:var(--warn-bg); }
.tone-crit { --tone:var(--crit); --tone-bg:var(--crit-bg); }

.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(148px,1fr));
         gap:1px; background:var(--rule); border:1px solid var(--rule);
         border-radius:3px; overflow:hidden; margin-top:20px; }
.stat { background:var(--surface); padding:16px 18px; }
.stat dt { font-family:var(--mono); font-size:10px; letter-spacing:.1em;
           text-transform:uppercase; color:var(--ink-3); margin:0 0 6px; }
.stat dd { margin:0; font-family:var(--mono); font-size:21px; font-weight:600;
           font-variant-numeric:tabular-nums; letter-spacing:-.02em; }
.stat .note { font-size:11px; color:var(--ink-3); font-family:var(--sans);
              font-weight:400; letter-spacing:0; margin-top:3px; }

.card { background:var(--surface); border:1px solid var(--rule);
        border-radius:3px; padding:22px 24px; }
figcaption { font-size:12px; color:var(--ink-3); margin-top:12px; }

.findings { list-style:none; margin:0; padding:0; display:flex;
            flex-direction:column; gap:1px; background:var(--rule);
            border:1px solid var(--rule); border-radius:3px; overflow:hidden; }
.findings li { background:var(--surface); padding:11px 16px; display:flex;
               gap:12px; align-items:baseline; font-size:13.5px; }
.tag { font-family:var(--mono); font-size:10px; font-weight:700;
       letter-spacing:.08em; padding:2px 7px; border-radius:2px;
       flex-shrink:0; min-width:52px; text-align:center; }
.tag-pass { color:var(--good); background:var(--good-bg); }
.tag-warn { color:var(--warn); background:var(--warn-bg); }
.tag-fail { color:var(--crit); background:var(--crit-bg); }
.f-check { font-family:var(--mono); font-size:12px; color:var(--ink-2);
           flex-shrink:0; }
.f-detail { color:var(--ink-2); }

.scroll { overflow-x:auto; border:1px solid var(--rule); border-radius:3px;
          background:var(--surface); }
table { border-collapse:collapse; width:100%; font-family:var(--mono);
        font-size:12.5px; font-variant-numeric:tabular-nums; }
th { text-align:right; font-weight:600; color:var(--ink-3); font-size:10px;
     letter-spacing:.08em; text-transform:uppercase; padding:11px 12px;
     border-bottom:1px solid var(--rule); white-space:nowrap;
     position:sticky; top:0; background:var(--surface); }
td { text-align:right; padding:9px 12px; border-bottom:1px solid var(--rule-2);
     white-space:nowrap; color:var(--ink-2); }
th:first-child, td:first-child { text-align:left; }
tr:last-child td { border-bottom:none; }
tbody tr:hover td { background:var(--surface-2); }
td.key { color:var(--ink); font-weight:600; }
.pos { color:var(--good); }
.neg { color:var(--crit); }
.row-mark td { background:var(--accent-soft); }
.tall { max-height:460px; overflow-y:auto; }

.bar { display:block; height:5px; border-radius:3px; background:var(--accent);
       min-width:2px; }
.bar-track { background:var(--surface-2); border-radius:3px; width:110px;
             display:inline-block; vertical-align:middle; }

.chart-wrap { position:relative; }
svg { display:block; width:100%; height:auto; }
.tip { position:absolute; pointer-events:none; opacity:0; transition:opacity .12s;
       background:var(--ink); color:var(--ground); font-family:var(--mono);
       font-size:11.5px; padding:7px 10px; border-radius:3px; white-space:nowrap;
       transform:translate(-50%,-120%); z-index:5; }
.tip.on { opacity:1; }
.hit:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }

footer { margin-top:48px; padding-top:20px; border-top:1px solid var(--rule);
         color:var(--ink-3); font-size:12.5px; }
code { font-family:var(--mono); font-size:.92em; background:var(--surface-2);
       padding:1px 5px; border-radius:2px; }
@media (prefers-reduced-motion:reduce) { * { transition:none !important; } }
@media (max-width:620px) {
  .wrap { padding:28px 16px 56px; }
  .verdict { flex-direction:column; gap:12px; }
  h1 { font-size:24px; }
}
"""


def _esc(value) -> str:
    return html.escape(str(value))


def _sign_class(text: str) -> str:
    text = str(text)
    if text.startswith("+"):
        return "pos"
    if text.startswith("-"):
        return "neg"
    return ""


def _chart(ctx: ReportContext) -> str:
    """Mean signed drift by horizon, with a +/-1 standard-error band.

    One series, so no legend - the title names it. The band is the point of
    the chart: where it straddles zero, the effect is not distinguishable
    from noise, which is the question the whole study asks.
    """
    frame = ctx.summary
    if frame.empty:
        return '<p class="sub">No horizons produced a signed sample.</p>'

    w, h = 720, 280
    pad_l, pad_r, pad_t, pad_b = 52, 18, 18, 34
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b

    horizons = list(frame.horizon_days)
    means = list(frame.mean_signed_car)
    ses = [
        (row.stdev / math.sqrt(row.n_events)) if row.n_events > 1 and row.stdev == row.stdev else 0.0
        for row in frame.itertuples()
    ]

    lo = min(min(m - s for m, s in zip(means, ses)), 0.0)
    hi = max(max(m + s for m, s in zip(means, ses)), 0.0)
    span = (hi - lo) or 0.02
    lo, hi = lo - span * 0.12, hi + span * 0.12

    def px(i: int) -> float:
        if len(horizons) == 1:
            return pad_l + plot_w / 2
        return pad_l + plot_w * i / (len(horizons) - 1)

    def py(v: float) -> float:
        return pad_t + plot_h * (hi - v) / (hi - lo)

    parts: list[str] = [
        f'<svg viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="Mean signed drift by horizon, with one standard error band">'
    ]

    # Recessive gridlines and y labels.
    steps = 5
    for i in range(steps + 1):
        value = lo + (hi - lo) * i / steps
        y = py(value)
        parts.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w - pad_r}" y2="{y:.1f}" '
            f'stroke="var(--rule-2)" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l - 9}" y="{y + 3.5:.1f}" text-anchor="end" '
            f'font-family="var(--mono)" font-size="10" fill="var(--ink-3)">'
            f'{value * 100:+.0f}%</text>'
        )

    # Zero is the reference the whole page is about, so it is drawn solid.
    parts.append(
        f'<line x1="{pad_l}" y1="{py(0):.1f}" x2="{w - pad_r}" y2="{py(0):.1f}" '
        f'stroke="var(--ink-3)" stroke-width="1.25"/>'
    )

    band_top = " ".join(f"{px(i):.1f},{py(m + s):.1f}" for i, (m, s) in enumerate(zip(means, ses)))
    band_bot = " ".join(
        f"{px(i):.1f},{py(m - s):.1f}" for i, (m, s) in reversed(list(enumerate(zip(means, ses))))
    )
    parts.append(f'<polygon points="{band_top} {band_bot}" fill="var(--accent-soft)"/>')

    line = " ".join(f"{px(i):.1f},{py(m):.1f}" for i, m in enumerate(means))
    parts.append(
        f'<polyline points="{line}" fill="none" stroke="var(--accent)" '
        f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
    )

    for i, (horizon, mean) in enumerate(zip(horizons, means)):
        emphasized = horizon == ctx.verdict_horizon
        radius = 5.5 if emphasized else 3.5
        parts.append(
            f'<circle cx="{px(i):.1f}" cy="{py(mean):.1f}" r="{radius}" '
            f'fill="var(--accent)" stroke="var(--surface)" stroke-width="2"/>'
        )
        if emphasized:
            parts.append(
                f'<text x="{px(i):.1f}" y="{py(mean) - 14:.1f}" text-anchor="middle" '
                f'font-family="var(--mono)" font-size="12" font-weight="700" '
                f'fill="var(--ink)">{mean * 100:+.1f}%</text>'
            )
        parts.append(
            f'<text x="{px(i):.1f}" y="{h - 12}" text-anchor="middle" '
            f'font-family="var(--mono)" font-size="10" '
            f'fill="{"var(--ink)" if emphasized else "var(--ink-3)"}">+{horizon}d</text>'
        )

    # Hit targets are wider than the marks, per interaction guidance.
    half = plot_w / max(len(horizons) - 1, 1) / 2
    for i, row in enumerate(frame.itertuples()):
        tip = (
            f"+{row.horizon_days}d  mean {row.mean_signed_car * 100:+.2f}%  "
            f"t {row.t_stat:+.2f}  hit {row.hit_rate * 100:.0f}%  n {row.n_events}"
        )
        parts.append(
            f'<rect class="hit" x="{px(i) - half:.1f}" y="{pad_t}" '
            f'width="{half * 2:.1f}" height="{plot_h}" fill="transparent" '
            f'tabindex="0" data-tip="{_esc(tip)}" data-x="{px(i) / w:.4f}"/>'
        )

    parts.append("</svg>")
    return "".join(parts)


def _findings(findings: list[Finding], max_pass: int = 4) -> str:
    findings = collapse(findings)
    tags = {PASS: "tag-pass", WARN: "tag-warn", FAIL: "tag-fail"}
    fails = [f for f in findings if f.level == FAIL]
    warns = [f for f in findings if f.level == WARN]
    passes = [f for f in findings if f.level == PASS]

    rows = []
    for finding in fails + warns:
        rows.append(
            f'<li><span class="tag {tags[finding.level]}">{finding.level}</span>'
            f'<span class="f-check">{_esc(finding.check)}</span>'
            f'<span class="f-detail">{_esc(finding.detail)}</span></li>'
        )
    if len(passes) > max_pass:
        rows.append(
            f'<li><span class="tag tag-pass">PASS</span>'
            f'<span class="f-detail">{len(passes)} other checks clean '
            f"(prices, events, alignment)</span></li>"
        )
    else:
        for finding in passes:
            rows.append(
                f'<li><span class="tag tag-pass">PASS</span>'
                f'<span class="f-check">{_esc(finding.check)}</span>'
                f'<span class="f-detail">{_esc(finding.detail)}</span></li>'
            )
    return f'<ul class="findings">{"".join(rows)}</ul>'


def _horizon_table(ctx: ReportContext) -> str:
    head = (
        "<tr><th>Horizon</th><th>Events</th><th>Mean signed</th><th>Median</th>"
        "<th>Std dev</th><th>t-stat</th><th>Hit rate</th></tr>"
    )
    rows = []
    for row in ctx.summary.itertuples():
        mark = ' class="row-mark"' if row.horizon_days == ctx.verdict_horizon else ""
        mean = f"{row.mean_signed_car:+.2%}"
        median = f"{row.median_signed_car:+.2%}"
        t = f"{row.t_stat:+.2f}"
        rows.append(
            f"<tr{mark}><td class='key'>+{row.horizon_days}d</td>"
            f"<td>{row.n_events}</td>"
            f"<td class='{_sign_class(mean)}'>{mean}</td>"
            f"<td class='{_sign_class(median)}'>{median}</td>"
            f"<td>{row.stdev:.2%}</td>"
            f"<td class='{_sign_class(t)}'>{t}</td>"
            f"<td>{row.hit_rate:.0%}</td></tr>"
        )
    return f'<div class="scroll"><table>{head}{"".join(rows)}</table></div>'


def _coverage_table(ctx: ReportContext) -> str:
    if ctx.coverage.empty:
        return ""
    peak = max(int(r.fired) for r in ctx.coverage.itertuples()) or 1
    rows = []
    for row in ctx.coverage.itertuples():
        width = int(round(100 * int(row.fired) / peak))
        rows.append(
            f"<tr><td class='key'>{_esc(row.ticker)}</td>"
            f"<td>{row.events}</td><td>{row.fired}</td>"
            f"<td>{_esc(row.share_of_signals)}</td>"
            f"<td style='text-align:left'><span class='bar-track'>"
            f"<span class='bar' style='width:{width}%'></span></span></td></tr>"
        )
    head = (
        "<tr><th>Ticker</th><th>Events</th><th>Fired</th><th>Share</th>"
        "<th style='text-align:left'>&nbsp;</th></tr>"
    )
    return f'<div class="scroll"><table>{head}{"".join(rows)}</table></div>'


def _event_table(frame: pd.DataFrame) -> str:
    head = "<tr>" + "".join(f"<th>{_esc(c)}</th>" for c in frame.columns) + "</tr>"
    rows = []
    for record in frame.to_dict("records"):
        cells = []
        for i, col in enumerate(frame.columns):
            value = record[col]
            css = "key" if i < 2 else _sign_class(value)
            cells.append(f"<td class='{css}'>{_esc(value)}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return f'<div class="scroll tall"><table>{head}{"".join(rows)}</table></div>'


def render(ctx: ReportContext) -> str:
    verdict = ctx.verdict
    tone = {SUPPRESSED: "tone-crit", SUPPORTED: "tone-good", INCONCLUSIVE: "tone-warn"}[verdict]
    mark = {SUPPRESSED: "Withheld", SUPPORTED: "Supported", INCONCLUSIVE: "Inconclusive"}[verdict]
    heading, blurb = VERDICT_COPY[verdict]

    row = ctx._verdict_row()
    threshold = ctx.threshold if ctx.threshold is not None else "default"
    fired = int(ctx.coverage.fired.sum()) if not ctx.coverage.empty else 0
    fire_rate = fired / ctx.n_events_total if ctx.n_events_total else 0.0

    stats = [
        ("Events", f"{ctx.n_events_total:,}", f"{len(ctx.tickers)} tickers"),
        ("Signals fired", f"{fired:,}", f"{fire_rate:.0%} of events"),
        (
            "Effective n",
            f"{ctx.effective_n:.0f}",
            "after earnings-week clustering",
        ),
    ]
    if row is not None:
        stats.append(
            (f"Mean drift +{ctx.verdict_horizon}d", f"{row['mean_signed_car']:+.2%}", "signed by signal")
        )
        stats.append(("t-statistic", f"{row['t_stat']:+.2f}", "2.0 clears the bar"))
        stats.append(("Hit rate", f"{row['hit_rate']:.0%}", "drift matched the move"))

    tiles = "".join(
        f'<div class="stat"><dt>{_esc(label)}</dt><dd>{_esc(value)}'
        f'<div class="note">{_esc(note)}</div></dd></div>'
        for label, value, note in stats
    )

    skipped = ""
    if ctx.skipped:
        items = "".join(f"<li><span class='tag tag-warn'>SKIP</span>"
                        f"<span class='f-detail'>{_esc(s)}</span></li>" for s in ctx.skipped)
        skipped = f'<section><h2>Skipped</h2><ul class="findings">{items}</ul></section>'

    span = ""
    if ctx.date_range[0]:
        span = f"{ctx.date_range[0]} to {ctx.date_range[1]} &middot; "

    return f"""<title>Big-Move Drift Study</title>
<style>{CSS}</style>
<div class="wrap">
  <p class="eyebrow">Post-earnings drift &middot; event study</p>
  <h1>Does a bigger-than-normal earnings move keep going?</h1>
  <p class="sub">Signal <code>{_esc(ctx.signal)}</code> at threshold
     <code>{_esc(threshold)}</code>, drift measured from the session after the
     announcement, abnormal to <code>{_esc(ctx.benchmark)}</code>. {span}
     Pre-registered horizon +{ctx.verdict_horizon} sessions.</p>

  <div class="verdict {tone}">
    <span class="verdict-mark">{_esc(mark)}</span>
    <div><h1>{_esc(heading)}</h1><p class="sub">{_esc(blurb)}</p></div>
  </div>

  <dl class="stats">{tiles}</dl>

  <section>
    <h2>Signed drift by horizon</h2>
    <figure class="card chart-wrap" style="margin:0">
      {_chart(ctx)}
      <div class="tip" id="tip"></div>
      <figcaption>Mean drift after the signal fires, signed so a correct
        prediction is positive. The shaded band is one standard error: where it
        crosses zero, the effect is not separable from noise.</figcaption>
    </figure>
  </section>

  <section><h2>Data quality</h2>{_findings(ctx.findings)}</section>
  {skipped}
  <section><h2>Horizons</h2>{_horizon_table(ctx)}</section>
  <section><h2>Per-ticker coverage</h2>{_coverage_table(ctx)}
    <p class="sub" style="margin-top:12px;font-size:13px">If one name owns most
      of the fired signals, the pooled result is that name's result.</p></section>
  <section><h2>Events</h2>{_event_table(ctx.per_event)}</section>

  <footer>Generated by <code>run_backtest.py --report</code>. Every figure comes
    from the price series on disk; none is recalled or estimated. A withheld
    verdict means the sample could not detect an effect this size, not that the
    effect is absent.</footer>
</div>
<script>
(function () {{
  var tip = document.getElementById('tip');
  if (!tip) return;
  document.querySelectorAll('.hit').forEach(function (hit) {{
    function show() {{
      tip.textContent = hit.dataset.tip;
      tip.style.left = (parseFloat(hit.dataset.x) * 100) + '%';
      tip.style.top = '38%';
      tip.classList.add('on');
    }}
    function hide() {{ tip.classList.remove('on'); }}
    hit.addEventListener('mouseenter', show);
    hit.addEventListener('focus', show);
    hit.addEventListener('mouseleave', hide);
    hit.addEventListener('blur', hide);
  }});
}})();
</script>"""
