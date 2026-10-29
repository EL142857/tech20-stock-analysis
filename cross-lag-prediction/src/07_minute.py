"""Minute level: predict each tech stock's next 1-minute % change, and compare models.

    r_i,t = P_i(t) / P_i(t-1) - 1,   t = one minute,   prices = last trade in the minute

Features use only bars that closed before minute t, and never cross the overnight
gap (each day starts fresh; the first 5 minutes of each day are only used as lags).

Walk-forward by day: train on the previous 5 trading days, predict every minute of the
next day, roll forward one day.

Models
  per-stock linear (OLS): own last 5 min / QQQ last 5 min / both
  all-stock VAR (the cross-stock idea): ridge on all 63 stocks + QQQ, last 3 min
  pooled models (one set of coefficients shared by all stocks, inputs scaled by each
  stock's volatility): ridge, gradient-boosted trees, a small neural net

Trading cost: half-spread per stock from the Roll (1984) estimator,
half-spread = sqrt(-cov(r_t, r_t-1)), i.e. the bid-ask bounce visible in trade prices.
"""
import json
import time
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

from common import DATA, FIG, RES, corr, newey_west_t, ridge_cv, robust_t

warnings.filterwarnings("ignore", module="sklearn")
rng = np.random.default_rng(0)
universe = list(pd.read_csv(DATA / "daily_close.csv", index_col=0, nrows=1).columns)
TRAIN_DAYS, LAGS, VAR_LAGS, SKIP = 5, 5, 3, 6


