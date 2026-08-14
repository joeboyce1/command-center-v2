"""Render a study run as a self-contained HTML table.

One row per earnings event: what the stock did on the session after the
release, and what it did over the 30 and 60 calendar days that followed.

Every figure comes from the price series the study read, so the page and the
run cannot disagree. These are raw price moves, not benchmark-adjusted - the
abnormal returns and the statistics live in the terminal output, because this
page exists to be scanned, not to carry a conclusion.

The page is written as a fragment - no doctype or body wrapper - so it renders
both when opened from disk and when published as an artifact.
"""

from __future__ import annotations

import html

# 21 trading sessions is about 30 calendar days, 42 is about 60.
D30_SESSIONS, D60_SESSIONS = 21, 42


def rows_from_results(results, signal: str, threshold: float | None) -> list[dict]:
    """Flatten event results into the handful of fields the page shows."""
    rows = []
    for result in results:
        move = result.announcement_raw
        d30 = result.raw_drift.get(D30_SESSIONS)
        d60 = result.raw_drift.get(D60_SESSIONS)
        # "Kept going" is judged on the 60-day move when there is one, since
        # that is the horizon the thesis is about.
        later = d60 if d60 is not None else d30
        rows.append(
            {
                "ticker": result.event.ticker,
                "date": result.event_day.date().isoformat(),
                "move": move,
                "d30": d30,
                "d60": d60,
                "same_way": None if later is None else (later > 0) == (move > 0),
                "big": bool(result.signal(signal, threshold)),
            }
        )
    return sorted(rows, key=lambda r: (r["ticker"], r["date"]))


CSS = """
:root {
  --ground:#f7f8fa; --surface:#ffffff; --surface-2:#f1f3f7;
  --ink:#161a22; --ink-2:#48525f; --ink-3:#798393;
  --rule:#e1e5ec; --rule-2:#eef1f5;
  --up:#1f7a4d; --down:#b23c33; --accent:#0e6c74;
  --sans:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
  --mono:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:#11141a; --surface:#171b22; --surface-2:#212632;
    --ink:#e8ebf1; --ink-2:#aeb7c5; --ink-3:#798393;
    --rule:#272e39; --rule-2:#1f242e;
    --up:#5cb98a; --down:#e08279; --accent:#4fb3bd;
  }
}
:root[data-theme="dark"] {
  --ground:#11141a; --surface:#171b22; --surface-2:#212632;
  --ink:#e8ebf1; --ink-2:#aeb7c5; --ink-3:#798393;
  --rule:#272e39; --rule-2:#1f242e;
  --up:#5cb98a; --down:#e08279; --accent:#4fb3bd;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--ground); color:var(--ink);
       font-family:var(--sans); -webkit-font-smoothing:antialiased; }
.wrap { max-width:760px; margin:0 auto; padding:44px 20px 80px; }
h1 { font-size:23px; font-weight:600; margin:0 0 6px; letter-spacing:-.01em; }
.sub { color:var(--ink-3); font-size:14px; margin:0 0 26px; }

.controls { display:flex; gap:10px; align-items:center; margin-bottom:14px;
            flex-wrap:wrap; }
input[type=search] {
  flex:1; min-width:150px; font-family:var(--mono); font-size:13px;
  padding:9px 12px; border:1px solid var(--rule); border-radius:4px;
  background:var(--surface); color:var(--ink);
}
input[type=search]::placeholder { color:var(--ink-3); }
input[type=search]:focus-visible { outline:2px solid var(--accent);
                                   outline-offset:1px; }
.toggle { display:flex; align-items:center; gap:7px; font-size:13px;
          color:var(--ink-2); cursor:pointer; user-select:none;
          padding:9px 12px; border:1px solid var(--rule); border-radius:4px;
          background:var(--surface); white-space:nowrap; }
.toggle input { accent-color:var(--accent); margin:0; cursor:pointer; }
.count { font-family:var(--mono); font-size:12px; color:var(--ink-3);
         margin-bottom:10px; }

.scroll { overflow-x:auto; border:1px solid var(--rule); border-radius:4px;
          background:var(--surface); }
table { border-collapse:collapse; width:100%; font-family:var(--mono);
        font-size:13px; font-variant-numeric:tabular-nums; }
th { text-align:right; font-weight:600; color:var(--ink-3); font-size:10px;
     letter-spacing:.09em; text-transform:uppercase; padding:12px 14px;
     border-bottom:1px solid var(--rule); white-space:nowrap;
     position:sticky; top:0; background:var(--surface); z-index:1; }
td { text-align:right; padding:10px 14px; border-bottom:1px solid var(--rule-2);
     white-space:nowrap; color:var(--ink-2); }
th:first-child, td:first-child { text-align:left; }
th:nth-child(2), td:nth-child(2) { text-align:left; }
tr:last-child td { border-bottom:none; }
tbody tr:hover td { background:var(--surface-2); }
td.tick { color:var(--ink); font-weight:600; }
td.move { color:var(--ink); font-weight:600; }
.up { color:var(--up); }
/* The last column must not reuse up/down colour: green already means "price
   rose" in the percent columns, and "kept going" is a different claim. */
.went { color:var(--accent); font-weight:600; }
.turned { color:var(--ink-3); }
.down { color:var(--down); }
.flat { color:var(--ink-3); }
.dot { display:inline-block; width:7px; height:7px; border-radius:50%;
       margin-right:7px; vertical-align:1px; }
.dot-big { background:var(--accent); }
.dot-small { background:var(--rule); }
.empty { padding:36px 14px; text-align:center; color:var(--ink-3);
         font-size:14px; }
footer { margin-top:22px; color:var(--ink-3); font-size:12.5px; line-height:1.6; }
.key { display:flex; gap:16px; flex-wrap:wrap; margin-top:10px;
       font-size:12px; color:var(--ink-3); }
@media (max-width:560px) {
  .wrap { padding:28px 14px 60px; }
  th, td { padding:9px 10px; }
}
"""


