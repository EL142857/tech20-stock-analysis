"""Cross-stock direction agreement: signal = close / mean(previous 3 closes) - 1; +1 same sign, -1 opposite, averaged."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, RES, FIG = ROOT / "data", ROOT / "results", ROOT / "figures"
for _d in (DATA, RES, FIG):
    _d.mkdir(exist_ok=True)
LAG = 3
close = pd.read_csv(DATA / "tech20_weekly_close.csv", index_col=0, parse_dates=True)
x = (close / close.rolling(LAG).mean().shift(1) - 1).dropna() * 100   # this week vs prior 3-week mean
n_weeks = len(x)
rng = f"{x.index[0]:%Y-%m-%d} 至 {x.index[-1]:%Y-%m-%d}，共 {n_weeks} 周"

# direction agreement: +1 if same sign that week, -1 if opposite, averaged over weeks
sgn = np.sign(x.values)
S = pd.DataFrame(sgn.T @ sgn / n_weeks, index=x.columns, columns=x.columns)
R = x.corr()                                                          # Pearson, for comparison

# cluster order so stocks that move together sit next to each other
Z = linkage(squareform(1 - S.values, checks=False), "average", optimal_ordering=True)
order = S.index[leaves_list(Z)].tolist()
S, R = S.loc[order, order], R.loc[order, order]
S.round(3).to_csv(RES / "tech20_direction_agreement.csv")
R.round(3).to_csv(RES / "tech20_pearson_corr.csv")

plt.rcParams["font.family"] = ["Microsoft YaHei", "Segoe UI", "sans-serif"]
INK, INK2, MUTED, SURF, DIAG = "#0b0b0b", "#52514e", "#898781", "#fcfcfb", "#e1e0d9"
div = LinearSegmentedColormap.from_list(
    "div", ["#a8322f", "#e34948", "#f0a5a0", "#f0efec", "#86b6ef", "#2a78d6", "#104281"])
norm = TwoSlopeNorm(vcenter=0, vmin=-1, vmax=1)
FOOT = ("数据：Yahoo Finance（yfinance，复权收盘价，周线）；信号 = 本周收盘 / 前3周平均收盘 − 1")


def heatmap(M, title, subtitle, cblabel, fname):
    k = len(order)
    V = M.values.copy()
    np.fill_diagonal(V, np.nan)
    fig = plt.figure(figsize=(13, 12), dpi=150, facecolor=SURF)
    ax = fig.add_axes([0.1, 0.07, 0.76, 0.8], facecolor=DIAG)
    ax.pcolormesh(np.arange(k + 1) - 0.5, np.arange(k + 1) - 0.5, V, cmap=div, norm=norm,
                  edgecolors=SURF, linewidth=1.5)
    for i in range(k):
        for j in range(k):
            if i == j:
                continue
            v = V[i, j]
            dark = abs(v) >= 0.5
            ax.text(j, i, f"{v:.2f}".replace("0.", ".").replace("-.", "−."), ha="center", va="center",
                    fontsize=6.5, color="#ffffff" if dark else INK2)
    ax.set_xticks(range(k))
    ax.set_yticks(range(k))
    ax.set_xticklabels(order, fontsize=8.5, color=INK2, rotation=90)
    ax.set_yticklabels(order, fontsize=8.5, color=INK2)
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    ax.invert_yaxis()
    ax.set_aspect("equal")
    for s in ax.spines.values():
        s.set_visible(False)
    cax = fig.add_axes([0.89, 0.3, 0.014, 0.4])
    cb = fig.colorbar(plt.cm.ScalarMappable(cmap=div, norm=norm), cax=cax)
    cb.ax.tick_params(labelsize=8, colors=INK2)
    cb.outline.set_visible(False)
    cb.set_label(cblabel, color=INK2)
    fig.text(0.04, 0.965, title, fontsize=17, color=INK, weight="bold")
    fig.text(0.04, 0.94, subtitle, fontsize=10, color=INK2)
    fig.text(0.04, 0.02, FOOT, fontsize=8, color=MUTED)
    fig.savefig(FIG / fname, facecolor=SURF)
    plt.close(fig)


heatmap(S, "20 家科技股方向一致性矩阵",
        f"{rng}；逐周比较两只股票的信号方向：同向 +1，反向 −1，取平均（= 同向周占比 × 2 − 1）",
        "方向一致性（−1 ~ +1）", "tech20_direction_agreement_heatmap.png")
heatmap(R, "20 家科技股相关系数矩阵（Pearson，对照）",
        f"{rng}；与方向一致性用同一信号、同一排序，但同时考虑涨跌幅度",
        "相关系数（−1 ~ +1）", "tech20_pearson_corr_heatmap.png")

# 3D surface of the direction-agreement matrix
k = len(order)
V = S.values.copy()
np.fill_diagonal(V, np.nan)
Xg, Yg = np.meshgrid(np.arange(k), np.arange(k))
fig = plt.figure(figsize=(14, 11), dpi=150, facecolor=SURF)
ax = fig.add_axes([-0.02, 0.0, 0.9, 0.9], projection="3d", facecolor=SURF)
ax.plot_surface(Xg, Yg, np.ma.masked_invalid(V), cmap=div, norm=norm, rstride=1, cstride=1,
                linewidth=0.3, edgecolor=(1, 1, 1, 0.6), antialiased=True, shade=False)
ax.set_xticks(range(k))
ax.set_xticklabels(order, fontsize=7, color=INK2, rotation=0, ha="right")
ax.set_yticks(range(k))
ax.set_yticklabels(order, fontsize=7, color=INK2, ha="left")
ax.tick_params(axis="z", labelsize=8, colors=INK2)
ax.set_zlim(-1, 1)
ax.set_zlabel("方向一致性", color=INK2, labelpad=8)
for a in (ax.xaxis, ax.yaxis, ax.zaxis):
    a.set_pane_color((0.99, 0.99, 0.98, 1))
    a._axinfo["grid"].update(color="#e1e0d9", linewidth=0.6)
ax.view_init(elev=32, azim=-50)
ax.set_box_aspect((1.6, 1.6, 0.8), zoom=1.1)
cax = fig.add_axes([0.9, 0.3, 0.012, 0.38])
cb = fig.colorbar(plt.cm.ScalarMappable(cmap=div, norm=norm), cax=cax)
cb.ax.tick_params(labelsize=8, colors=INK2)
cb.outline.set_visible(False)
cb.set_label("方向一致性（−1 ~ +1）", color=INK2)
fig.text(0.04, 0.95, "20 家科技股方向一致性（三维曲面）", fontsize=17, color=INK, weight="bold")
fig.text(0.04, 0.92, f"{rng}；同向 +1、反向 −1 后取平均；对角线（自己和自己）留空", fontsize=10, color=INK2)
fig.text(0.04, 0.02, FOOT, fontsize=8, color=MUTED)
fig.savefig(FIG / "tech20_direction_agreement_surface.png", facecolor=SURF)
plt.close(fig)

# summary
iu = np.triu_indices(k, 1)
pairs = pd.DataFrame({"a": np.array(order)[iu[0]], "b": np.array(order)[iu[1]],
                      "S": S.values[iu], "R": R.values[iu]})
print("order:", order)
print("mean S:", round(pairs.S.mean(), 3), " mean R:", round(pairs.R.mean(), 3),
      " corr(S,R):", round(np.corrcoef(pairs.S, pairs.R)[0, 1], 3), " #S<0:", (pairs.S < 0).sum())
print("top S:\n", pairs.nlargest(8, "S").round(2).to_string(index=False))
print("bottom S:\n", pairs.nsmallest(8, "S").round(2).to_string(index=False))
print("avg S per stock:\n", ((S.sum() - 1) / (k - 1)).sort_values().round(2).to_string())