def load(name):
    df = pd.read_csv(DATA / name, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York")
    return df[universe]


Cl, Vo = load("minute_close.csv"), load("minute_volume.csv")
grid = pd.date_range("09:30", "15:59", freq="1min").strftime("%H:%M")
days = sorted(set(Cl.index.date))
D, Mn = len(days), len(grid)
stocks = [c for c in universe if c != "QQQ"]
cols = stocks + ["QQQ"]


def cube(df):
    """(day, minute, stock) array on a full 390-minute grid."""
    out = np.full((D, Mn, len(cols)), np.nan)
    key = pd.MultiIndex.from_arrays([df.index.date, df.index.strftime("%H:%M")])
    df = df.set_axis(key)[cols]
    for k, d in enumerate(days):
        out[k] = df.loc[d].reindex(grid).to_numpy()
    return out


Praw, Vraw = cube(Cl), cube(Vo)
traded = ~np.isnan(Praw)
P = pd.DataFrame(Praw.reshape(D * Mn, -1)).groupby(np.repeat(np.arange(D), Mn)).ffill()
P = P.to_numpy().reshape(D, Mn, -1)
R = np.full_like(P, np.nan)
R[:, 1:] = P[:, 1:] / P[:, :-1] - 1           # within-day only
R = np.nan_to_num(R)                            # no trade yet at the open -> 0
V = np.nan_to_num(Vraw)
N = len(stocks)
iQ = N  # QQQ column

no_trade_share = 1 - traded[:, 1:, :N].mean((0, 1))
liquid = no_trade_share <= np.quantile(no_trade_share, 0.5)

# ---------- feature construction on the (day, minute) grid ----------
def lag(X, k):
    out = np.zeros_like(X)
    out[:, k:] = X[:, :-k]
    return out


def cum_ret(k):
    """Own % change over the k minutes before t (from the open if fewer)."""
    Pk = np.empty_like(P)
    for m in range(Mn):
        Pk[:, m] = P[:, max(m - k, 0)]
    out = np.zeros_like(P)
    out[:, 1:] = P[:, :-1] / Pk[:, :-1] - 1
    return np.nan_to_num(out)


R_l = [lag(R, k) for k in range(1, LAGS + 1)]
logv = np.log1p(V)
vroll = pd.DataFrame(logv.reshape(D * Mn, -1)).groupby(np.repeat(np.arange(D), Mn)) \
    .transform(lambda s: s.rolling(30, min_periods=5).mean()).to_numpy().reshape(D, Mn, -1)
vshock = lag(np.nan_to_num(logv - vroll), 1)
stale1 = lag((~traded).astype(float), 1)
cum15, cum30 = cum_ret(15), cum_ret(30)
grp = [x[:, :, :N].mean(2, keepdims=True) for x in R_l[:3]]
tod = np.broadcast_to((np.arange(Mn) / Mn)[None, :, None], R.shape)

rows = np.arange(SKIP, Mn)                     # minutes used as targets
Y = R[:, rows, :N]                             # (D, m, N)


def per_stock_feats(kind):
    if kind == "own":
        F = [R_l[k][:, rows, :N] for k in range(LAGS)]
    elif kind == "qqq":
        F = [np.repeat(R_l[k][:, rows, iQ:iQ + 1], N, 2) for k in range(LAGS)]
    else:
        F = per_stock_feats("own") + per_stock_feats("qqq")
    return F


def pooled_feats():
    """(D, m, N) feature arrays in three groups: own returns (scaled later by the stock's
    sigma), market returns (scaled by QQQ's sigma), and unscaled extras."""
    q = lambda X: np.repeat(X[:, rows, iQ:iQ + 1], N, 2)
    g = lambda X: np.repeat(X[:, rows], N, 2)
    own = [R_l[k][:, rows, :N] for k in range(LAGS)] + [cum15[:, rows, :N], cum30[:, rows, :N]]
    mkt = [q(R_l[k]) for k in range(LAGS)] + [g(x) for x in grp] + [q(cum15)]
    other = [vshock[:, rows, :N], stale1[:, rows, :N], tod[:, rows, :N]]
    return own, mkt, other


PS = {k: np.stack(per_stock_feats(k), -1) for k in ["own", "qqq", "both"]}   # (D, m, N, F)
pooled_own, pooled_mkt, pooled_other = pooled_feats()
var_X = np.concatenate([R_l[k][:, rows, :] for k in range(VAR_LAGS)], axis=2)  # (D, m, (N+1)*3)

# ---------- diagnostics ----------
Yf = Y.reshape(-1, N)
X1 = R_l[0][:, rows].reshape(-1, N + 1)
C1 = corr(Yf, X1[:, :N])
T1 = robust_t(Yf, X1[:, :N])
off = ~np.eye(N, dtype=bool)
perm = [(np.abs(robust_t(Yf, X1[rng.permutation(len(X1)), :N])[off]) > 1.96).mean() for _ in range(200)]
own_ac = np.diag(C1)
qqq_lead = corr(Yf, X1[:, iQ:iQ + 1])[:, 0]
cov1 = ((Yf - Yf.mean(0)) * (X1[:, :N] - X1[:, :N].mean(0))).mean(0)
half_spread = np.sqrt(np.clip(-cov1, 0, None))          # Roll estimator, as a fraction
half_spread = np.maximum(half_spread, 0.25e-4)            # floor 0.25 bp
# best case: the quote is one tick ($0.01) wide, so half a cent per share each way
half_tick = 0.005 / np.nanmedian(Praw[:, :, :N], axis=(0, 1))
diag = dict(
    n_stocks=N, n_days=D, start=str(days[0]), end=str(days[-1]),
    minutes_per_day_used=len(rows), test_days=D - TRAIN_DAYS,
    median_no_trade_share_pct=float(100 * np.median(no_trade_share)),
    max_no_trade_share_pct=float(100 * no_trade_share.max()),
    mean_own_autocorr_lag1=float(own_ac.mean()),
    mean_own_autocorr_lag1_liquid=float(own_ac[liquid].mean()),
    mean_own_autocorr_lag1_illiquid=float(own_ac[~liquid].mean()),
    qqq_lag1_mean_corr=float(qqq_lead.mean()),
    qqq_lag1_mean_corr_liquid=float(qqq_lead[liquid].mean()),
    qqq_lag1_mean_corr_illiquid=float(qqq_lead[~liquid].mean()),
    corr_no_trade_share_vs_qqq_lead=float(stats.spearmanr(no_trade_share, qqq_lead)[0]),
    cross_lag1_frac_sig=float((np.abs(T1[off]) > 1.96).mean()),
    cross_lag1_perm_95=float(np.quantile(perm, .95)),
    cross_lag1_mean_corr=float(C1[off].mean()),
    noise_se=float(1 / np.sqrt(len(Yf))),
    roll_half_spread_bp_median=float(1e4 * np.median(half_spread)),
    roll_half_spread_bp_liquid=float(1e4 * np.median(half_spread[liquid])),
    roll_half_spread_bp_illiquid=float(1e4 * np.median(half_spread[~liquid])),
    half_tick_bp_median=float(1e4 * np.median(half_tick)),
    minute_vol_bp_median=float(1e4 * np.median(Yf.std(0))),
)
print(json.dumps(diag, indent=2))

# ---------- walk-forward by day ----------
MODELS = ["own_lags_ols", "qqq_lags_ols", "own+qqq_ols", "var_ridge_all_stocks",
          "pooled_ridge", "pooled_gbm", "pooled_mlp"]
pred = {m: np.full(Y.shape, np.nan) for m in MODELS}
fit_sec = {m: 0.0 for m in MODELS}


def pooled_matrix(dsel, sig, sig_q):
    """Stack (day, minute, stock) features into rows; returns scaled by volatility."""
    F = np.stack([x[dsel] / sig for x in pooled_own] + [x[dsel] / sig_q for x in pooled_mkt]
                 + [x[dsel] for x in pooled_other], -1)
    return F.reshape(-1, F.shape[-1])


for d in range(TRAIN_DAYS, D):
    tr = slice(d - TRAIN_DAYS, d)
    Ytr = Y[tr].reshape(-1, N)

    for m, k in [("own_lags_ols", "own"), ("qqq_lags_ols", "qqq"), ("own+qqq_ols", "both")]:
        t0 = time.perf_counter()
        Xtr, Xte = PS[k][tr], PS[k][d]
        for i in range(N):
            A = np.column_stack([np.ones(Xtr.shape[0] * Xtr.shape[1]), Xtr[:, :, i].reshape(-1, Xtr.shape[-1])])
            b = np.linalg.lstsq(A, Ytr[:, i], rcond=None)[0]
            pred[m][d, :, i] = np.column_stack([np.ones(len(Xte)), Xte[:, i]]) @ b
        fit_sec[m] += time.perf_counter() - t0

    t0 = time.perf_counter()
    p, _ = ridge_cv(var_X[tr].reshape(-1, var_X.shape[-1]), Ytr, var_X[d], n_val=len(rows))
    pred["var_ridge_all_stocks"][d] = p
    fit_sec["var_ridge_all_stocks"] += time.perf_counter() - t0

    sig = Ytr.std(0)
    sig_q = R[tr][:, rows, iQ].std()
    Ftr = pooled_matrix(tr, sig, sig_q)
    Fte = pooled_matrix(slice(d, d + 1), sig, sig_q)
    ytr = np.clip((Y[tr] / sig).reshape(-1), -10, 10)
    sc = StandardScaler().fit(Ftr)
    Ftr_s, Fte_s = sc.transform(Ftr), sc.transform(Fte)
    for m, model in [
        ("pooled_ridge", Ridge(alpha=1.0)),
        ("pooled_gbm", HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=500,
            l2_regularization=1.0, early_stopping=True, validation_fraction=0.2,
            n_iter_no_change=20, random_state=0)),
        ("pooled_mlp", MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-3, batch_size=2048,
                                    learning_rate_init=1e-3, max_iter=40, early_stopping=True,
                                    n_iter_no_change=5, random_state=0)),
    ]:
        t0 = time.perf_counter()
        model.fit(Ftr_s, ytr)
        pred[m][d] = model.predict(Fte_s).reshape(len(rows), N) * sig
        fit_sec[m] += time.perf_counter() - t0
    print(f"day {days[d]} done", flush=True)

