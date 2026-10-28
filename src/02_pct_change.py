"""Weekly % change vs N weeks earlier (or vs the mean of the previous N weeks) -> heatmap + 3D surface.

Usage: python 02_pct_change.py [N] [avg]   e.g. 1 | 3 | 3 avg
"""
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, RES, FIG = ROOT / "data", ROOT / "results", ROOT / "figures"
for _d in (DATA, RES, FIG):
    _d.mkdir(exist_ok=True)
LAG = int(sys.argv[1]) if len(sys.argv) > 1 else 1   # compare with the close LAG weeks earlier
AVG = len(sys.argv) > 2 and sys.argv[2] == "avg"     # ...or with the mean of the previous LAG closes
TAG = "pct" if LAG == 1 else f"pct{LAG}w" + ("avg" if AVG else "")
NAME = "周涨跌幅" if LAG == 1 else (f"相对前{LAG}周均价涨跌幅" if AVG else f"{LAG}周涨跌幅")
BASE = "上周" if LAG == 1 else (f"前{LAG}周平均" if AVG else f"{LAG}周前")

close = pd.read_csv(DATA / "tech20_weekly_close.csv", index_col=0, parse_dates=True)
ref = close.rolling(LAG).mean().shift(1) if AVG else close.shift(LAG)
pct = (close / ref - 1).dropna() * 100
pct.to_csv(RES / f"tech20_weekly_{TAG}.csv", float_format="%.2f")

total = (close.iloc[-1] / close.iloc[0] - 1) * 100
order = total.sort_values().index.tolist()          # same order as the normalized surface
P = pct[order].T.values
weeks = np.arange(len(pct))
rng = f"{pct.index[0]:%Y-%m-%d} 至 {pct.index[-1]:%Y-%m-%d}，共 {len(pct)} 周"

plt.rcParams["font.family"] = ["Microsoft YaHei", "Segoe UI", "sans-serif"]
INK, INK2, MUTED, SURF = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
div = LinearSegmentedColormap.from_list(
    "div", ["#a8322f", "#e34948", "#f0a5a0", "#f0efec", "#86b6ef", "#2a78d6", "#104281"])
lim = np.ceil(np.percentile(np.abs(P), 98) / 5) * 5  # symmetric, clip the rare extremes
norm = TwoSlopeNorm(vcenter=0, vmin=-lim, vmax=lim)

# tick every other month, at the first week of that month
months = [i for i in range(1, len(pct)) if pct.index[i].month != pct.index[i - 1].month]
months = [0] + months[1::2]
mlabels = [pct.index[i].strftime("%Y-%m") for i in months]


def header(fig, title, subtitle, sub_y=0.92):
    fig.text(0.04, 0.95, title, fontsize=17, color=INK, weight="bold")
    fig.text(0.04, sub_y, subtitle, fontsize=10, color=INK2)
    fig.text(0.04, 0.02, f"数据：Yahoo Finance（yfinance，复权收盘价，周线）；{NAME} = 本周收盘 / {BASE}收盘 − 1",
             fontsize=8, color=MUTED)


def colorbar(fig, rect):
    cax = fig.add_axes(rect)
    cb = fig.colorbar(plt.cm.ScalarMappable(cmap=div, norm=norm), cax=cax, extend="both")
    cb.ax.tick_params(labelsize=8, colors=INK2)
    cb.outline.set_visible(False)
    cb.set_label(f"{NAME}（%）", color=INK2)


# 1) 3D surface
X, Y = np.meshgrid(weeks, np.arange(len(order)))
fig = plt.figure(figsize=(15, 10.5), dpi=150, facecolor=SURF)
ax = fig.add_axes([-0.04, 0.0, 0.92, 0.9], projection="3d", facecolor=SURF)
ax.plot_surface(X, Y, P, cmap=div, norm=norm, rstride=1, cstride=1,
                linewidth=0.25, edgecolor=(1, 1, 1, 0.55), antialiased=True, shade=False)
ax.set_yticks(np.arange(len(order)))
ax.set_yticklabels(order, fontsize=7.5, color=INK2, va="center", ha="left")
ax.set_xticks(months)
ax.set_xticklabels(mlabels, fontsize=8, color=INK2)
ax.tick_params(axis="z", labelsize=8, colors=INK2)
ax.tick_params(axis="y", pad=1)
ax.set_xlabel("周", color=INK2, labelpad=10)
ax.set_zlabel(f"{NAME}（%）", color=INK2, labelpad=10)
for a in (ax.xaxis, ax.yaxis, ax.zaxis):
    a.set_pane_color((0.99, 0.99, 0.98, 1))
    a._axinfo["grid"].update(color="#e1e0d9", linewidth=0.6)
ax.view_init(elev=27, azim=-56)
ax.set_box_aspect((2.2, 2.0, 1.1), zoom=1.12)
colorbar(fig, [0.9, 0.3, 0.012, 0.38])
header(fig, f"20 家科技股一年{NAME}（三维曲面）",
       f"{rng}；按一年总涨幅从低到高排列；蓝 = 比{BASE}高，红 = 比{BASE}低，浅灰 ≈ 0%")
fig.savefig(FIG / f"tech20_{TAG}_surface.png", facecolor=SURF)
plt.close(fig)

# 2) flat heatmap of the same matrix
fig = plt.figure(figsize=(15, 8.5), dpi=150, facecolor=SURF)
ax = fig.add_axes([0.07, 0.1, 0.8, 0.76], facecolor=SURF)
ax.pcolormesh(np.arange(len(pct) + 1) - 0.5, np.arange(len(order) + 1) - 0.5, P,
              cmap=div, norm=norm, edgecolors=SURF, linewidth=1.2)
ax.set_yticks(np.arange(len(order)))
ax.set_yticklabels([f"{t}  {total[t]:+.0f}%" for t in order], fontsize=8.5, color=INK2)
ax.set_xticks(months)
ax.set_xticklabels(mlabels, fontsize=8.5, color=INK2)
ax.tick_params(length=0)
for s in ax.spines.values():
    s.set_visible(False)
ax.set_xlabel("周", color=INK2)
colorbar(fig, [0.9, 0.25, 0.012, 0.5])
header(fig, f"20 家科技股一年{NAME}（平面热力图）",
       f"{rng}；每格 = 该周收盘相对{BASE}收盘的涨跌幅；股票名旁为一年总涨跌幅，自上而下从高到低",
       sub_y=0.905)
fig.savefig(FIG / f"tech20_{TAG}_heatmap.png", facecolor=SURF)
plt.close(fig)

print("color limit ±", lim)
s = pct.stack().sort_values()
print("worst:\n", s.head(5).round(1).to_string())
print("best:\n", s.tail(5).round(1).to_string())
print("share of windows up (%):", round((P > 0).mean() * 100, 1))
print("std (%):\n", pct.std().sort_values(ascending=False).round(1).head(5).to_string())
