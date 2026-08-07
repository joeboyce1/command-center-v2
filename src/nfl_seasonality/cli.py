"""Entry point: run the full NFL-seasonality study and write the report."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import analysis, backtest, charts, report
from .config import (
    ALL_SYMBOLS,
    FLUT_LONG_HISTORY_PROXY,
    FRONT_RUN,
    INITIAL_CAPITAL,
    MARKET_BENCHMARK,
    NFL_SEASON,
    N_PERMUTATIONS,
    RANDOM_SEED,
    ROBUSTNESS_EXCLUDE_YEARS,
    SECTOR_BENCHMARK,
    TICKERS,
    TRANSACTION_COST_BPS,
)
from .data import load_universe, synthetic_universe
from .stats_tests import permutation_pvalue
from .windows import in_window


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NFL-season seasonality study for gambling stocks")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="CSV cache directory")
    parser.add_argument("--out-dir", type=Path, default=Path("output"), help="Report/chart output directory")
    parser.add_argument("--force-download", action="store_true", help="Re-download even if cached")
    parser.add_argument("--permutations", type=int, default=N_PERMUTATIONS)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--cost-bps", type=float, default=TRANSACTION_COST_BPS)
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="OFFLINE SELF-TEST ONLY: fabricate prices with a known planted effect. "
             "Output is labelled SYNTHETIC and is not a finding about real securities.",
    )
    parser.add_argument("--no-charts", action="store_true")
    return parser.parse_args(argv)


def _scenario(
    daily_exc: pd.DataFrame,
    label: str,
    permutations: int,
    seed: int,
    window=NFL_SEASON,
) -> tuple[pd.DataFrame, dict]:
    per_ticker = analysis.window_comparison(
        daily_exc, window=window, n_permutations=permutations, seed=seed
    )
    pooled = analysis.pooled_comparison(
        daily_exc, window=window, n_permutations=permutations, seed=seed
    )
    per_ticker.insert(0, "scenario", label)
    pooled["scenario"] = label
    return per_ticker, pooled


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.data_dir.mkdir(parents=True, exist_ok=True)

    banner = ""
    if args.synthetic:
        banner = (
            "> **SYNTHETIC SELF-TEST OUTPUT - NOT REAL DATA.**\n"
            "> Prices were fabricated to exercise the pipeline offline, with a known effect planted\n"
            "> in DKNG and RSI. Nothing here says anything about real securities.\n\n"
        )
        print("*** SYNTHETIC MODE - fabricated prices, results are not findings ***")
        prices, earnings = synthetic_universe(args.data_dir)
    else:
        print(f"Loading {len(ALL_SYMBOLS)} symbols (cache: {args.data_dir})")
        prices, earnings = load_universe(args.data_dir, force=args.force_download)

    # ---------------- coverage ----------------
    coverage = analysis.coverage_table(prices)
    print("\nCoverage:")
    print(coverage.to_string(index=False))
    coverage.to_csv(args.out_dir / "coverage.csv", index=False)
    analysis.season_coverage_detail(prices).to_csv(args.out_dir / "season_coverage_detail.csv", index=False)

    thin = coverage[coverage["flag_lt_5_seasons"] & coverage["symbol"].isin(TICKERS)]
    for symbol in thin["symbol"]:
        print(f"  ! {symbol}: fewer than 5 full NFL seasons")

    # ---------------- returns ----------------
    if MARKET_BENCHMARK not in prices.columns:
        raise SystemExit(f"{MARKET_BENCHMARK} is required but was not loaded.")

    universe = [t for t in TICKERS if t in prices.columns]
    daily = analysis.daily_returns(prices)
    daily_exc_all = analysis.excess_daily_returns(daily, MARKET_BENCHMARK)
    daily_exc = daily_exc_all[universe]

    # ---------------- 1 & 2. monthly tables ----------------
    monthly_raw = analysis.monthly_returns(daily)[universe]
    monthly_exc = analysis.monthly_excess(prices, MARKET_BENCHMARK)[universe]

    stats_raw = analysis.monthly_stats(monthly_raw)
    stats_exc = analysis.monthly_stats(monthly_exc)
    significance = analysis.monthly_significance(monthly_exc)

    stats_raw.to_csv(args.out_dir / "monthly_stats_raw.csv", index=False)
    stats_exc.to_csv(args.out_dir / "monthly_stats_excess.csv", index=False)
    significance.to_csv(args.out_dir / "monthly_significance.csv", index=False)

    # ---------------- 3, 4, 6. season tests ----------------
    daily_exc_ex_years = analysis.exclude_years(daily_exc, ROBUSTNESS_EXCLUDE_YEARS)
    daily_exc_ex_earnings = analysis.drop_earnings_windows(daily_exc, earnings)

    scenarios = {
        "base": daily_exc,
        "ex_2020_2021": daily_exc_ex_years,
        "ex_earnings_weeks": daily_exc_ex_earnings,
    }

    per_ticker_frames, pooled_rows = [], []
    for i, (label, frame) in enumerate(scenarios.items()):
        print(f"\nRunning scenario '{label}' ({args.permutations:,} permutations)...")
        pt, pooled = _scenario(frame, label, args.permutations, args.seed + 100 * i)
        per_ticker_frames.append(pt)
        pooled_rows.append(pooled)

    # Front-run window on the base sample.
    pt_front, pooled_front = _scenario(
        daily_exc, "front_run_aug_dec", args.permutations, args.seed + 900, window=FRONT_RUN
    )
    per_ticker_frames.append(pt_front)
    pooled_rows.append(pooled_front)

    per_ticker_all = pd.concat(per_ticker_frames, ignore_index=True)
    pooled_all = pd.DataFrame(pooled_rows)
    per_ticker_all.to_csv(args.out_dir / "season_tests_by_ticker.csv", index=False)
    pooled_all.to_csv(args.out_dir / "season_tests_basket.csv", index=False)

    base_per_ticker = per_ticker_all[per_ticker_all["scenario"] == "base"].reset_index(drop=True)
    by_label = {row["scenario"]: row for row in pooled_rows}

    # ---------------- FLUT long-history proxy ----------------
    proxy_note = "_(proxy not retrieved)_\n"
    if FLUT_LONG_HISTORY_PROXY in prices.columns:
        proxy_exc = daily_exc_all[[FLUT_LONG_HISTORY_PROXY]].dropna()
        proxy_frame = analysis.window_comparison(
            proxy_exc, n_permutations=args.permutations, seed=args.seed + 777
        )
        proxy_frame.to_csv(args.out_dir / "flut_proxy_test.csv", index=False)
        proxy_note = report.md_table(
            proxy_frame[["ticker", "n_seasons", "in_bps_day", "off_bps_day", "diff_bps_day", "t_hac", "p_perm_rotate"]]
        )

    # ---------------- 5. backtest ----------------
    curves, perf = backtest.run_backtest(
        daily, universe, window=NFL_SEASON, initial_capital=INITIAL_CAPITAL, cost_bps=args.cost_bps
    )
    curves.to_csv(args.out_dir / "equity_curves.csv")
    perf.to_csv(args.out_dir / "backtest_summary.csv")

    daily_ex_years = analysis.exclude_years(daily, ROBUSTNESS_EXCLUDE_YEARS)
    curves_rb, perf_rb = backtest.run_backtest(
        daily_ex_years, universe, window=NFL_SEASON, initial_capital=INITIAL_CAPITAL, cost_bps=args.cost_bps
    )
    curves_rb.to_csv(args.out_dir / "equity_curves_ex_2020_2021.csv")
    perf_rb.to_csv(args.out_dir / "backtest_summary_ex_2020_2021.csv")

    # ---------------- charts ----------------
    chart_paths: list[Path] = []
    if not args.no_charts:
        tag = "SYNTHETIC - " if args.synthetic else ""
        chart_paths.append(
            charts.monthly_heatmap(
                analysis.month_heatmap_matrix(stats_exc, "mean"),
                args.out_dir / "heatmap_monthly_excess.png",
                subtitle=f"{tag}mean monthly return minus SPY, by calendar month; NFL window is Sep-Feb",
            )
        )
        chart_paths.append(
            charts.monthly_heatmap(
                analysis.month_heatmap_matrix(stats_raw, "mean"),
                args.out_dir / "heatmap_monthly_raw.png",
                title="Mean monthly raw return",
                subtitle=f"{tag}raw returns pick up general market seasonality - see the excess heatmap",
            )
        )
        chart_paths.append(
            charts.equity_curves(
                curves,
                args.out_dir / "equity_curves.png",
                subtitle=f"{tag}equal-weight basket held Sep 1 - Feb 15 only, {args.cost_bps:.0f}bps per switch, 0% on cash",
            )
        )
        chart_paths.append(
            charts.equity_curves(
                curves_rb,
                args.out_dir / "equity_curves_ex_2020_2021.png",
                title="Growth of $10,000 - excluding 2020 and 2021",
                subtitle=f"{tag}same rules, COVID crash and 2021 melt-up removed",
            )
        )
        chart_paths.append(
            charts.season_bars(
                base_per_ticker,
                args.out_dir / "season_vs_offseason.png",
                subtitle=f"{tag}*  fewer than 10 NFL seasons - not statistically meaningful",
            )
        )
        basket = daily_exc.mean(axis=1, skipna=True).dropna()
        mask = in_window(basket.index, NFL_SEASON).to_numpy()
        _, observed, null = permutation_pvalue(
            basket.to_numpy(), mask, args.permutations, args.seed, scheme="rotate"
        )
        if null.size:
            chart_paths.append(
                charts.permutation_histogram(
                    null, observed, args.out_dir / "permutation_null.png",
                    subtitle=f"{tag}{args.permutations:,} circular rotations of the season mask",
                )
            )

    # ---------------- report ----------------
    verdict = report.build_verdict(
        by_label.get("base", {}),
        by_label.get("ex_2020_2021", {}),
        by_label.get("ex_earnings_weeks", {}),
        base_per_ticker,
        coverage,
    )

    summary_cols = [
        "ticker", "n_seasons", "meaningful", "in_bps_day", "off_bps_day", "diff_bps_day",
        "in_annualised_pct", "diff_annualised_pct", "t_welch", "t_hac", "p_hac",
        "p_perm_rotate", "p_perm_bh", "p_perm_bonf",
    ]
    summary = base_per_ticker[summary_cols].sort_values("in_bps_day", ascending=False)

    top_monthly = (
        significance.dropna(subset=["p_raw"])
        .sort_values("p_raw")
        .head(15)[["ticker", "month_name", "n", "mean_excess", "t_stat", "p_raw", "p_bonferroni", "p_bh"]]
    )
    n_tests = int(significance["p_raw"].notna().sum())
    n_raw_hits = int((significance["p_raw"] < 0.05).sum())
    n_bh_hits = int((significance["p_bh"] < 0.10).sum())
    n_bonf_hits = int((significance["p_bonferroni"] < 0.05).sum())

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Do gambling stocks show NFL-season seasonality?",
        "",
        banner.rstrip("\n") if banner else "",
        f"_Generated {generated}. Season window Sep 1 - Feb 15. Excess return is vs {MARKET_BENCHMARK}. "
        f"{args.permutations:,} permutations, seed {args.seed}._",
        "",
        "## Verdict",
        "",
        f"**{verdict.headline}**",
        "",
        *[f"- {b}" for b in verdict.bullets],
        "",
        "## Summary table - ranked by in-season excess return",
        "",
        report.md_table(summary),
        "`in_bps_day` / `off_bps_day` are mean daily excess return over SPY inside and outside the season window. "
        "`p_perm_rotate` is the circular-rotation permutation p-value; `p_perm_bh` and `p_perm_bonf` correct it "
        "across the 9 tickers. `meaningful = no` means fewer than 10 NFL seasons.",
        "",
        "## Equal-weight basket - the single pre-specified test",
        "",
        report.md_table(
            pooled_all[[
                "scenario", "window", "n_days_in", "n_days_out", "in_bps_day", "off_bps_day",
                "diff_bps_day", "diff_annualised_pct", "t_welch", "t_hac", "p_hac",
                "p_perm_rotate", "p_perm_shuffle",
            ]]
        ),
        "",
        "## Coverage and season counts",
        "",
        report.md_table(coverage),
        "",
        "## Flutter long-history proxy",
        "",
        proxy_note,
        "Reported separately, not merged into the main tables - different currency, different trading hours, "
        "and a pre-2024 business with little NFL exposure.",
        "",
        "## Monthly excess-return tests (the 9 x 12 grid)",
        "",
        f"{n_tests} tests run. At the raw 5% level, {n_raw_hits} are 'significant' "
        f"(about {0.05 * n_tests:.0f} expected by chance). After Bonferroni at 5%: {n_bonf_hits}. "
        f"After Benjamini-Hochberg at 10% FDR: {n_bh_hits}.",
        "",
        "Fifteen smallest raw p-values:",
        "",
        report.md_table(top_monthly),
        "",
        "## Backtest - $10,000",
        "",
        report.md_table(perf.reset_index(names="sleeve")),
        "",
        "Excluding 2020-2021:",
        "",
        report.md_table(perf_rb.reset_index(names="sleeve")),
        "",
        "## Charts",
        "",
        *[f"![{p.stem}]({p.name})" for p in chart_paths],
        "",
        report.caveats_section(coverage),
        "",
        "## Files",
        "",
        "Raw prices are cached under `data/` (one CSV per symbol); every table above is also written "
        "as a CSV in this directory. Re-running with the same seed reproduces every number.",
        "",
    ]
    text = "\n".join(line for line in lines if line is not None)
    (args.out_dir / "REPORT.md").write_text(text, encoding="utf-8")

    print("\n" + "=" * 78)
    print(verdict.headline)
    print("=" * 78)
    for bullet in verdict.bullets:
        print(f"  - {bullet}")
    print(f"\nWrote {args.out_dir / 'REPORT.md'} and {len(chart_paths)} charts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
