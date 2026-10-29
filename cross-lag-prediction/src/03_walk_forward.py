"""The proposed model, tested out of sample.

    r_i,t = a_i + sum_{k=1..L} sum_j  x_{i,j,k} * r_j,t-k + e_i,t

Every stock's return today is regressed on the last L daily % changes of all N tech stocks.
All N targets share the same features, so one solve fits the whole coefficient
matrix x (shape N*L x N).

Walk-forward: train on the previous 756 days (3 years), predict the next 21 days,
roll forward, repeat. Nothing after day t is used to predict day t.
Benchmark: "tomorrow's return is 0".
"""
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import FIG, RES, load_returns, long_short, newey_west_t, ols, pcr, per_stock_ols, ridge_cv

R, mkt = load_returns()
A, S = R.to_numpy(), mkt.to_numpy()
T, N = A.shape
WIN, STEP, LMAX = 756, 21, 5


def lagged(M, L):
    """Row t holds M[t-1], ..., M[t-L] side by side."""
    return np.hstack([np.roll(M, k, axis=0) for k in range(1, L + 1)])


X1, X5 = lagged(A, 1), lagged(A, 5)
Smat = np.repeat(lagged(S[:, None], 1), N, axis=1)
rng = np.random.default_rng(1)
NOISE = rng.standard_normal(X1.shape) * A.std()  # placebo features: pure noise

MODELS = ["hist_mean", "own_lag1", "mkt_lag1", "ols_all_L1", "ols_all_L5",
          "ridge_all_L1", "ridge_all_L5", "pcr5_all_L5", "placebo_noise_ols"]
pred = {m: np.full((T, N), np.nan) for m in MODELS}
in_r2 = {m: [] for m in ["ols_all_L1", "ols_all_L5", "placebo_noise_ols"]}
chosen_alpha = []

for t0 in range(LMAX + WIN, T, STEP):
    tr, te = slice(t0 - WIN, t0), slice(t0, min(t0 + STEP, T))
    Ytr = A[tr]
    pred["hist_mean"][te] = Ytr.mean(0)
    pred["own_lag1"][te] = per_stock_ols(X1[tr], Ytr, X1[te])
    pred["mkt_lag1"][te] = per_stock_ols(Smat[tr], Ytr, Smat[te])
    for m, X in [("ols_all_L1", X1), ("ols_all_L5", X5), ("placebo_noise_ols", NOISE)]:
        pred[m][te], fit = ols(X[tr], Ytr, X[te])
        in_r2[m].append(1 - ((Ytr - fit) ** 2).sum() / ((Ytr - Ytr.mean(0)) ** 2).sum())
    pred["ridge_all_L1"][te], _ = ridge_cv(X1[tr], Ytr, X1[te])
    pred["ridge_all_L5"][te], a = ridge_cv(X5[tr], Ytr, X5[te])
    chosen_alpha.append(a)
    pred["pcr5_all_L5"][te] = pcr(X5[tr], Ytr, X5[te])

oos = ~np.isnan(pred["hist_mean"][:, 0])
Y = A[oos]
dates = R.index[oos]
covid = np.asarray((dates >= "2020-02-15") & (dates <= "2020-06-30"))


def r2(y, p):
    return 1 - ((y - p) ** 2).sum() / (y**2).sum()


