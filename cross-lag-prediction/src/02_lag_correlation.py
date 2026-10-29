"""Correlation tests: does stock j's return yesterday line up with stock i's return today?

C0[i, j] = corr(r_i,t , r_j,t)      same day (expected to be large)
C1[i, j] = corr(r_i,t , r_j,t-1)    yesterday's j vs today's i (what a predictor needs)

Each C1 entry gets a heteroskedasticity-robust t-stat. Because the 10,000 tests are
strongly dependent (stocks move together), the null for "how many are significant"
comes from a permutation test: shuffle the days of the lagged block, keeping each
day's cross-section intact, so co-movement survives but any lead-lag is destroyed.
"""
import json

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from scipy.cluster.hierarchy import leaves_list, linkage

from common import FIG, RES, bh_count, corr, load_returns, newey_west_t, robust_t

rng = np.random.default_rng(0)
R, mkt = load_returns()
names = list(R.columns)
N = len(names)
A = R.to_numpy()


off = ~np.eye(N, dtype=bool)
Y, X = A[1:], A[:-1]
C0 = corr(A, A)
C1 = corr(Y, X)
T1 = robust_t(Y, X)
P1 = 2 * stats.norm.sf(np.abs(T1))
frac_sig = (np.abs(T1[off]) > 1.96).mean()

# permutation null for the share of significant pairs and for the largest |t|
n_perm = 500
perm_frac, perm_max = np.empty(n_perm), np.empty(n_perm)
for b in range(n_perm):
    Tb = robust_t(Y, X[rng.permutation(len(X))])
    perm_frac[b] = (np.abs(Tb[off]) > 1.96).mean()
    perm_max[b] = np.abs(Tb[off]).max()

# lags 1..5
by_lag = {}
for k in range(1, 6):
    Tk = robust_t(A[k:], A[:-k])
    by_lag[k] = dict(frac_sig_offdiag=float((np.abs(Tk[off]) > 1.96).mean()),
                     mean_corr_offdiag=float(corr(A[k:], A[:-k])[off].mean()),
                     mean_own_corr=float(np.diag(corr(A[k:], A[:-k])).mean()))

# stability: is the lead-lag matrix from 2015-2020 the same as from 2021-2026?
h = len(A) // 2
C1a, C1b = corr(A[1:h], A[:h - 1]), corr(A[h + 1:], A[h:-1])
stab = stats.pearsonr(C1a[off], C1b[off])
# subtract the cross-sectional average, which is the "market moved yesterday" part
dm = lambda C: (C - C[off].mean())[off]
stab_rank = stats.spearmanr(dm(C1a), dm(C1b))

# "leaders": stocks whose yesterday move lines up with everyone's today move
lead_a, lead_b = C1a[:, :].sum(0) - np.diag(C1a), C1b.sum(0) - np.diag(C1b)
lead_stab = stats.spearmanr(lead_a, lead_b)

# market: QQQ yesterday -> each stock today; own lag
t_mkt = robust_t(Y, mkt.to_numpy()[:-1, None])[:, 0]
t_own = np.diag(T1)
pooled_mkt_t = newey_west_t((Y - Y.mean(0)).mean(1) * (mkt.to_numpy()[:-1] - mkt.mean()))


def summarize(M, n_perm=200):
    """Share significant, permutation null and half-vs-half stability for return matrix M."""
    Ym, Xm = M[1:], M[:-1]
    Tm = robust_t(Ym, Xm)
    f = (np.abs(Tm[off]) > 1.96).mean()
    pf = [(np.abs(robust_t(Ym, Xm[rng.permutation(len(Xm))])[off]) > 1.96).mean()
          for _ in range(n_perm)]
    hm = len(M) // 2
    ca, cb = corr(M[1:hm], M[:hm - 1]), corr(M[hm + 1:], M[hm:-1])
    return dict(mean_C1_offdiag=float(corr(Ym, Xm)[off].mean()), frac_sig_offdiag=float(f),
                perm_frac_95=float(np.quantile(pf, .95)), perm_p=float(np.mean(np.array(pf) >= f)),
                stability_pearson=float(stats.pearsonr(ca[off], cb[off])[0]),
                stability_demeaned_spearman=float(stats.spearmanr(dm(ca), dm(cb))[0]))


# robustness 1: drop the COVID crash and rebound (Feb 15 - Jun 30, 2020)
covid = (R.index >= "2020-02-15") & (R.index <= "2020-06-30")
A_nc = A.copy()
A_nc[covid] = np.nan
keep = ~np.isnan(A_nc[1:]).any(1) & ~np.isnan(A_nc[:-1]).any(1)
# stack valid (today, yesterday) pairs directly so no artificial jump is created
Yn, Xn = A[1:][keep], A[:-1][keep]
Tn = robust_t(Yn, Xn)
mn = mkt.to_numpy()[:-1][keep]
no_covid = dict(mean_C1_offdiag=float(corr(Yn, Xn)[off].mean()),
                frac_sig_offdiag=float((np.abs(Tn[off]) > 1.96).mean()),
                perm_frac_95=float(np.quantile(
                    [(np.abs(robust_t(Yn, Xn[rng.permutation(len(Xn))])[off]) > 1.96).mean()
                     for _ in range(200)], .95)),
                mkt_lag_pooled_nw_t=float(newey_west_t((Yn - Yn.mean(0)).mean(1) * (mn - mn.mean()))))

