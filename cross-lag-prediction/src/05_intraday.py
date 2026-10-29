"""Same question within the day: does the morning predict the afternoon?

    morning_j   = P_j(12:30) / P_j(09:30 open) - 1
    afternoon_i = P_i(16:00 close) / P_i(12:30) - 1

    afternoon_i,t = a_i + sum_j x_ij * morning_j,t + e

A trader would see every morning move at 12:30 and could act on it immediately.
Also tested: the documented "intraday momentum" version, where the overnight gap
plus the first hour (to 10:30) predicts the last half hour (15:30 -> 16:00).

Hourly bars cover only ~2.9 years, so the walk-forward uses a 250-day window.
"""
import json

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from common import (DATA, FIG, RES, bh_count, corr, long_short, newey_west_t, ols,
                    per_stock_ols, ridge_cv, robust_t)

rng = np.random.default_rng(0)
universe = list(pd.read_csv(DATA / "daily_close.csv", index_col=0, nrows=1).columns)


def load(name):
    df = pd.read_csv(DATA / name, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York")
    return df[universe]


O, C = load("hourly_open.csv"), load("hourly_close.csv")
day, hhmm = C.index.date, C.index.strftime("%H:%M")
at = lambda df, t: df[hhmm == t].set_axis(day[hhmm == t])
open_ = at(O, "09:30")
p1030, p1230, p1530, close = at(C, "09:30"), at(C, "11:30"), at(C, "14:30"), at(C, "15:30")
prev_close = close.shift(1).reindex(open_.index)

morning = (p1230 / open_ - 1)
afternoon = (close / p1230 - 1)
first_hour = (p1030 / open_ - 1)
last_half = (close / p1530 - 1)
overnight = (open_ / prev_close - 1)

full = morning.index.intersection(afternoon.index)  # half days have no 15:30 bar
panel = {k: v.reindex(full) for k, v in dict(m=morning, a=afternoon, f=first_hour,
                                             l=last_half, o=overnight).items()}
ok = np.all([v.notna().all(axis=1) for v in panel.values()], axis=0)
panel = {k: v[ok] for k, v in panel.items()}
dates = pd.DatetimeIndex(panel["m"].index)
mkt = {k: v.pop("QQQ").to_numpy() for k, v in panel.items()}
names = list(panel["m"].columns)
M, Af, F, L, On = (panel[k].to_numpy() for k in "maflo")
T, N = M.shape
off = ~np.eye(N, dtype=bool)
tariff = np.asarray((dates >= "2025-04-01") & (dates <= "2025-04-30"))  # April 2025 tariff shock

# ---------- 1. correlation tests ----------
Cma = corr(Af, M)            # afternoon_i vs morning_j
Caa = corr(Af, Af)           # afternoon vs afternoon, same time (for scale)
Tma = robust_t(Af, M)
P = 2 * stats.norm.sf(np.abs(Tma))
perm = np.array([(np.abs(robust_t(Af, M[rng.permutation(T)])[off]) > 1.96).mean()
                 for _ in range(500)])


def mkt_out(X, x):
    """Remove the same-period QQQ beta from every stock."""
    xc = x - x.mean()
    return X - np.outer(x, (X - X.mean(0)).T @ xc / (xc @ xc))


Me, Ae = mkt_out(M, mkt["m"]), mkt_out(Af, mkt["a"])
Te = robust_t(Ae, Me)
perm_e = np.array([(np.abs(robust_t(Ae, Me[rng.permutation(T)])[off]) > 1.96).mean()
                   for _ in range(500)])
h = T // 2
stab_e = stats.pearsonr(corr(Ae[:h], Me[:h])[off], corr(Ae[h:], Me[h:])[off])[0]
stab = stats.pearsonr(corr(Af[:h], M[:h])[off], corr(Af[h:], M[h:])[off])[0]


def pooled_t(y, x):
    """NW t of the slope sign: mean of demeaned x*y across days."""
    return newey_west_t((y - y.mean()) * (x - x.mean()))


q_m_a = stats.pearsonr(mkt["m"], mkt["a"])
fo = mkt["f"] + mkt["o"]
q_fo_l = stats.pearsonr(fo, mkt["l"])
own_fo_l = robust_t(L, F + On)
corr_out = dict(
    n_stocks=N, n_days=T, start=str(dates[0].date()), end=str(dates[-1].date()),
    mean_corr_afternoon_same_time=float(Caa[off].mean()),
    mean_corr_afternoon_vs_morning=float(Cma[off].mean()),
    max_abs_corr_afternoon_vs_morning=float(np.abs(Cma[off]).max()),
    noise_se=float(1 / np.sqrt(T)),
    frac_sig_offdiag=float((np.abs(Tma[off]) > 1.96).mean()),
    perm_frac_95=float(np.quantile(perm, .95)), perm_p=float((perm >= (np.abs(Tma[off]) > 1.96).mean()).mean()),
    bh_fdr5=bh_count(P[off]),
    own_morning_frac_sig=float((np.abs(np.diag(Tma)) > 1.96).mean()),
    own_morning_mean_corr=float(np.diag(Cma).mean()),
    stability_halves=float(stab),
    idio_mean_corr=float(corr(Ae, Me)[off].mean()),
    idio_frac_sig=float((np.abs(Te[off]) > 1.96).mean()),
    idio_perm_frac_95=float(np.quantile(perm_e, .95)),
    idio_stability_halves=float(stab_e),
    qqq_morning_vs_afternoon_corr=float(q_m_a[0]),
    qqq_morning_vs_afternoon_nw_t=float(pooled_t(mkt["a"], mkt["m"])),
    qqq_morning_vs_afternoon_corr_ex_apr2025=float(stats.pearsonr(mkt["m"][~tariff], mkt["a"][~tariff])[0]),
    qqq_morning_to_each_afternoon_frac_sig=float((np.abs(robust_t(Af, mkt["m"][:, None])) > 1.96).mean()),
    qqq_morning_to_each_afternoon_mean_t=float(robust_t(Af, mkt["m"][:, None]).mean()),
    qqq_overnight_first_hour_vs_last_half_corr=float(q_fo_l[0]),
    qqq_overnight_first_hour_vs_last_half_nw_t=float(pooled_t(mkt["l"], fo)),
    own_overnight_first_hour_vs_last_half_mean_t=float(np.diag(own_fo_l).mean()),
    own_overnight_first_hour_vs_last_half_frac_sig=float((np.abs(np.diag(own_fo_l)) > 1.96).mean()),
)

# ---------- 2. walk-forward: predict each stock's afternoon at 12:30 ----------
WIN, STEP = 250, 21
NOISE = rng.standard_normal(M.shape) * M.std()
Qm = np.repeat(mkt["m"][:, None], N, axis=1)
MO = np.hstack([M, On])
MODELS = ["hist_mean", "own_morning", "qqq_morning", "ols_all_mornings",
          "ridge_all_mornings", "ridge_mornings_overnight", "placebo_noise_ols"]
pred = {m: np.full((T, N), np.nan) for m in MODELS}
in_r2 = {m: [] for m in ["ols_all_mornings", "placebo_noise_ols"]}
for t0 in range(WIN, T, STEP):
    tr, te = slice(t0 - WIN, t0), slice(t0, min(t0 + STEP, T))
    Ytr = Af[tr]
    pred["hist_mean"][te] = Ytr.mean(0)
    pred["own_morning"][te] = per_stock_ols(M[tr], Ytr, M[te])
    pred["qqq_morning"][te] = per_stock_ols(Qm[tr], Ytr, Qm[te])
    for m, X in [("ols_all_mornings", M), ("placebo_noise_ols", NOISE)]:
        pred[m][te], fit = ols(X[tr], Ytr, X[te])
        in_r2[m].append(1 - ((Ytr - fit) ** 2).sum() / ((Ytr - Ytr.mean(0)) ** 2).sum())
    pred["ridge_all_mornings"][te], _ = ridge_cv(M[tr], Ytr, M[te], n_val=60)
    pred["ridge_mornings_overnight"][te], _ = ridge_cv(MO[tr], Ytr, MO[te], n_val=60)

oos = ~np.isnan(pred["hist_mean"][:, 0])
Y, d_oos, tar = Af[oos], dates[oos], tariff[oos]
r2 = lambda y, p: 1 - ((y - p) ** 2).sum() / (y**2).sum()
n_ls = max(5, N // 10)
rows, curves = [], {}
for m in MODELS:
    Pm = pred[m][oos]
    nz = Pm != 0
    gross, net, sr_g, sr_n, to = long_short(Pm, Y, n=n_ls, intraday=True)
    _, net1, _, sr_n1, _ = long_short(Pm, Y, n=n_ls, cost_bp=1, intraday=True)
    curves[m] = gross
    rows.append(dict(
        model=m, oos_r2_pct=100 * r2(Y, Pm), oos_r2_ex_apr2025_pct=100 * r2(Y[~tar], Pm[~tar]),
        stocks_with_pos_r2=int((1 - ((Y - Pm) ** 2).sum(0) / (Y**2).sum(0) > 0).sum()),
        hit_rate_pct=100 * (np.sign(Pm[nz]) == np.sign(Y[nz])).mean(),
        clark_west_t=newey_west_t((Y**2 - (Y - Pm) ** 2 + Pm**2).mean(1)),
        ls_sharpe_gross=sr_g, ls_sharpe_net_1bp=sr_n1, ls_sharpe_net_5bp=sr_n,
        ls_gross_bp_per_day=1e4 * gross.mean(),
        in_sample_r2_pct=100 * np.mean(in_r2[m]) if m in in_r2 else np.nan))
tab = pd.DataFrame(rows).set_index("model").round(3)
tab.to_csv(RES / "intraday_walk_forward.csv")


# ---------- 3. QQQ timing rules with no fitted parameters ----------
def timing(signal, ret, cost_bp):
    """Hold QQQ long/short over the target window by the sign of the signal; enter+exit cost."""
    r = np.sign(signal) * ret - 2 * cost_bp / 1e4
    return r, r.mean() / r.std() * np.sqrt(252)


rules = {}
for name, sig, ret in [("morning_sign->afternoon", mkt["m"], mkt["a"]),
                       ("overnight+first_hour_sign->last_half_hour", fo, mkt["l"])]:
    r0, s0 = timing(sig, ret, 0)
    _, s1 = timing(sig, ret, 1)
    rules[name] = dict(sharpe_gross=float(s0), sharpe_net_1bp=float(s1),
                       gross_bp_per_day=float(1e4 * r0.mean()),
                       hit_rate_pct=float(100 * (np.sign(sig) == np.sign(ret)).mean()),
                       nw_t_gross=float(newey_west_t(r0)),
                       sharpe_gross_ex_apr2025=float(timing(sig[~tariff], ret[~tariff], 0)[1]))
    curves[name] = r0

out = dict(correlation=corr_out, walk_forward_oos_days=int(oos.sum()),
           walk_forward_oos_start=str(d_oos[0].date()),
           share_up_afternoons_pct=float(100 * (Y > 0).mean()), qqq_timing=rules)
(RES / "intraday.json").write_text(json.dumps(out, indent=2))
pd.set_option("display.width", 220)
print(json.dumps(out, indent=2))
print(tab.to_string())

# ---------- figure ----------
fig, ax = plt.subplots(2, 2, figsize=(14, 10.5))
a = ax[0, 0]
bins = np.linspace(-0.3, 0.9, 121)
a.hist(Caa[off], bins, alpha=.6, label="same afternoon  corr(aftᵢ , aftⱼ)")
a.hist(Cma[off], bins, alpha=.8, label="morning → afternoon  corr(aftᵢ , mornⱼ)")
a.axvspan(-1.96 / np.sqrt(T), 1.96 / np.sqrt(T), color="k", alpha=.12, label="±1.96/√T noise band")
a.set(title=f"A. All {off.sum():,} stock pairs, {T} days", xlabel="correlation", ylabel="pairs")
a.legend(fontsize=9)

a = ax[0, 1]
x, y = 100 * mkt["m"], 100 * mkt["a"]
a.scatter(x, y, s=6, alpha=.4)
a.scatter(x[tariff], y[tariff], s=10, c="C3", label="April 2025")
b = np.polyfit(x, y, 1)
xx = np.array([x.min(), x.max()])
a.plot(xx, np.polyval(b, xx), "k", lw=1)
a.axhline(0, c="k", lw=.4)
a.axvline(0, c="k", lw=.4)
a.set(title=f"B. QQQ: morning vs afternoon, corr {q_m_a[0]:.3f}",
      xlabel="morning 09:30→12:30 (%)", ylabel="afternoon 12:30→16:00 (%)")
a.legend(fontsize=9)

a = ax[1, 0]
labels = {"hist_mean": "historical mean", "own_morning": "own morning",
          "qqq_morning": "QQQ morning", "ols_all_mornings": f"OLS, all {N} mornings",
          "ridge_all_mornings": f"ridge, all {N} mornings",
          "ridge_mornings_overnight": "ridge, mornings + overnight gaps",
          "placebo_noise_ols": "placebo: OLS on random noise"}
o = tab["oos_r2_pct"]
a.barh(range(len(o)), o.clip(lower=-5), color=["C3" if v < 0 else "C2" for v in o])
for i, v in enumerate(o):
    if v < -5:
        a.text(-4.95, i, f"{v:.1f}%", va="center", ha="left", fontsize=8, color="w")
    else:
        a.text(v + (0.05 if v >= 0 else -0.05), i, f"{v:.2f}%", va="center",
               ha="left" if v >= 0 else "right", fontsize=8)
a.set_yticks(range(len(o)), [labels[m] for m in o.index], fontsize=8)
a.axvline(0, c="k", lw=.6)
a.set(title="C. Out-of-sample R² for each stock's afternoon (clipped at −5%)", xlabel="R² (%)")

a = ax[1, 1]
for m in ["own_morning", "qqq_morning", "ridge_all_mornings", "ols_all_mornings"]:
    a.plot(d_oos, 1e2 * np.cumsum(curves[m]), lw=1, label=f"L/S top/bottom {n_ls}: {labels[m]}")
for k, lab in [("morning_sign->afternoon", "QQQ: afternoon by sign of morning"),
               ("overnight+first_hour_sign->last_half_hour", "QQQ: last ½h by sign of gap + 1st hour")]:
    a.plot(dates, 1e2 * np.cumsum(curves[k]), lw=1.2, ls="--", label=lab)
a.axhline(0, c="k", lw=.6)
a.set(title="D. Cumulative return before costs", ylabel="cumulative %")
a.xaxis.set_major_formatter(mdates.ConciseDateFormatter(a.xaxis.get_major_locator()))
a.legend(fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "05_intraday.png", dpi=130)
