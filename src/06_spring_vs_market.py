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
plt.rcParams["font.family"] = ["Microsoft YaHei", "Segoe UI", "sans-serif"]
INK, INK2, MUTED, SURF, GRID = "#0b0b0b", "#52514e", "#898781", "#fcfcfb", "#e1e0d9"
BLUE, RED, BLUE_L, RED_L = "#2a78d6", "#e34948", "#86b6ef", "#f0a5a0"
test_rng = f"{te.index.get_level_values('date').min():%Y-%m-%d} 至 {te.index.get_level_values('date').max():%Y-%m-%d}"
train_rng = f"{tr.index.get_level_values('date').min():%Y-%m-%d} 至 {tr.index.get_level_values('date').max():%Y-%m-%d}"
FOOT = (f"数据：Yahoo Finance 周线（复权）。背景板 = QQQ（纳斯达克 100）× 过去 52 周 β。"
        f"弹簧参数只用训练期 {train_rng} 拟合，图中全部是样本外检验期 {test_rng} 的结果。")


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
        label="样本外（检验期）")
ax3.scatter(xs, grid.r_train, s=46, facecolor=SURF, edgecolor=INK2, lw=1.5, zorder=3,
            label="样本内（训练期）")
for x, v in zip(xs, grid.r_test):
    ax3.text(x, v + (0.004 if v >= 0 else -0.004), f"{v:+.3f}".replace("-", "−"), ha="center",
             va="bottom" if v >= 0 else "top", fontsize=8, color=INK2)
ax3.set_xticks(xs)
ax3.set_xticklabels([f"{h}" for h in grid.h])
ax3.set_ylim(-0.08, 0.08)
ax3.set_xlabel("弹簧松弛半衰期（周）　短 = 只记得最近，长 = 记得很久", color=INK2)
ax3.set_ylabel("相关系数 r（概率 vs 实际涨/跌）", color=INK2)
ax3.text(len(grid) - 0.6, band + 0.003, f"灰带 = 噪音范围 ±{band:.3f}", ha="right", fontsize=8, color=MUTED)
ax3.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=INK2)
ax3.set_title("③ 换成别的半衰期呢？", loc="left", fontsize=12, color=INK, pad=10)

b = binned(te.z.values, te.y.values, np.array([-9, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 9]))
zz = np.linspace(-3, 3, 200)
ax1.axhline(0.5, color="#c3c2b7", lw=1)
ax1.axvline(0, color="#c3c2b7", lw=1)
ax1.axvspan(0, 3, color=BLUE, alpha=0.04, lw=0)
ax1.axvspan(-3, 0, color=RED, alpha=0.04, lw=0)
ax1.plot(zz, predict(w, zz), color=INK, lw=2, label="模型：P(上涨) = σ(a + b·z)")
ax1.errorbar(b[:, 0], b[:, 1], yerr=1.96 * b[:, 2], fmt="o", ms=8, color=BLUE, ecolor=BLUE_L,
             elinewidth=2, capsize=0, mec=SURF, mew=2, label="实际：该区间下周跑赢大盘的比例（±95%）")
ax1.set_xlim(-3, 3)
ax1.set_ylim(0.3, 0.7)
ax1.set_xlabel("弹簧位移 z（标准化）　← 压缩（近期跑输大盘）　｜　拉伸（近期跑赢大盘）→", color=INK2)
ax1.set_ylabel("下周跑赢大盘的概率", color=INK2)
ax1.legend(loc="upper right", frameon=False, fontsize=8.5, labelcolor=INK2)
ax1.set_title("① 势能 → 概率：位移越大，回弹力越强？", loc="left", fontsize=12, color=INK, pad=10)

c = binned(te.p.values, te.y.values, np.quantile(te.p.values, np.linspace(0, 1, 11)))
lo, hi = c[:, 0].min() - 0.01, c[:, 0].max() + 0.01
ax2.axhline(te.y.mean(), color="#c3c2b7", lw=1, ls="--")
ax2.text(hi, te.y.mean() + 0.006, f"整体实际上涨比例 {te.y.mean():.1%}", ha="right", fontsize=8, color=MUTED)
ax2.errorbar(c[:, 0], c[:, 1], yerr=1.96 * c[:, 2], fmt="o", ms=8, color=BLUE, ecolor=BLUE_L,
             elinewidth=2, capsize=0, mec=SURF, mew=2)