# robustness 2: idiosyncratic returns (same-day QQQ beta removed)
s_ = mkt.to_numpy()
beta = ((A - A.mean(0)).T @ (s_ - s_.mean())) / ((s_ - s_.mean()) @ (s_ - s_.mean()))
E = A - np.outer(s_, beta)
idio = summarize(E)
C1e = corr(E[1:], E[:-1])

out = dict(
    n_stocks=N, n_days=len(A), start=str(R.index[0].date()), end=str(R.index[-1].date()),
    mean_abs_C0_offdiag=float(np.abs(C0[off]).mean()),
    mean_C0_offdiag=float(C0[off].mean()),
    mean_abs_C1_offdiag=float(np.abs(C1[off]).mean()),
    mean_C1_offdiag=float(C1[off].mean()),
    max_abs_C1_offdiag=float(np.abs(C1[off]).max()),
    iid_se_of_corr=float(1 / np.sqrt(len(Y))),
    frac_sig_offdiag=float(frac_sig),
    perm_frac_mean=float(perm_frac.mean()), perm_frac_95=float(np.quantile(perm_frac, .95)),
    perm_p_frac=float((perm_frac >= frac_sig).mean()),
    max_abs_t=float(np.abs(T1[off]).max()), perm_max_t_95=float(np.quantile(perm_max, .95)),
    n_pairs_beat_perm_max95=int((np.abs(T1[off]) > np.quantile(perm_max, .95)).sum()),
    bh_fdr5_offdiag=bh_count(P1[off]),
    by_lag=by_lag,
    stability_pearson=float(stab[0]), stability_pearson_p=float(stab[1]),
    stability_demeaned_spearman=float(stab_rank[0]),
    leader_score_spearman=float(lead_stab[0]), leader_score_p=float(lead_stab[1]),
    own_lag_frac_sig=float((np.abs(t_own) > 1.96).mean()),
    own_lag_mean_corr=float(np.diag(C1).mean()),
    mkt_lag_frac_sig=float((np.abs(t_mkt) > 1.96).mean()),
    mkt_lag_mean_t=float(t_mkt.mean()), mkt_lag_pooled_nw_t=float(pooled_mkt_t),
    no_covid=no_covid, idiosyncratic=idio,
    idio_max_abs_C1=float(np.abs(C1e[off]).max()),
)
(RES / "lag_correlation.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))

# ---------- figures ----------
fig, ax = plt.subplots(2, 2, figsize=(13, 10.5))

a = ax[0, 0]
bins = np.linspace(-0.25, 0.85, 111)
a.hist(C0[off], bins, alpha=.6, label="same day  corr(rᵢ,t , rⱼ,t)")
a.hist(C1[off], bins, alpha=.8, label="next day  corr(rᵢ,t , rⱼ,t−1)")
a.axvspan(-1.96 / np.sqrt(len(Y)), 1.96 / np.sqrt(len(Y)), color="k", alpha=.12,
          label="±1.96/√T (pure-noise band)")
a.set(title=f"A. Same-day vs. next-day correlation, all {off.sum():,} stock pairs",
      xlabel="correlation", ylabel="number of pairs")
a.legend(fontsize=9)

a = ax[0, 1]
order = leaves_list(linkage(A.T, "average", metric="correlation"))
v = np.quantile(np.abs(C1), .99)
im = a.imshow(C1[np.ix_(order, order)], cmap="RdBu_r", vmin=-v, vmax=v)
a.set(title="B. Next-day matrix C1 (rows: today i, cols: yesterday j)\n"
            "ordered by same-day clusters", xticks=[], yticks=[])
plt.colorbar(im, ax=a, fraction=.046)

a = ax[1, 0]
a.hist(perm_frac * 100, 30, color="0.6", label="500 shuffled-day nulls")
a.axvline(frac_sig * 100, color="C3", lw=2, label=f"observed {frac_sig:.1%}")
a.axvline(5, color="k", ls=":", label="naive 5%")
a.set(title="C. Share of pairs with |t| > 1.96\n(null keeps co-movement, kills lead-lag)",
      xlabel=f"% of {off.sum():,} pairs significant", ylabel="count")
a.legend(fontsize=9)

a = ax[1, 1]
a.scatter(C1a[off], C1b[off], s=3, alpha=.3)
a.set(title=f"D. Stability: C1 in 1st half vs 2nd half\n"
            f"Pearson {stab[0]:.2f}; after removing the common level, Spearman {stab_rank[0]:.2f}",
      xlabel=f"{R.index[0].year}–{R.index[h].year}", ylabel=f"{R.index[h].year}–{R.index[-1].year}")
a.axhline(0, c="k", lw=.5)
a.axvline(0, c="k", lw=.5)

fig.tight_layout()
fig.savefig(FIG / "02_lag_correlation.png", dpi=130)
