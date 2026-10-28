"""Spring driven by each stock's own weekly % change (market kept in); correlate displacement with next-week % change."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from scipy.stats import pearsonr

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, RES, FIG = ROOT / "data", ROOT / "results", ROOT / "figures"
for _d in (DATA, RES, FIG):
    _d.mkdir(exist_ok=True)
close = pd.read_csv(DATA / "tech20_qqq_weekly_10y.csv", index_col=0, parse_dates=True)
TICKERS = [c for c in close.columns if c != "QQQ"]

r = close[TICKERS].pct_change() * 100             # weekly % change, market NOT removed
sig = r.rolling(26, min_periods=13).std().shift(1)
eps = (r / sig).clip(-5, 5)                       # each week's push, in units of the stock's own volatility
nxt = r.shift(-1)                                 # next week's % change (the thing we compare against)
HS = [1, 2, 4, 8, 13, 26, 52]
H = 13


def spring(h):
    lam = 0.5 ** (1 / h)
    x = eps.ewm(alpha=1 - lam, adjust=False, ignore_na=True).mean() / (1 - lam)
    return x * np.sqrt(1 - lam ** 2)


def pairs(z, t=None, period=None):
    a, b = (z, nxt) if t is None else (z[t], nxt[t])
    d = pd.concat([a.stack() if t is None else a, b.stack() if t is None else b], axis=1).dropna()
    if period is not None:
        dts = d.index.get_level_values(0)
        d = d[(dts >= period[0]) & (dts < period[1])]
    return d.iloc[:, 0].values, d.iloc[:, 1].values


start = spring(H).dropna(how="all").index[0]
end = close.index[-1]
mid = start + (end - start) / 2
halves = [(start, mid), (mid, end + pd.Timedelta(days=1))]

# correlation table: stocks x half-life
tab, sig_tab = {}, {}
for h in HS:
    z = spring(h)
    col, pcol = {}, {}
    for t in TICKERS:
        a, b = pairs(z, t)
        col[t], pcol[t] = pearsonr(a, b)
    a, b = pairs(z)
    col["20 只合并"], pcol["20 只合并"] = pearsonr(a, b)
    tab[h], sig_tab[h] = col, pcol
tab, sig_tab = pd.DataFrame(tab), pd.DataFrame(sig_tab)
tab.round(4).to_csv(RES / "tech20_spring2_corr_table.csv")

sweep = []
for h in HS:
    z = spring(h)
    row = dict(h=h, all=pearsonr(*pairs(z))[0])
    for i, p in enumerate(halves):
        row[f"half{i}"] = pearsonr(*pairs(z, period=p))[0]
    sweep.append(row)
sweep = pd.DataFrame(sweep)

z = spring(H)
za, ra = pairs(z)
n_all = len(za)
r_all, p_all = pearsonr(za, ra)
ru, pu = pearsonr(0.5 * za ** 2, np.abs(ra))     # energy vs size of next move (side check)
print(f"start={start.date()} end={end.date()} n={n_all} r={r_all:.4f} p={p_all:.3g}  energy-vs-|move| r={ru:.4f}")
print(sweep.round(4).to_string(index=False))
print(tab.round(3).to_string())

# ---------------------------------------------------------------- charts
plt.rcParams["font.family"] = ["Microsoft YaHei", "Segoe UI", "sans-serif"]
INK, INK2, MUTED, SURF, GRID = "#0b0b0b", "#52514e", "#898781", "#fcfcfb", "#e1e0d9"
BLUE, RED, BLUE_L = "#2a78d6", "#e34948", "#86b6ef"
rng = f"{start:%Y-%m-%d} 至 {end:%Y-%m-%d}"
FOOT = ("数据：Yahoo Finance 周线（复权）；不扣除大盘。弹簧：每周涨跌幅 ÷ 该股过去 26 周波动率 推动位移，"
        "旧位移按半衰期指数松弛；z 为标准化位移，势能 U = ½·z²。相关系数无需拟合任何参数。")


def style(ax):
    ax.set_facecolor(SURF)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c3c2b7")
    ax.tick_params(colors=INK2, labelsize=8.5, length=0)
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


# Figure 1: displacement vs next-week % change + half-life sweep
fig = plt.figure(figsize=(17, 7.8), dpi=150, facecolor=SURF)
ax1 = fig.add_axes([0.05, 0.14, 0.42, 0.66])
ax2 = fig.add_axes([0.56, 0.14, 0.41, 0.66])
for ax in (ax1, ax2):
    style(ax)

edges = np.array([-9, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 9])
idx = np.digitize(za, edges[1:-1])
B = np.array([(za[idx == i].mean(), ra[idx == i].mean(), ra[idx == i].std() / np.sqrt((idx == i).sum()),
               (idx == i).sum()) for i in range(len(edges) - 1)])
ax1.axhline(0, color="#c3c2b7", lw=1)
ax1.axhline(ra.mean(), color=MUTED, lw=1, ls="--")
ax1.text(2.95, ra.mean() + 0.04, f"全样本平均周涨幅 {ra.mean():+.2f}%", ha="right", fontsize=8, color=MUTED)
ax1.axvline(0, color="#c3c2b7", lw=1)
ax1.axvspan(0, 3, color=BLUE, alpha=0.04, lw=0)
ax1.axvspan(-3, 0, color=RED, alpha=0.04, lw=0)
k, c0 = np.polyfit(za, ra, 1)
xx = np.linspace(-3, 3, 50)
ax1.plot(xx, c0 + k * xx, color=INK, lw=2, label=f"线性拟合：斜率 {k:+.3f} %/单位位移")
ax1.errorbar(B[:, 0], B[:, 1], yerr=1.96 * B[:, 2], fmt="o", ms=8, color=BLUE, ecolor=BLUE_L,
             elinewidth=2, capsize=0, mec=SURF, mew=2, label="实际：该位移区间下周平均涨跌幅（±95%）")
for x_, y_, e_, n_ in B:
    ax1.text(x_, y_ - 1.96 * e_ - 0.08, f"{int(n_)}", ha="center", va="top", fontsize=7, color=MUTED)
ax1.set_xlim(min(-3, B[:, 0].min() - 0.3), max(3, B[:, 0].max() + 0.3))
ax1.set_xlabel("弹簧位移 z　← 压缩（近期跌）　｜　拉伸（近期涨）→　（小字 = 样本数）", color=INK2)
ax1.set_ylabel("下周涨跌幅（%）", color=INK2)
ax1.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=INK2)
ax1.set_title(f"① 弹簧位移 vs 下周涨跌幅（半衰期 {H} 周）", loc="left", fontsize=12, color=INK, pad=10)
ax1.text(0.98, 0.04, f"相关系数 r = {r_all:+.3f}　(p = {p_all:.2g})\n样本 = {n_all} 个“股票·周”",
         transform=ax1.transAxes, ha="right", va="bottom", fontsize=9.5, color=INK2, linespacing=1.6,
         bbox=dict(boxstyle="round,pad=0.5", fc=SURF, ec=GRID))

band = 1.96 / np.sqrt(n_all)
xs = np.arange(len(sweep))
ax2.axhspan(-band, band, color="#f0efec", lw=0)
ax2.axhline(0, color="#c3c2b7", lw=1)
ax2.bar(xs, sweep["all"], width=0.5, color=[BLUE if v > 0 else RED for v in sweep["all"]], label="全部 10 年")
ax2.scatter(xs - 0.12, sweep.half0, s=40, marker="o", facecolor=SURF, edgecolor=INK2, lw=1.5, zorder=3,
            label=f"前 5 年（{halves[0][0]:%Y}–{halves[0][1]:%Y}）")
ax2.scatter(xs + 0.12, sweep.half1, s=40, marker="s", facecolor=INK2, edgecolor=SURF, lw=1, zorder=3,
            label=f"后 5 年（{halves[1][0]:%Y}–{end:%Y}）")
for x_, v in zip(xs, sweep["all"]):
    ax2.text(x_, (max(v, 0) if v >= 0 else min(v, 0)) + (0.004 if v >= 0 else -0.004),
             f"{v:+.3f}".replace("-", "−"), ha="center", va="bottom" if v >= 0 else "top",
             fontsize=8.5, color=INK2, weight="bold")
lim = max(0.06, np.abs(sweep[["all", "half0", "half1"]].values).max() + 0.015)
ax2.set_ylim(-lim, lim)
ax2.set_xticks(xs)
ax2.set_xticklabels([str(h) for h in HS])
ax2.set_xlabel("弹簧松弛半衰期（周）　短 = 只记得最近，长 = 记得很久", color=INK2)
ax2.set_ylabel("相关系数 r（弹簧位移 vs 下周涨跌幅）", color=INK2)
ax2.text(len(HS) - 0.6, band + 0.002, f"灰带 = 噪音范围 ±{band:.3f}", ha="right", fontsize=8, color=MUTED)
ax2.legend(loc="lower left", frameon=False, fontsize=8.5, labelcolor=INK2, ncol=3)
ax2.set_title("② 不同半衰期 + 前后两个 5 年是否一致", loc="left", fontsize=12, color=INK, pad=10)
fig.text(0.04, 0.94, "弹簧位移与下周涨跌幅的相关性（不扣大盘）", fontsize=17, color=INK, weight="bold")
fig.text(0.04, 0.905, f"{rng}；20 只合并；r > 0 = 惯性（涨了还涨），r < 0 = 回弹（涨多了要跌）",
         fontsize=10, color=INK2)
fig.text(0.04, 0.025, FOOT, fontsize=7.5, color=MUTED)
fig.savefig(FIG / "tech20_spring2_vs_pct_change.png", facecolor=SURF)
plt.close(fig)

# Figure 2: correlation table, stocks x half-life
order = tab.drop(index="20 只合并").sort_values(H).index.tolist() + ["20 只合并"]
T, P = tab.loc[order], sig_tab.loc[order]
div = LinearSegmentedColormap.from_list(
    "div", ["#a8322f", "#e34948", "#f0a5a0", "#f0efec", "#86b6ef", "#2a78d6", "#104281"])
cnorm = TwoSlopeNorm(vcenter=0, vmin=-0.2, vmax=0.2)
nr, nc = T.shape
fig = plt.figure(figsize=(11, 12), dpi=150, facecolor=SURF)
ax = fig.add_axes([0.14, 0.08, 0.7, 0.78], facecolor=SURF)
for i in range(nr):
    y = i if i < nr - 1 else i + 0.35
    for j in range(nc):
        v = T.iat[i, j]
        ax.add_patch(plt.Rectangle((j - 0.47, y - 0.45), 0.94, 0.9, color=div(cnorm(v)), lw=0))
        ax.text(j, y, f"{v:+.3f}".replace("-", "−") + ("*" if P.iat[i, j] < 0.05 else ""),
                ha="center", va="center", fontsize=8.5, color="#ffffff" if abs(v) >= 0.12 else INK,
                weight="bold" if HS[j] == H else "normal")
ax.set_xlim(-0.6, nc - 0.4)
ax.set_ylim(nr + 0.0, -0.6)
ax.set_yticks([i if i < nr - 1 else i + 0.35 for i in range(nr)])
ax.set_yticklabels(order, fontsize=9.5, color=INK2)
ax.set_xticks(range(nc))
ax.set_xticklabels([f"{h} 周" + ("\n（主）" if h == H else "") for h in HS], fontsize=9, color=INK2)
ax.xaxis.tick_top()
ax.tick_params(length=0)
for s in ax.spines.values():
    s.set_visible(False)
ax.text((nc - 1) / 2, -1.5, "弹簧松弛半衰期", ha="center", fontsize=9, color=MUTED)
cax = fig.add_axes([0.88, 0.3, 0.014, 0.4])
cb = fig.colorbar(plt.cm.ScalarMappable(cmap=div, norm=cnorm), cax=cax, extend="both")
cb.ax.tick_params(labelsize=8, colors=INK2)
cb.outline.set_visible(False)
cax.text(0.5, 1.07, "惯性\n涨了还涨", transform=cax.transAxes, ha="center", va="bottom", fontsize=8.5, color=INK2)
cax.text(0.5, -0.07, "回弹\n涨多了要跌", transform=cax.transAxes, ha="center", va="top", fontsize=8.5, color=INK2)
n_one = int(np.median([len(pairs(spring(H), t)[0]) for t in TICKERS]))
fig.text(0.04, 0.965, "相关性表：弹簧位移 vs 下周涨跌幅", fontsize=17, color=INK, weight="bold")
fig.text(0.04, 0.943, f"{rng}；每只约 {n_one} 周（PLTR 约 300 周）；按 {H} 周列从回弹到惯性排序；"
         f"* = p < 0.05（单只噪音范围约 ±{1.96 / np.sqrt(n_one):.2f}）", fontsize=9.5, color=INK2)
fig.text(0.04, 0.025, FOOT, fontsize=7.2, color=MUTED, wrap=True)
fig.savefig(FIG / "tech20_spring2_corr_table.png", facecolor=SURF)
plt.close(fig)