rows, curves = [], {}
for m in MODELS:
    P = pred[m][oos]
    cw = Y**2 - (Y - P) ** 2 + P**2  # Clark-West vs. the zero forecast
    nz = P != 0
    per_stock = 1 - ((Y - P) ** 2).sum(0) / (Y**2).sum(0)
    gross, net, sr_g, sr_n, to = long_short(P, Y, n=max(5, N // 10))
    curves[m] = net
    rows.append(dict(
        model=m,
        oos_r2_pct=100 * r2(Y, P),
        oos_r2_ex_covid_pct=100 * r2(Y[~covid], P[~covid]),
        stocks_with_pos_r2=int((per_stock > 0).sum()),
        hit_rate_pct=100 * (np.sign(P[nz]) == np.sign(Y[nz])).mean(),
        clark_west_t=newey_west_t(cw.mean(1)),
        ls_sharpe_gross=sr_g, ls_sharpe_net_5bp=sr_n, ls_daily_turnover=to,
        ls_sharpe_net_ex_covid=net[~covid].mean() / net[~covid].std() * np.sqrt(252),
        ls_sharpe_net_2018_21=net[dates < "2022"].mean() / net[dates < "2022"].std() * np.sqrt(252),
        ls_sharpe_net_2022_26=net[dates >= "2022"].mean() / net[dates >= "2022"].std() * np.sqrt(252),
        in_sample_r2_pct=100 * np.mean(in_r2[m]) if m in in_r2 else np.nan,
    ))
tab = pd.DataFrame(rows).set_index("model").round(3)
tab.to_csv(RES / "walk_forward.csv")
up_share = 100 * (Y > 0).mean()
meta = dict(oos_start=str(dates[0].date()), oos_end=str(dates[-1].date()), oos_days=len(Y),
            share_up_days_pct=up_share,
            ridge_L5_median_alpha_over_n=float(np.median(np.concatenate(chosen_alpha))),
            ridge_L5_share_max_alpha=float(np.mean(np.concatenate(chosen_alpha) == 1e4)))
(RES / "walk_forward_meta.json").write_text(json.dumps(meta, indent=2))
pd.set_option("display.width", 200)
print(tab.to_string())
print(json.dumps(meta, indent=2))

# ---------- figure ----------
labels = {"hist_mean": "historical mean", "own_lag1": "own yesterday",
          "mkt_lag1": "QQQ yesterday", "ols_all_L1": f"OLS, all {N} × 1 day",
          "ols_all_L5": f"OLS, all {N} × 5 days", "ridge_all_L1": f"ridge, all {N} × 1 day",
          "ridge_all_L5": f"ridge, all {N} × 5 days", "pcr5_all_L5": f"5 PCs of {N} × 5 days",
          "placebo_noise_ols": "placebo: OLS on random noise"}
fig, ax = plt.subplots(1, 3, figsize=(17, 5.5))
a = ax[0]
ins = tab["in_sample_r2_pct"].dropna()
a.bar(range(len(ins)), ins, color="C1", label="in-sample R² (fit window)")
a.bar(range(len(ins)), tab.loc[ins.index, "oos_r2_pct"], color="C0", label="out-of-sample R²")
a.set_xticks(range(len(ins)), [labels[m] for m in ins.index], rotation=15, fontsize=8)
a.axhline(0, c="k", lw=.6)
a.set(title="A. Fit vs. forecast: in-sample R² is mostly overfitting", ylabel="R² (%)")
a.legend(fontsize=8)

a = ax[1]
o = tab["oos_r2_pct"]
a.barh(range(len(o)), o.clip(lower=-3), color=["C3" if v < 0 else "C2" for v in o])
for i, v in enumerate(o):
    if v < -3:  # clipped bar: label inside it
        a.text(-2.95, i, f"{v:.1f}%", va="center", ha="left", fontsize=8, color="w")
    else:
        a.text(v + (0.05 if v >= 0 else -0.05), i, f"{v:.2f}%", va="center",
               ha="left" if v >= 0 else "right", fontsize=8)
a.set_yticks(range(len(o)), [labels[m] for m in o.index], fontsize=8)
a.axvline(0, c="k", lw=.6)
a.set(title="B. Out-of-sample R² vs. 'tomorrow = 0' (clipped at −3%)", xlabel="R² (%)")

a = ax[2]
for m in ["hist_mean", "own_lag1", "mkt_lag1", "ridge_all_L5", "pcr5_all_L5", "ols_all_L1"]:
    a.plot(dates, np.cumsum(curves[m]), label=labels[m], lw=1)
a.axhline(0, c="k", lw=.6)
a.set(title=f"C. Top-{max(5, N // 10)} / bottom-{max(5, N // 10)} long-short, after 5 bp costs", ylabel="cumulative return")
a.legend(fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "03_walk_forward.png", dpi=130)
