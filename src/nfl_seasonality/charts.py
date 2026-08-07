"""Charts: monthly-return heatmap, equity curves, in/off-season bars.

Colors come from a validated palette (see README). Categorical slots 1-3 clear
the all-pairs CVD and normal-vision floors in light mode; the aqua slot sits
below 3:1 against the surface, so every series also carries a direct end label
rather than relying on the legend swatch alone.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

# Categorical slots 1-3.
SERIES = {"seasonal": "#2a78d6", "buy_hold": "#eb6834", "spy": "#1baf7a"}
SERIES_LABEL = {
    "seasonal": "Season-only basket",
    "buy_hold": "Basket buy & hold",
    "spy": "SPY",
}

# Diverging: blue (positive) <-> red (negative), neutral gray midpoint.
DIVERGING = LinearSegmentedColormap.from_list(
    "excess",
    ["#a01f1f", "#e34948", "#f0efec", "#2a78d6", "#0d366b"],
)


def _style_axes(ax: plt.Axes, ylabel: str = "", xlabel: str = "") -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
        ax.spines[side].set_linewidth(1.0)
    ax.tick_params(colors=INK_MUTED, labelsize=9, length=0)
    ax.grid(True, color=GRIDLINE, linewidth=1.0, alpha=1.0)
    ax.set_axisbelow(True)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK_SECONDARY, fontsize=10)
    if xlabel:
        ax.set_xlabel(xlabel, color=INK_SECONDARY, fontsize=10)


def _title(ax: plt.Axes, title: str, subtitle: str = "") -> None:
    ax.set_title(title, color=INK_PRIMARY, fontsize=13, fontweight="bold", loc="left", pad=18 if subtitle else 10)
    if subtitle:
        ax.text(
            0.0, 1.02, subtitle, transform=ax.transAxes,
            color=INK_SECONDARY, fontsize=9.5, va="bottom", ha="left",
        )


def monthly_heatmap(
    matrix: pd.DataFrame,
    path: Path,
    title: str = "Mean monthly excess return vs SPY",
    subtitle: str = "",
) -> Path:
    """Ticker x month heatmap, diverging around zero, every cell labelled."""
    data = matrix.to_numpy(dtype=float) * 100
    finite = data[np.isfinite(data)]
    limit = float(np.nanmax(np.abs(finite))) if finite.size else 1.0
    limit = max(limit, 1e-6)
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)

    height = max(3.2, 0.46 * len(matrix.index) + 2.2)
    fig, ax = plt.subplots(figsize=(11, height), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    mesh = ax.imshow(data, cmap=DIVERGING, norm=norm, aspect="auto")

    ax.set_xticks(range(len(matrix.columns)), matrix.columns)
    ax.set_yticks(range(len(matrix.index)), matrix.index)
    ax.tick_params(colors=INK_MUTED, labelsize=9.5, length=0)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)

    # 2px surface gap between cells.
    ax.set_xticks(np.arange(-0.5, len(matrix.columns), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(matrix.index), 1), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2)
    ax.grid(which="major", visible=False)
    ax.tick_params(which="minor", length=0)

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data[i, j]
            if not np.isfinite(value):
                ax.text(j, i, "-", ha="center", va="center", color=INK_MUTED, fontsize=8)
                continue
            shade = abs(value) / limit
            ax.text(
                j, i, f"{value:+.1f}",
                ha="center", va="center", fontsize=7.8,
                color="#ffffff" if shade > 0.62 else INK_PRIMARY,
            )

    bar = fig.colorbar(mesh, ax=ax, fraction=0.02, pad=0.015)
    bar.set_label("mean excess return, % per month", color=INK_SECONDARY, fontsize=9)
    bar.ax.tick_params(colors=INK_MUTED, labelsize=8, length=0)
    bar.outline.set_visible(False)

    _title(ax, title, subtitle)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return path


def equity_curves(
    curves: pd.DataFrame,
    path: Path,
    title: str = "Growth of $10,000",
    subtitle: str = "",
) -> Path:
    """Equity curves with direct end labels plus a legend."""
    fig, ax = plt.subplots(figsize=(11, 5.6), facecolor=SURFACE)
    _style_axes(ax, ylabel="portfolio value ($)")
    ax.grid(axis="x", visible=False)

    for name in ("buy_hold", "spy", "seasonal"):
        if name not in curves.columns:
            continue
        series = curves[name].dropna()
        if series.empty:
            continue
        ax.plot(
            series.index, series.to_numpy(),
            color=SERIES[name], linewidth=2.0,
            label=SERIES_LABEL[name], solid_capstyle="round",
        )
        ax.annotate(
            f"  {SERIES_LABEL[name]}  ${series.iloc[-1]:,.0f}",
            xy=(series.index[-1], series.iloc[-1]),
            xytext=(6, 0), textcoords="offset points",
            color=SERIES[name], fontsize=9, fontweight="bold", va="center",
        )

    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    ax.margins(x=0.02)
    ax.set_xlim(right=curves.index[-1] + pd.Timedelta(days=int(len(curves) * 0.16)))
    legend = ax.legend(frameon=False, loc="upper left", fontsize=9.5)
    for text in legend.get_texts():
        text.set_color(INK_SECONDARY)

    _title(ax, title, subtitle)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return path


def season_bars(
    comparison: pd.DataFrame,
    path: Path,
    title: str = "In-season vs off-season excess return",
    subtitle: str = "",
) -> Path:
    """Paired bars of in- and off-season mean daily excess return, bps/day."""
    frame = comparison.sort_values("in_bps_day")
    y = np.arange(len(frame))
    fig, ax = plt.subplots(figsize=(10, max(3.0, 0.52 * len(frame) + 2.0)), facecolor=SURFACE)
    _style_axes(ax, xlabel="mean excess return vs SPY, bps per day")
    ax.grid(axis="y", visible=False)

    # 2px surface gap between adjacent bars.
    ax.barh(y + 0.20, frame["in_bps_day"], height=0.36, color=SERIES["seasonal"], label="In season (Sep 1 - Feb 15)")
    ax.barh(y - 0.20, frame["off_bps_day"], height=0.36, color=SERIES["buy_hold"], label="Off season")
    ax.axvline(0, color=BASELINE, linewidth=1.2)

    labels = [
        f"{t}{'  *' if not m else ''}"
        for t, m in zip(frame["ticker"], frame.get("meaningful", pd.Series(True, index=frame.index)))
    ]
    ax.set_yticks(y, labels)
    legend = ax.legend(frameon=False, loc="lower right", fontsize=9.5)
    for text in legend.get_texts():
        text.set_color(INK_SECONDARY)

    _title(ax, title, subtitle or "*  fewer than 10 NFL seasons of history - not statistically meaningful")
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return path


def permutation_histogram(
    null: np.ndarray,
    observed: float,
    path: Path,
    title: str = "Permutation null: basket in-season minus off-season",
    subtitle: str = "",
) -> Path:
    """Null distribution from the rotation scheme with the observed value marked."""
    fig, ax = plt.subplots(figsize=(9, 4.6), facecolor=SURFACE)
    _style_axes(ax, xlabel="in-season minus off-season excess, bps/day", ylabel="permutations")
    ax.grid(axis="x", visible=False)
    ax.hist(null * 1e4, bins=60, color="#b7d3f6", edgecolor=SURFACE, linewidth=0.5)
    ax.axvline(observed * 1e4, color="#d03b3b", linewidth=2.0)
    ax.annotate(
        f" observed {observed * 1e4:+.2f} bps/day",
        xy=(observed * 1e4, ax.get_ylim()[1] * 0.92),
        color="#d03b3b", fontsize=9.5, fontweight="bold",
    )
    _title(ax, title, subtitle)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return path