# ---------- evaluation ----------
test = slice(TRAIN_DAYS, D)
Yt = Y[test].reshape(-1, N)


def evaluate(Pm, cols_mask):
    y, p = Yt[:, cols_mask], Pm[:, cols_mask]
    nz = (p != 0) & (y != 0)
    out = dict(oos_r2_pct=100 * (1 - ((y - p) ** 2).sum() / (y**2).sum()),
               hit_rate_pct=100 * (np.sign(p[nz]) == np.sign(y[nz])).mean(),
               clark_west_t=newey_west_t((y**2 - (y - p) ** 2 + p**2).mean(1), lags=10),
               stocks_pos_r2=int((1 - ((y - p) ** 2).sum(0) / (y**2).sum(0) > 0).sum()))
    # minute-by-minute long-short, held one minute; positions reset each day
    k = max(3, cols_mask.sum() // 10)
    rank = p.argsort(1)
    W = np.zeros_like(p)
    r_ = np.arange(len(p))[:, None]
    W[r_, rank[:, -k:]] = 1 / k
    W[r_, rank[:, :k]] = -1 / k
    W3 = W.reshape(D - TRAIN_DAYS, len(rows), -1)
    dW = np.abs(np.diff(W3, axis=1, prepend=0)) + np.abs(np.diff(W3, axis=1, append=0)) * \
        (np.arange(len(rows)) == len(rows) - 1)[None, :, None]       # close out at day end
    dW = dW.reshape(len(p), -1)
    gross = (W * y).sum(1)
    cost = (dW * half_spread[cols_mask]).sum(1)
    cost_tick = (dW * half_tick[cols_mask]).sum(1)
    # latency check: the same positions, but filled one minute late
    late = (W3[:, :-1] * y.reshape(W3.shape)[:, 1:]).sum(2).reshape(-1)
    out.update(ls_gross_bp_per_min=1e4 * gross.mean(),
               ls_gross_t=newey_west_t(gross, lags=10),
               ls_turnover_per_min=dW.sum(1).mean(),
               ls_breakeven_cost_bp=1e4 * gross.sum() / dW.sum(),
               ls_avg_half_spread_traded_bp=1e4 * cost.sum() / dW.sum(),
               ls_net_bp_per_min=1e4 * (gross - cost).mean(),
               ls_avg_half_tick_traded_bp=1e4 * cost_tick.sum() / dW.sum(),
               ls_net_half_tick_bp_per_min=1e4 * (gross - cost_tick).mean(),
               ls_net_half_tick_t=newey_west_t(gross - cost_tick, lags=10),
               ls_gross_1min_late_bp_per_min=1e4 * late.mean(),
               ls_gross_1min_late_t=newey_west_t(late, lags=10))
    return out, dict(gross=gross, net_tick=gross - cost_tick, late=late)


table, curves = [], {}
for m in MODELS:
    Pm = pred[m][test].reshape(-1, N)
    a, curves[m] = evaluate(Pm, np.ones(N, bool))
    b, _ = evaluate(Pm, liquid)
    table.append(dict(model=m, **a, liquid_oos_r2_pct=b["oos_r2_pct"],
                      liquid_hit_rate_pct=b["hit_rate_pct"],
                      liquid_gross_bp_per_min=b["ls_gross_bp_per_min"],
                      liquid_gross_t=b["ls_gross_t"],
                      liquid_breakeven_cost_bp=b["ls_breakeven_cost_bp"],
                      liquid_net_bp_per_min=b["ls_net_bp_per_min"],
                      fit_seconds_total=fit_sec[m]))
tab = pd.DataFrame(table).set_index("model").round(3)
tab.to_csv(RES / "minute_models.csv")
diag["share_up_minutes_pct_of_nonzero"] = float(100 * (Yt[Yt != 0] > 0).mean())
diag["share_zero_minutes_pct"] = float(100 * (Yt == 0).mean())
(RES / "minute.json").write_text(json.dumps(diag, indent=2))
pd.set_option("display.width", 250)
print(tab.to_string())

# ---------- figure ----------
labels = {"own_lags_ols": "own last 5 min", "qqq_lags_ols": "QQQ last 5 min",
          "own+qqq_ols": "own + QQQ", "var_ridge_all_stocks": f"ridge VAR, all {N}+QQQ × 3 min",
          "pooled_ridge": "pooled ridge", "pooled_gbm": "pooled gradient boosting",
          "pooled_mlp": "pooled neural net"}
fig, ax = plt.subplots(2, 2, figsize=(14, 10.5))
a = ax[0, 0]
a.scatter(100 * no_trade_share, qqq_lead, s=18, label="corr(rᵢ,t , QQQ t−1)")
a.scatter(100 * no_trade_share, own_ac, s=18, label="corr(rᵢ,t , rᵢ,t−1)")
for i in np.argsort(-no_trade_share)[:5]:
    a.annotate(stocks[i], (100 * no_trade_share[i], qqq_lead[i]), fontsize=7)
a.axhline(0, c="k", lw=.5)
a.set_xscale("symlog", linthresh=1)
a.set_xlim(left=0)
a.set(title="A. One-minute lead-lag vs. how often the stock goes untraded",
      xlabel="% of minutes with no trade", ylabel="correlation")
a.legend(fontsize=9)

a = ax[0, 1]
x = np.arange(len(MODELS))
a.bar(x - .2, tab["oos_r2_pct"], .4, label=f"all {N} stocks")
a.bar(x + .2, tab["liquid_oos_r2_pct"], .4, label=f"{liquid.sum()} most-traded")
a.set_xticks(x, [labels[m] for m in MODELS], rotation=25, ha="right", fontsize=8)
a.axhline(0, c="k", lw=.6)
a.set(title="B. Out-of-sample R² for the next minute", ylabel="R² (%)")
a.legend(fontsize=9)

a = ax[1, 0]
a.bar(x - .27, tab["ls_breakeven_cost_bp"], .27, label="break-even cost per side")
a.bar(x, tab["ls_avg_half_spread_traded_bp"], .27, label="Roll half-spread of names traded")
a.bar(x + .27, tab["ls_avg_half_tick_traded_bp"], .27, label="best case: half a 1¢ tick")
a.set_xticks(x, [labels[m] for m in MODELS], rotation=25, ha="right", fontsize=8)
a.set(title="C. Long-short each minute: what it earns vs. what it pays (bp)", ylabel="bp per unit traded")
a.legend(fontsize=9)

a = ax[1, 1]
for m, c in [("pooled_ridge", "C3"), ("var_ridge_all_stocks", "C2")]:
    cv = curves[m]
    a.plot(1e4 * np.cumsum(cv["gross"]), c=c, lw=1.2, label=f"{labels[m]}: filled at the bar close")
    a.plot(1e4 * np.cumsum(cv["net_tick"]), c=c, lw=1, ls="-.", label="   … minus best-case cost (half a tick)")
    a.plot(1e4 * np.cumsum(cv["late"]), c=c, lw=1, ls=":", label="   … filled one minute late (gross)")
a.axhline(0, c="k", lw=.6)
a.set(title=f"D. Cumulative long-short, {D - TRAIN_DAYS} test days ({(D - TRAIN_DAYS) * len(rows):,} minutes)",
      xlabel="test minute", ylabel="cumulative bp")
a.legend(fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "07_minute.png", dpi=130)
