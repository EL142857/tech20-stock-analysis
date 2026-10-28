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
rng = f"{r.index[0]:%Y-%m-%d} to {r.index[-1]:%Y-%m-%d}, {n} weeks"

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

plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]
INK, INK2, MUTED, SURF = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
div = LinearSegmentedColormap.from_list(
    "div", ["#a8322f", "#e34948", "#f0a5a0", "#f0efec", "#86b6ef", "#2a78d6", "#104281"])
norm = TwoSlopeNorm(vcenter=0, vmin=-0.6, vmax=0.6)
FOOT = ("Data: Yahoo Finance (yfinance), adjusted weekly closes; * = significant (p < 0.05): binomial test for "
        f"direction agreement, t-test for Pearson; {n} weeks, so |value| below ~0.3 is mostly noise")


def fmt(v):
    return f"{v:+.2f}".replace("-", "−")


# 1) the table
cols = [("lag1", "1 week\nback"), ("lag2", "2 weeks\nback"), ("lag3", "3 weeks\nback"),
        ("weighted", "Weighted 4:2:1\n(main metric)"), ("pearson", "Pearson r\n(this week vs\nweighted mean)")]
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
ax.set_yticklabels(order + ["Average of 20"], fontsize=9.5, color=INK2)
ax.set_xticks(xpos)
ax.set_xticklabels([h for _, h in cols], fontsize=9, color=INK2)
ax.xaxis.tick_top()
ax.tick_params(length=0)
for s in ax.spines.values():
    s.set_visible(False)
ax.text(1, -1.75, "Direction agreement with an earlier week (+1 same, −1 opposite, averaged)",
        ha="center", va="center", fontsize=8.5, color=MUTED)
ax.plot([-0.45, 2.45], [-1.45, -1.45], color="#c3c2b7", lw=0.8, clip_on=False)
cax = fig.add_axes([0.9, 0.3, 0.014, 0.4])
cb = fig.colorbar(plt.cm.ScalarMappable(cmap=div, norm=norm), cax=cax, extend="both")
cb.ax.tick_params(labelsize=8, colors=INK2)
cb.outline.set_visible(False)
cax.text(0.5, 1.07, "Continues", transform=cax.transAxes, ha="center", va="bottom", fontsize=8.5, color=INK2)
cax.text(0.5, -0.07, "Reverses", transform=cax.transAxes, ha="center", va="top", fontsize=8.5, color=INK2)
fig.text(0.04, 0.965, "Trend Persistence: This Week vs the Weighted Previous 3 Weeks", fontsize=16, color=INK, weight="bold")
fig.text(0.04, 0.943, f"{rng}; previous 3 weeks weighted 4:2:1 (more recent = heavier); sorted by weighted agreement, high to low",
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
ax.legend(handles=[Patch(color="#2a78d6", label="Continue: this week's direction = weighted previous-3-week direction"),
                   Patch(color="#e34948", label="Reverse: this week's direction ≠ weighted previous-3-week direction")],
          loc="upper left", bbox_to_anchor=(0, -0.06), ncol=2, frameon=False, fontsize=9,
          labelcolor=INK2)
fig.text(0.04, 0.95, "Week-by-Week Trend Continuation / Reversal", fontsize=17, color=INK, weight="bold")
fig.text(0.04, 0.915, f"{rng}; each cell = that week's +1 or −1; label = full-period average (the table's 'Weighted' column), sorted high to low",
         fontsize=10, color=INK2)
fig.text(0.04, 0.02, "Data: Yahoo Finance (yfinance), adjusted weekly closes; previous 3 weeks weighted 4:2:1",
         fontsize=8, color=MUTED)
fig.savefig(FIG / "tech20_persistence_weekly.png", facecolor=SURF)
plt.close(fig)

pd.set_option("display.width", 200)
print(tbl.round(3).to_string())
print("avg:", avg.round(3).to_dict())
print("share of continue weeks, all:", round((agree.values > 0).mean() * 100, 1))
