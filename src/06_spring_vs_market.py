"""Spring model: excess return vs QQQ stretches / compresses a leaky spring; displacement -> P(up next week)."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import pearsonr, mannwhitneyu

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, RES, FIG = ROOT / "data", ROOT / "results", ROOT / "figures"
for _d in (DATA, RES, FIG):
    _d.mkdir(exist_ok=True)
close = pd.read_csv(DATA / "tech20_qqq_weekly_10y.csv", index_col=0, parse_dates=True)
TICKERS = [c for c in close.columns if c != "QQQ"]

lr = np.log(close).diff()
rI = lr["QQQ"]
# 1) background: remove the market part with a trailing 52-week beta (past data only)
beta = lr[TICKERS].rolling(52, min_periods=26).cov(rI).div(rI.rolling(52, min_periods=26).var(), axis=0).shift(1)
e = lr[TICKERS] - beta.mul(rI, axis=0)            # excess log return
# 2) noise: scale by each stock's own trailing excess volatility
sig = e.rolling(26, min_periods=13).std().shift(1)
eps = (e / sig).clip(-5, 5)


def spring(h):
    """Leaky accumulation x_t = lam*x_{t-1} + eps_t, normalized to unit variance."""
    lam = 0.5 ** (1 / h)
    x = eps.ewm(alpha=1 - lam, adjust=False, ignore_na=True).mean() / (1 - lam)
    return x * np.sqrt(1 - lam ** 2)


def fit_logit(z, y, iters=30):
    X = np.column_stack([np.ones_like(z), z])
    w = np.zeros(2)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ w))
        g = X.T @ (y - p)
        H = X.T @ (X * (p * (1 - p))[:, None])
        w += np.linalg.solve(H, g)
    return w


def predict(w, z):
    return 1 / (1 + np.exp(-(w[0] + w[1] * z)))


def frame(h):
    z = spring(h)
    d = pd.DataFrame({"z": z.stack(), "e_next": e.shift(-1).stack(),
                      "r_next": lr[TICKERS].shift(-1).stack()}).dropna()
    d["y"] = (d.e_next > 0).astype(float)
    d.index.names = ["date", "ticker"]
    return d


split = close.index[-1] - pd.Timedelta(weeks=104)   # last 2 years = out-of-sample test

# choose the half-life on the training years only
grid = []
for h in [1, 2, 4, 8, 13, 26, 52]:
    d = frame(h)
    tr = d[d.index.get_level_values("date") < split]
    te = d[d.index.get_level_values("date") >= split]
    w = fit_logit(tr.z.values, tr.y.values)
    p_tr, p_te = predict(w, tr.z.values), predict(w, te.z.values)
    ll = np.mean(tr.y * np.log(p_tr) + (1 - tr.y) * np.log(1 - p_tr))
    grid.append(dict(h=h, a=w[0], b=w[1], ll_train=ll,
                     r_train=pearsonr(p_tr, tr.y)[0], r_test=pearsonr(p_te, te.y)[0]))
grid = pd.DataFrame(grid)
print(grid.round(4).to_string(index=False))
H = 13                                            # one quarter: the "long process"; the sweep panel shows the rest

d = frame(H)
dates = d.index.get_level_values("date")
tr, te = d[dates < split].copy(), d[dates >= split].copy()
w = fit_logit(tr.z.values, tr.y.values)
d["p"] = predict(w, d.z.values)
tr["p"], te["p"] = predict(w, tr.z.values), predict(w, te.z.values)
d.to_csv(RES / "tech20_spring_weekly.csv", float_format="%.4f")

def auc(p, y):
    """Chance that a random up-week got a higher probability than a random down-week."""
    return mannwhitneyu(p[y > 0], p[y == 0]).statistic / ((y > 0).sum() * (y == 0).sum())


r_y, p_y = pearsonr(te.p, te.y)
r_e, p_e = pearsonr(te.p, te.e_next)
r_raw, _ = pearsonr(te.p, te.r_next > 0)
hit = ((te.p > 0.5) == (te.y > 0)).mean()
print(f"H={H}  w={w.round(4)}  test n={len(te)}  r(p,up)={r_y:.4f} (p={p_y:.3g})  "
      f"r(p,excess ret)={r_e:.4f} (p={p_e:.3g})  r(p,raw up)={r_raw:.4f}  hit={hit:.4f}  "
      f"up share={te.y.mean():.4f}  p range={te.p.min():.3f}-{te.p.max():.3f}")

per = pd.DataFrame({t: dict(r=pearsonr(g.p, g.y)[0], p_value=pearsonr(g.p, g.y)[1], n=len(g),
                            auc=auc(g.p.values, g.y.values))
                    for t, g in te.groupby(level="ticker")}).T.sort_values("r")
print(per.round(3).to_string())
per.round(4).to_csv(RES / "tech20_spring_per_stock.csv")

# ---------------------------------------------------------------- charts
plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]
INK, INK2, MUTED, SURF, GRID = "#0b0b0b", "#52514e", "#898781", "#fcfcfb", "#e1e0d9"
BLUE, RED, BLUE_L, RED_L = "#2a78d6", "#e34948", "#86b6ef", "#f0a5a0"
test_rng = f"{te.index.get_level_values('date').min():%Y-%m-%d} to {te.index.get_level_values('date').max():%Y-%m-%d}"
train_rng = f"{tr.index.get_level_values('date').min():%Y-%m-%d} to {tr.index.get_level_values('date').max():%Y-%m-%d}"
FOOT = (f"Data: Yahoo Finance weekly (adjusted). Market background = QQQ (Nasdaq-100) × trailing 52-week beta. "
        f"Spring parameters fitted on {train_rng} only; everything shown is out-of-sample ({test_rng}).")


def style(ax):
    ax.set_facecolor(SURF)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c3c2b7")
    ax.tick_params(colors=INK2, labelsize=8.5, length=0)
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def binned(x, y, edges):
    idx = np.digitize(x, edges[1:-1])
    out = []
    for i in range(len(edges) - 1):
        m = idx == i
        if m.sum() >= 15:
            f = y[m].mean()
            out.append((x[m].mean(), f, np.sqrt(f * (1 - f) / m.sum()), m.sum()))
    return np.array(out)


# Figure 1: spring displacement -> probability, and probability vs reality
fig = plt.figure(figsize=(19, 7.8), dpi=150, facecolor=SURF)
ax1 = fig.add_axes([0.045, 0.14, 0.28, 0.66])
ax2 = fig.add_axes([0.375, 0.14, 0.28, 0.66])
ax3 = fig.add_axes([0.705, 0.14, 0.28, 0.66])
for ax in (ax1, ax2, ax3):
    style(ax)

band = 1.96 / np.sqrt(len(te))
xs = np.arange(len(grid))
ax3.axhspan(-band, band, color="#f0efec", lw=0)
ax3.axhline(0, color="#c3c2b7", lw=1)
ax3.bar(xs, grid.r_test, width=0.55, color=[BLUE if v > 0 else RED for v in grid.r_test],
        label="Out-of-sample (test)")
ax3.scatter(xs, grid.r_train, s=46, facecolor=SURF, edgecolor=INK2, lw=1.5, zorder=3,
            label="In-sample (train)")
for x, v in zip(xs, grid.r_test):
    ax3.text(x, v + (0.004 if v >= 0 else -0.004), f"{v:+.3f}".replace("-", "−"), ha="center",
             va="bottom" if v >= 0 else "top", fontsize=8, color=INK2)
ax3.set_xticks(xs)
ax3.set_xticklabels([f"{h}" for h in grid.h])
ax3.set_ylim(-0.08, 0.08)
ax3.set_xlabel("Spring half-life (weeks): short = short memory, long = long memory", color=INK2)
ax3.set_ylabel("Correlation r (probability vs actual up/down)", color=INK2)
ax3.text(len(grid) - 0.6, band + 0.003, f"gray band = noise range ±{band:.3f}", ha="right", fontsize=8, color=MUTED)
ax3.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=INK2)
ax3.set_title("(c) What about other half-lives?", loc="left", fontsize=12, color=INK, pad=10)

b = binned(te.z.values, te.y.values, np.array([-9, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 9]))
zz = np.linspace(-3, 3, 200)
ax1.axhline(0.5, color="#c3c2b7", lw=1)
ax1.axvline(0, color="#c3c2b7", lw=1)
ax1.axvspan(0, 3, color=BLUE, alpha=0.04, lw=0)
ax1.axvspan(-3, 0, color=RED, alpha=0.04, lw=0)
ax1.plot(zz, predict(w, zz), color=INK, lw=2, label="Model: P(up) = σ(a + b·z)")
ax1.errorbar(b[:, 0], b[:, 1], yerr=1.96 * b[:, 2], fmt="o", ms=8, color=BLUE, ecolor=BLUE_L,
             elinewidth=2, capsize=0, mec=SURF, mew=2, label="Actual: share beating the market next week (±95%)")
ax1.set_xlim(-3, 3)
ax1.set_ylim(0.3, 0.7)
ax1.set_xlabel("Spring displacement z (standardized)   ← compressed (lagged the market)  |  stretched (beat the market) →", color=INK2)
ax1.set_ylabel("Probability of beating the market next week", color=INK2)
ax1.legend(loc="upper right", frameon=False, fontsize=8.5, labelcolor=INK2)
ax1.set_title("(a) Energy → probability: bigger displacement, stronger pull back?", loc="left", fontsize=12, color=INK, pad=10)

c = binned(te.p.values, te.y.values, np.quantile(te.p.values, np.linspace(0, 1, 11)))
lo, hi = c[:, 0].min() - 0.01, c[:, 0].max() + 0.01
ax2.axhline(te.y.mean(), color="#c3c2b7", lw=1, ls="--")
ax2.text(hi, te.y.mean() + 0.006, f"overall actual up share {te.y.mean():.1%}", ha="right", fontsize=8, color=MUTED)
ax2.errorbar(c[:, 0], c[:, 1], yerr=1.96 * c[:, 2], fmt="o", ms=8, color=BLUE, ecolor=BLUE_L,
             elinewidth=2, capsize=0, mec=SURF, mew=2)
ax2.set_xlim(lo, hi)
ax2.set_ylim(0.3, 0.7)
ax2.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=1))
ax2.set_xlabel(f"Model probability of up (deciles; the x-axis spans only {te.p.min():.1%}–{te.p.max():.1%})", color=INK2)
ax2.set_ylabel("Actual up share", color=INK2)
ax2.set_title("(b) Predicted probability vs actual up/down", loc="left", fontsize=12, color=INK, pad=10)
stats = (f"r(probability, actual up/down) = {r_y:+.3f}   (p = {p_y:.2g})\n"
         f"r(probability, actual excess return) = {r_e:+.3f}   (p = {p_e:.2g})\n"
         f"Ranking accuracy AUC = {auc(te.p.values, te.y.values):.3f}   (coin flip = 0.500)\n"
         f"Sample = {len(te)} stock-weeks")
ax2.text(0.03, 0.97, stats, transform=ax2.transAxes, va="top", fontsize=9, color=INK2,
         linespacing=1.6, bbox=dict(boxstyle="round,pad=0.5", fc=SURF, ec=GRID))
fig.text(0.04, 0.94, "Spring Model: Does Spring Energy Predict Next Week's Move?", fontsize=17, color=INK, weight="bold")
fig.text(0.04, 0.905, f"Beating QQQ stretches the spring, lagging compresses it; old displacement relaxes with a {H}-week half-life; "
         f"fitted b = {w[1]:+.3f} (negative = pull back, positive = momentum)", fontsize=10, color=INK2)
fig.text(0.04, 0.025, FOOT, fontsize=7.5, color=MUTED)
fig.savefig(FIG / "tech20_spring_probability_vs_actual.png", facecolor=SURF)
plt.close(fig)

# Figure 2: per-stock correlation
fig = plt.figure(figsize=(11, 8.5), dpi=150, facecolor=SURF)
ax = fig.add_axes([0.1, 0.1, 0.84, 0.74])
style(ax)
ax.grid(axis="y", visible=False)
n_med = per.n.median()
band = 1.96 / np.sqrt(n_med)
ax.axvspan(-band, band, color="#f0efec", lw=0)
ax.axvline(0, color="#c3c2b7", lw=1)
yy = np.arange(len(per))
ax.barh(yy, per.r, height=0.62, color=[BLUE if v > 0 else RED for v in per.r])
for i, (t, row) in enumerate(per.iterrows()):
    ax.text(row.r + (0.006 if row.r >= 0 else -0.006), i, f"{row.r:+.2f}".replace("-", "−"),
            va="center", ha="left" if row.r >= 0 else "right", fontsize=8.5, color=INK2)
ax.set_yticks(yy)
ax.set_yticklabels(per.index, fontsize=9, color=INK2)
ax.set_xlabel("Correlation r (model probability vs actual next-week up/down)", color=INK2)
ax.text(0, len(per) - 0.2, f"gray band = noise range (±{band:.2f})", ha="center", fontsize=8, color=MUTED)
fig.text(0.04, 0.94, "Spring Model by Stock (Out-of-Sample)", fontsize=17, color=INK, weight="bold")
fig.text(0.04, 0.905, f"{test_rng}; about {int(n_med)} weeks per stock; blue = higher probability went with more up weeks "
         "(model works), red = backwards", fontsize=10, color=INK2)
fig.text(0.04, 0.025, FOOT, fontsize=7.5, color=MUTED)
fig.savefig(FIG / "tech20_spring_per_stock.png", facecolor=SURF)
plt.close(fig)

# Figure 3: one stock through time
T = "NVDA"
g = te.xs(T, level="ticker")
fig = plt.figure(figsize=(15, 8), dpi=150, facecolor=SURF)
a1 = fig.add_axes([0.07, 0.52, 0.9, 0.33])
a2 = fig.add_axes([0.07, 0.12, 0.9, 0.33], sharex=a1)
for ax in (a1, a2):
    style(ax)
a1.fill_between(g.index, g.z, 0, where=g.z >= 0, color=BLUE_L, lw=0, interpolate=True, label="Stretched (cumulative outperformance)")
a1.fill_between(g.index, g.z, 0, where=g.z < 0, color=RED_L, lw=0, interpolate=True, label="Compressed (cumulative underperformance)")
a1.plot(g.index, g.z, color=INK2, lw=1.2)
a1.axhline(0, color="#c3c2b7", lw=1)
a1.set_ylabel("Spring displacement z", color=INK2)
a1.legend(loc="upper left", frameon=False, fontsize=8.5, ncol=2, labelcolor=INK2)
a1.set_title(f"{T}: spring displacement (energy U = ½·z²)", loc="left", fontsize=12, color=INK, pad=8)
a2.axhline(0, color="#c3c2b7", lw=1)
ex = g.e_next * 100
a2.bar(g.index, ex, width=5, color=[BLUE if v > 0 else RED for v in ex])
a2.set_ylabel("Next-week excess return (%)", color=INK2)
a2.set_title("Actual next week vs the market: blue = beat, red = lagged", loc="left", fontsize=12, color=INK, pad=8)
r1 = pearsonr(g.p, g.y)[0]
fig.text(0.04, 0.94, f"Spring Model Example: {T}", fontsize=17, color=INK, weight="bold")
fig.text(0.04, 0.905, f"{test_rng} (out-of-sample); r(probability, actual up/down) = {r1:+.3f}: after compression (red) it beat "
         "the market more often, after stretching it lagged (pull back); the model probability only moves within "
         f"{g.p.min():.1%}–{g.p.max():.1%}, so it is not drawn", fontsize=10, color=INK2)
fig.text(0.04, 0.02, FOOT, fontsize=7.5, color=MUTED)
fig.savefig(FIG / f"tech20_spring_example_{T}.png", facecolor=SURF)
plt.close(fig)
