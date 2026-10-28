"""Per-stock trend persistence: this week's direction vs the 4:2:1-weighted mean of the previous 3 weekly changes."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm, ListedColormap
from matplotlib.patches import Patch
from scipy.stats import binomtest, pearsonr

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, RES, FIG = ROOT / "data", ROOT / "results", ROOT / "figures"
for _d in (DATA, RES, FIG):
    _d.mkdir(exist_ok=True)
W = np.array([4, 2, 1]) / 7                      # exponential weights for lag 1, 2, 3 (halves each week back)

close = pd.read_csv(DATA / "tech20_weekly_close.csv", index_col=0, parse_dates=True)
r = close.pct_change() * 100                     # weekly % change
m = sum(W[k] * r.shift(k + 1) for k in range(3))  # weighted mean of the previous 3 weeks
rows = r.notna().all(axis=1) & m.notna().all(axis=1)
r, m = r[rows], m[rows]
lagged = {k: (close.pct_change() * 100).shift(k)[rows] for k in (1, 2, 3)}
n = len(r)
agree = np.sign(r) * np.sign(m)                  # +1 continue, -1 reverse
rng = f"{r.index[0]:%Y-%m-%d} 至 {r.index[-1]:%Y-%m-%d}，共 {n} 周"

tbl = pd.DataFrame(index=close.columns)
for k in (1, 2, 3):
    tbl[f"lag{k}"] = (np.sign(r) * np.sign(lagged[k])).mean()
tbl["weighted"] = agree.mean()
tbl["pearson"] = [pearsonr(r[t], m[t])[0] for t in close.columns]
tbl["p_weighted"] = [binomtest(int((agree[t] > 0).sum()), n).pvalue for t in close.columns]
tbl["p_pearson"] = [pearsonr(r[t], m[t])[1] for t in close.columns]
tbl = tbl.sort_values("weighted", ascending=False)
tbl.round(3).to_csv(RES / "tech20_persistence_table.csv")
order = tbl.index.tolist()

plt.rcParams["font.family"] = ["Microsoft YaHei", "Segoe UI", "sans-serif"]
INK, INK2, MUTED, SURF = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
div = LinearSegmentedColormap.from_list(
    "div", ["#a8322f", "#e34948", "#f0a5a0", "#f0efec", "#86b6ef", "#2a78d6", "#104281"])
norm = TwoSlopeNorm(vcenter=0, vmin=-0.6, vmax=0.6)
FOOT = ("数据：Yahoo Finance（yfinance，复权收盘价，周线）；* = 统计显著（p < 0.05）："
        f"方向一致性用二项检验，Pearson 用 t 检验；样本 {n} 周，|值| 小于约 0.3 基本可视为噪音")


def fmt(v):
    return f"{v:+.2f}".replace("-", "−")


# 1) the table
cols = [("lag1", "上 1 周"), ("lag2", "上 2 周"), ("lag3", "上 3 周"),
        ("weighted", "加权 4:2:1\n（主指标）"), ("pearson", "Pearson 相关\n（本周 vs 加权均值）")]
xpos = [0, 1, 2, 3.25, 4.5]                      # small gaps set the main metric and Pearson apart
avg = tbl[[c for c, _ in cols]].mean()
k = len(order)
fig = plt.figure(figsize=(10, 12.5), dpi=150, facecolor=SURF)
ax = fig.add_axes([0.14, 0.07, 0.72, 0.76], facecolor=SURF)
for (c, _), x in zip(cols, xpos):
    vals = list(tbl[c]) + [avg[c]]
    for i, v in enumerate(vals):
        y = i if i < k else k + 0.35
        ax.add_patch(plt.Rectangle((x - 0.47, y - 0.45), 0.94, 0.9, color=div(norm(v)), lw=0))
        star = ""
        if i < k and c in ("weighted", "pearson"):
            star = "*" if tbl[f"p_{c}"].iloc[i] < 0.05 else ""
        ax.text(x, y, fmt(v) + star, ha="center", va="center", fontsize=9,
                color="#ffffff" if abs(v) >= 0.35 else INK,
                weight="bold" if c == "weighted" else "normal")
ax.set_xlim(-0.6, xpos[-1] + 0.6)
ax.set_ylim(k + 0.9, -0.6)
ax.set_yticks(list(range(k)) + [k + 0.35])
ax.set_yticklabels(order + ["20 只平均"], fontsize=9.5, color=INK2)
ax.set_xticks(xpos)
ax.set_xticklabels([h for _, h in cols], fontsize=9, color=INK2)
ax.xaxis.tick_top()
ax.tick_params(length=0)
for s in ax.spines.values():
    s.set_visible(False)
ax.text(1, -1.75, "方向一致性：本周涨跌方向 vs 该周之前的方向（同向 +1，反向 −1，取平均）",
        ha="center", va="center", fontsize=8.5, color=MUTED)
ax.plot([-0.45, 2.45], [-1.45, -1.45], color="#c3c2b7", lw=0.8, clip_on=False)
cax = fig.add_axes([0.9, 0.3, 0.014, 0.4])
cb = fig.colorbar(plt.cm.ScalarMappable(cmap=div, norm=norm), cax=cax, extend="both")
cb.ax.tick_params(labelsize=8, colors=INK2)
cb.outline.set_visible(False)
cb.set_label("蓝 = 趋势延续　红 = 趋势反转", color=INK2)
fig.text(0.04, 0.965, "20 家科技股趋势延续性：本周 vs 前 3 周加权", fontsize=16, color=INK, weight="bold")
fig.text(0.04, 0.943, f"{rng}；前 3 周权重按指数递减 4:2:1（越近越重）；按加权方向一致性从高到低排序",
         fontsize=9.5, color=INK2)
fig.text(0.04, 0.025, FOOT, fontsize=7.5, color=MUTED, wrap=True)
fig.savefig(FIG / "tech20_persistence_table.png", facecolor=SURF)
plt.close(fig)

# 2) week-by-week map of +1 / -1
A = agree[order].T.values
fig = plt.figure(figsize=(15, 8.5), dpi=150, facecolor=SURF)
ax = fig.add_axes([0.08, 0.12, 0.86, 0.74], facecolor=SURF)
ax.pcolormesh(np.arange(n + 1) - 0.5, np.arange(k + 1) - 0.5, A,
              cmap=ListedColormap(["#e34948", "#2a78d6"]), vmin=-1, vmax=1,
              edgecolors=SURF, linewidth=1.2)
ax.set_yticks(range(k))
ax.set_yticklabels([f"{t}  {fmt(tbl.loc[t, 'weighted'])}" for t in order], fontsize=8.5, color=INK2)
months = [i for i in range(1, n) if r.index[i].month != r.index[i - 1].month]
months = [0] + months[1::2]
ax.set_xticks(months)
ax.set_xticklabels([r.index[i].strftime("%Y-%m") for i in months], fontsize=8.5, color=INK2)
ax.set_ylim(k - 0.5, -0.5)
ax.tick_params(length=0)
for s in ax.spines.values():
    s.set_visible(False)
ax.legend(handles=[Patch(color="#2a78d6", label="延续：本周方向 = 前 3 周加权方向"),
                   Patch(color="#e34948", label="反转：本周方向 ≠ 前 3 周加权方向")],
          loc="upper left", bbox_to_anchor=(0, -0.06), ncol=2, frameon=False, fontsize=9,
          labelcolor=INK2)
fig.text(0.04, 0.95, "20 家科技股逐周趋势延续 / 反转", fontsize=17, color=INK, weight="bold")
fig.text(0.04, 0.915, f"{rng}；每格 = 该周的 +1 或 −1；股票名旁为全年平均（即表中“加权”列），自上而下从高到低",
         fontsize=10, color=INK2)
fig.text(0.04, 0.02, "数据：Yahoo Finance（yfinance，复权收盘价，周线）；前 3 周权重 4:2:1",
         fontsize=8, color=MUTED)
fig.savefig(FIG / "tech20_persistence_weekly.png", facecolor=SURF)
plt.close(fig)

pd.set_option("display.width", 200)
print(tbl.round(3).to_string())
print("avg:", avg.round(3).to_dict())
print("share of continue weeks, all:", round((agree.values > 0).mean() * 100, 1))
