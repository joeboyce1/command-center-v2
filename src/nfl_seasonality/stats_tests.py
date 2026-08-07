"""Hypothesis tests: Welch, Newey-West HAC, permutation, multiplicity control."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class MeanDiff:
    n_in: int
    n_out: int
    mean_in: float
    mean_out: float
    diff: float
    t_welch: float
    p_welch: float
    t_hac: float
    p_hac: float


def welch(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Welch's t-test (unequal variances) of mean(a) - mean(b)."""
    if len(a) < 2 or len(b) < 2:
        return np.nan, np.nan
    t, p = stats.ttest_ind(a, b, equal_var=False)
    return float(t), float(p)


def newey_west_dummy(values: np.ndarray, dummy: np.ndarray, lags: int | None = None) -> tuple[float, float]:
    """t-stat on ``b`` in ``values = a + b*dummy + e`` with Newey-West errors.

    Daily returns are heteroskedastic and mildly autocorrelated, and the
    in-season indicator arrives in long blocks; an IID t-test understates the
    standard error. Bartlett kernel, lag length ~ 4*(n/100)^(2/9) (Newey-West
    1994 rule of thumb) unless overridden.
    """
    y = np.asarray(values, dtype=float)
    d = np.asarray(dummy, dtype=float)
    ok = np.isfinite(y) & np.isfinite(d)
    y, d = y[ok], d[ok]
    n = len(y)
    if n < 30 or len(np.unique(d)) < 2:
        return np.nan, np.nan

    X = np.column_stack([np.ones(n), d])
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta

    if lags is None:
        lags = int(np.floor(4 * (n / 100.0) ** (2.0 / 9.0)))
    lags = max(0, min(lags, n - 2))

    u = X * resid[:, None]
    S = u.T @ u
    for lag in range(1, lags + 1):
        weight = 1.0 - lag / (lags + 1.0)
        gamma = u[lag:].T @ u[:-lag]
        S += weight * (gamma + gamma.T)

    cov = XtX_inv @ S @ XtX_inv
    se = float(np.sqrt(max(cov[1, 1], 0.0)))
    if se == 0 or not np.isfinite(se):
        return np.nan, np.nan
    t = float(beta[1] / se)
    p = float(2 * stats.norm.sf(abs(t)))
    return t, p


def mean_difference(values: np.ndarray, mask: np.ndarray) -> MeanDiff:
    """Difference in means between ``mask`` and ``~mask``, both t-stats."""
    values = np.asarray(values, dtype=float)
    mask = np.asarray(mask, dtype=bool)
    ok = np.isfinite(values)
    values, mask = values[ok], mask[ok]
    inside, outside = values[mask], values[~mask]
    mean_in = float(np.mean(inside)) if len(inside) else np.nan
    mean_out = float(np.mean(outside)) if len(outside) else np.nan
    t_w, p_w = welch(inside, outside)
    t_h, p_h = newey_west_dummy(values, mask.astype(float))
    return MeanDiff(
        n_in=len(inside),
        n_out=len(outside),
        mean_in=mean_in,
        mean_out=mean_out,
        diff=mean_in - mean_out,
        t_welch=t_w,
        p_welch=p_w,
        t_hac=t_h,
        p_hac=p_h,
    )


def permutation_pvalue(
    values: np.ndarray,
    mask: np.ndarray,
    n_permutations: int,
    seed: int,
    scheme: str = "rotate",
) -> tuple[float, float, np.ndarray]:
    """Empirical two-sided p-value for the in-season minus off-season mean.

    Schemes:

    ``rotate``  Circularly shift the season mask by a random offset. This is
        the right null for a calendar effect: it keeps the mask's block
        structure and the return series' autocorrelation intact, and only
        destroys the *alignment* between them. This is the primary test.

    ``shuffle`` Shuffle daily labels independently. This breaks the block
        structure, so the permutation distribution is far too narrow and the
        p-value is anticonservative. Reported only as a contrast.

    Returns ``(p_value, observed_diff, null_distribution)``.
    """
    values = np.asarray(values, dtype=float)
    mask = np.asarray(mask, dtype=bool)
    ok = np.isfinite(values)
    values, mask = values[ok], mask[ok]
    n = len(values)
    if n < 30 or mask.all() or not mask.any():
        return np.nan, np.nan, np.array([])

    def diff_for(m: np.ndarray) -> float:
        if m.all() or not m.any():
            return np.nan
        return float(values[m].mean() - values[~m].mean())

    observed = diff_for(mask)
    rng = np.random.default_rng(seed)

    if scheme == "rotate":
        offsets = rng.integers(1, n, size=n_permutations)
        null = np.array([diff_for(np.roll(mask, int(k))) for k in offsets])
    elif scheme == "shuffle":
        null = np.empty(n_permutations)
        for i in range(n_permutations):
            null[i] = diff_for(rng.permutation(mask))
    else:
        raise ValueError(f"unknown permutation scheme: {scheme}")

    null = null[np.isfinite(null)]
    if null.size == 0:
        return np.nan, observed, null
    # +1 correction: the observed labelling is itself one draw from the null.
    p = (np.sum(np.abs(null) >= abs(observed)) + 1) / (null.size + 1)
    return float(p), observed, null


def bonferroni(pvalues: np.ndarray) -> np.ndarray:
    p = np.asarray(pvalues, dtype=float)
    m = int(np.sum(np.isfinite(p)))
    return np.minimum(p * max(m, 1), 1.0)


def benjamini_hochberg(pvalues: np.ndarray) -> np.ndarray:
    """BH step-up adjusted p-values (q-values), NaNs preserved."""
    p = np.asarray(pvalues, dtype=float)
    out = np.full(p.shape, np.nan)
    finite = np.isfinite(p)
    vals = p[finite]
    m = vals.size
    if m == 0:
        return out
    order = np.argsort(vals)
    ranked = vals[order]
    adjusted = ranked * m / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.minimum(adjusted, 1.0)
    restored = np.empty(m)
    restored[order] = adjusted
    out[finite] = restored
    return out
