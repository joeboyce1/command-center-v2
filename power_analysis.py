#!/usr/bin/env python3
"""How many earnings events does this strategy need before a result means anything?

The CRWV study produced 4 confirmations out of 5. This asks the prior question:
at the effect sizes PEAD actually delivers, how large a sample separates a real
edge from noise?

Two things drive the answer:

* **Effect size** - the mean signed abnormal drift per event. Published
  post-earnings drift, conditioned on the announcement return, runs roughly
  1-4% over 60 days in modern samples, and has decayed over time.
* **Dispersion** - the standard deviation of 60-day abnormal returns per event.
  This is the killer. For a high-volatility name it is 30%+, i.e. an order of
  magnitude larger than the effect being measured.

There is also a correlation penalty that most retail backtests miss entirely,
so it gets its own section below.
"""

from __future__ import annotations

import numpy as np

# Mean signed abnormal drift per event over ~60 days.
EFFECT_SIZES = (0.01, 0.02, 0.03, 0.04)

# Per-event standard deviation of 60-day abnormal returns, by name type.
DISPERSIONS = {
    "large-cap, low vol": 0.12,
    "mid-cap": 0.20,
    "high-vol tech": 0.30,
    "CRWV-like": 0.40,
}

TARGET_T = 2.0  # ~5% significance, two-sided


def required_n(effect: float, dispersion: float, target_t: float = TARGET_T) -> int:
    """Events needed for the mean signed drift to clear `target_t`.

    t = mean / (sd / sqrt(n))  ->  n = (target_t * sd / mean)^2
    """
    return int(np.ceil((target_t * dispersion / effect) ** 2))


def effective_n(nominal: int, avg_cluster_size: float, intra_cluster_corr: float) -> float:
    """Shrink nominal sample size for correlation within earnings season.

    Earnings cluster into four windows a year, so events in the same week share
    macro and sector shocks and are not independent draws. The standard design
    effect is 1 + (m - 1) * rho.
    """
    design_effect = 1 + (avg_cluster_size - 1) * intra_cluster_corr
    return nominal / design_effect


def main() -> None:
    print("Events required for t >= 2.0 on mean signed 60-day drift\n")
    header = f"{'per-event sd':<22}" + "".join(f"{e:>12.0%}" for e in EFFECT_SIZES)
    print(header)
    print("-" * len(header))
    for label, sd in DISPERSIONS.items():
        row = f"{label + f' ({sd:.0%})':<22}"
        row += "".join(f"{required_n(e, sd):>12,}" for e in EFFECT_SIZES)
        print(row)

    print("\nTranslating to calendar time (4 events per name per year):\n")
    for sd in (0.20, 0.30):
        for effect in (0.02, 0.03):
            n = required_n(effect, sd)
            print(
                f"  sd {sd:.0%}, effect {effect:.0%}: {n:,} events"
                f" = {n / 4:,.0f} name-years"
                f" (e.g. {n // 20:,} names over 5 years)"
            )

    print("\nThe clustering penalty\n")
    print(
        "  Earnings land in four crowded windows a year, so same-week events\n"
        "  share macro shocks. Treating them as independent overstates your\n"
        "  effective sample - and therefore your t-stat."
    )
    nominal = 400
    for rho in (0.05, 0.15, 0.30):
        for cluster in (20, 50):
            eff = effective_n(nominal, cluster, rho)
            print(
                f"  {nominal} events, {cluster} per week, rho={rho:.2f}"
                f" -> effective n = {eff:,.0f}"
                f" ({eff / nominal:.0%} of nominal)"
            )

    print(
        "\n  A t-stat computed on 400 clustered events can be overstated by\n"
        "  2-3x. Cluster standard errors by event date, or the backtest will\n"
        "  look significant when it is not."
    )

    print("\nWhat CRWV alone could ever prove\n")
    for sd in (0.30, 0.40):
        detectable = TARGET_T * sd / np.sqrt(6)
        print(
            f"  sd {sd:.0%}, n=6: only an effect larger than {detectable:.0%}"
            " per event is detectable"
        )
    print(
        "\n  That is 5-15x the size of the real effect. A six-event sample on\n"
        "  one ticker cannot distinguish this strategy from a coin flip, which\n"
        "  is why the CRWV result is a hypothesis and not a finding."
    )


if __name__ == "__main__":
    main()