ax2.set_xlim(lo, hi)
ax2.set_ylim(0.3, 0.7)
ax2.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=1))
ax2.set_xlabel(f"模型给出的上涨概率（十分位分组；注意横轴只跨 {te.p.min():.1%}–{te.p.max():.1%}）", color=INK2)
ax2.set_ylabel("实际上涨比例", color=INK2)
ax2.set_title("② 预测概率 vs 实际涨跌", loc="left", fontsize=12, color=INK, pad=10)
stats = (f"相关系数 r(概率, 实际涨/跌) = {r_y:+.3f}　(p = {p_y:.2g})\n"
         f"相关系数 r(概率, 实际超额收益) = {r_e:+.3f}　(p = {p_e:.2g})\n"
         f"排序准确率 AUC = {auc(te.p.values, te.y.values):.3f}　（瞎猜 = 0.500）\n"
         f"样本 = {len(te)} 个“股票·周”")
ax2.text(0.03, 0.97, stats, transform=ax2.transAxes, va="top", fontsize=9, color=INK2,
         linespacing=1.6, bbox=dict(boxstyle="round,pad=0.5", fc=SURF, ec=GRID))
fig.text(0.04, 0.94, "弹簧模型：弹簧势能能预测下周涨跌吗？", fontsize=17, color=INK, weight="bold")
fig.text(0.04, 0.905, f"跑赢大盘 = 拉伸，跑输 = 压缩；每周的超额收益推动弹簧，旧位移按半衰期 {H} 周慢慢松弛；"
         f"拟合出的 b = {w[1]:+.3f}（负 = 回弹，正 = 惯性）", fontsize=10, color=INK2)
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
ax.set_xlabel("相关系数 r（模型概率 vs 实际下周涨/跌）", color=INK2)
ax.text(0, len(per) - 0.2, f"灰带 = 噪音范围（±{band:.2f}）", ha="center", fontsize=8, color=MUTED)
fig.text(0.04, 0.94, "弹簧模型分股票表现（样本外）", fontsize=17, color=INK, weight="bold")
fig.text(0.04, 0.905, f"{test_rng}；每只约 {int(n_med)} 周；蓝 = 概率越高越常涨（模型有效），"
         "红 = 方向反了", fontsize=10, color=INK2)
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
a1.fill_between(g.index, g.z, 0, where=g.z >= 0, color=BLUE_L, lw=0, interpolate=True, label="拉伸（跑赢大盘累积）")
a1.fill_between(g.index, g.z, 0, where=g.z < 0, color=RED_L, lw=0, interpolate=True, label="压缩（跑输大盘累积）")
a1.plot(g.index, g.z, color=INK2, lw=1.2)
a1.axhline(0, color="#c3c2b7", lw=1)
a1.set_ylabel("弹簧位移 z", color=INK2)
a1.legend(loc="upper left", frameon=False, fontsize=8.5, ncol=2, labelcolor=INK2)
a1.set_title(f"{T}：弹簧位移（势能 U = ½·z²）", loc="left", fontsize=12, color=INK, pad=8)
a2.axhline(0, color="#c3c2b7", lw=1)
ex = g.e_next * 100
a2.bar(g.index, ex, width=5, color=[BLUE if v > 0 else RED for v in ex])
a2.set_ylabel("下周超额收益（%）", color=INK2)
a2.set_title("下周实际表现（相对大盘）：蓝 = 跑赢，红 = 跑输", loc="left", fontsize=12, color=INK, pad=8)
r1 = pearsonr(g.p, g.y)[0]
fig.text(0.04, 0.94, f"弹簧模型示例：{T}", fontsize=17, color=INK, weight="bold")
fig.text(0.04, 0.905, f"{test_rng}（样本外）；该股 r(概率, 实际涨/跌) = {r1:+.3f}："
         "压缩（红区）之后更常跑赢，拉伸之后更常跑输，即回弹；模型概率只在 "
         f"{g.p.min():.1%}–{g.p.max():.1%} 之间变动，故不单独画出", fontsize=10, color=INK2)
fig.text(0.04, 0.02, FOOT, fontsize=7.5, color=MUTED)
fig.savefig(FIG / f"tech20_spring_example_{T}.png", facecolor=SURF)
plt.close(fig)