def _esc(value) -> str:
    return html.escape(str(value))


def _pct(value) -> str:
    return "—" if value is None else f"{value * 100:+.1f}%"


def _tone(value) -> str:
    if value is None:
        return "flat"
    if value > 0.0005:
        return "up"
    if value < -0.0005:
        return "down"
    return "flat"


def render(rows: list[dict], subtitle: str = "") -> str:
    body = []
    for row in rows:
        dot = "dot-big" if row["big"] else "dot-small"
        if row["same_way"] is None:
            same = '<td class="flat">—</td>'
        elif row["same_way"]:
            same = '<td class="went">kept going</td>'
        else:
            same = '<td class="turned">reversed</td>'

        body.append(
            f'<tr data-t="{_esc(row["ticker"].lower())}" '
            f'data-big="{"1" if row["big"] else "0"}">'
            f'<td class="tick"><span class="dot {dot}"></span>{_esc(row["ticker"])}</td>'
            f'<td>{_esc(row["date"])}</td>'
            f'<td class="move {_tone(row["move"])}">{_pct(row["move"])}</td>'
            f'<td class="{_tone(row["d30"])}">{_pct(row["d30"])}</td>'
            f'<td class="{_tone(row["d60"])}">{_pct(row["d60"])}</td>'
            f"{same}</tr>"
        )

    big = sum(1 for r in rows if r["big"])
    tickers = len({r["ticker"] for r in rows})

    return f"""<title>Earnings Drift Tape</title>
<style>{CSS}</style>
<div class="wrap">
  <h1>Earnings move, and what happened next</h1>
  <p class="sub">{_esc(subtitle)}</p>

  <div class="controls">
    <input type="search" id="q" placeholder="Filter ticker…"
           aria-label="Filter by ticker">
    <label class="toggle"><input type="checkbox" id="onlybig">
      Big moves only</label>
  </div>
  <p class="count" id="count"></p>

  <div class="scroll">
    <table>
      <thead><tr>
        <th>Ticker</th><th>Earnings</th><th>Next session</th>
        <th>+30 days</th><th>+60 days</th><th>Then</th>
      </tr></thead>
      <tbody id="rows">{"".join(body)}</tbody>
    </table>
    <div class="empty" id="empty" hidden>No rows match.</div>
  </div>

  <footer>
    Raw price moves from the close before the release. &ldquo;Next session&rdquo;
    is the first full trading day after the announcement, never the after-hours
    print. {len(rows)} events across {tickers} tickers; {big} were big moves.
    <div class="key">
      <span><span class="dot dot-big"></span>big move</span>
      <span><span class="dot dot-small"></span>ordinary</span>
      <span>&mdash; = not enough trading days yet</span>
      <span>green/red = price up/down &middot; teal = move continued</span>
    </div>
  </footer>
</div>
<script>
(function () {{
  var q = document.getElementById('q'),
      onlyBig = document.getElementById('onlybig'),
      rows = Array.prototype.slice.call(
        document.getElementById('rows').getElementsByTagName('tr')),
      count = document.getElementById('count'),
      empty = document.getElementById('empty');

  function apply() {{
    var term = q.value.trim().toLowerCase(), shown = 0;
    rows.forEach(function (row) {{
      var ok = (!term || row.dataset.t.indexOf(term) === 0) &&
               (!onlyBig.checked || row.dataset.big === '1');
      row.hidden = !ok;
      if (ok) shown++;
    }});
    count.textContent = shown + ' event' + (shown === 1 ? '' : 's');
    empty.hidden = shown > 0;
  }}

  q.addEventListener('input', apply);
  onlyBig.addEventListener('change', apply);
  apply();
}})();
</script>"""
