"""1-year weekly closes of 20 tech stocks -> 3D surfaces (normalized index and raw USD price).

Uses the cached data/tech20_weekly_close.csv; pass --refresh to download the latest year again.
"""
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm, Normalize

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, RES, FIG = ROOT / "data", ROOT / "results", ROOT / "figures"
for _d in (DATA, RES, FIG):
    _d.mkdir(exist_ok=True)
TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "ORCL", "AMD",
           "CRM", "ADBE", "NFLX", "INTC", "QCOM", "CSCO", "IBM", "TXN", "MU", "PLTR"]
CACHE = DATA / "tech20_weekly_close.csv"

if CACHE.exists() and "--refresh" not in sys.argv:
    close = pd.read_csv(CACHE, index_col=0, parse_dates=True)
else:
    import yfinance as yf
    raw = yf.download(TICKERS, period="1y", interval="1wk", auto_adjust=True, progress=False, threads=False)
    close = raw["Close"][TICKERS].dropna(how="all").ffill()
    missing = [t for t in TICKERS if close[t].isna().all()]
    assert not missing, f"failed: {missing}"
    close = close.dropna()
    close.to_csv(CACHE, float_format="%.4f")
print(close.shape, close.index[0].date(), "->", close.index[-1].date())

plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]
INK, INK2, MUTED, SURF = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"

# diverging blue <-> red with gray midpoint (palette.md)
div = LinearSegmentedColormap.from_list(
    "div", ["#a8322f", "#e34948", "#f0a5a0", "#f0efec", "#86b6ef", "#2a78d6", "#104281"])
seq = LinearSegmentedColormap.from_list(
    "seq", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])


def plot(Z, order, cmap, norm, zlabel, title, subtitle, fname, cticks=None):
    weeks = np.arange(len(close))
    X, Y = np.meshgrid(weeks, np.arange(len(order)))
    fig = plt.figure(figsize=(15, 10.5), dpi=150, facecolor=SURF)
    ax = fig.add_axes([-0.04, 0.0, 0.92, 0.9], projection="3d", facecolor=SURF)
    ax.plot_surface(X, Y, Z, cmap=cmap, norm=norm, rstride=1, cstride=1,
                    linewidth=0.25, edgecolor=(1, 1, 1, 0.55), antialiased=True, shade=False)
    ax.set_yticks(np.arange(len(order)))
    ax.set_yticklabels(order, fontsize=7.5, color=INK2, va="center", ha="left")
    # tick every other month, at the first week of that month
    months = [i for i in range(1, len(close)) if close.index[i].month != close.index[i - 1].month]
    months = [0] + months[1::2]
    ax.set_xticks(months)
    ax.set_xticklabels([close.index[i].strftime("%Y-%m") for i in months], fontsize=8, color=INK2)
    ax.tick_params(axis="z", labelsize=8, colors=INK2)
    ax.tick_params(axis="y", pad=1)
    ax.set_xlabel("Week", color=INK2, labelpad=10)
    ax.set_zlabel(zlabel, color=INK2, labelpad=10)
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.set_pane_color((0.99, 0.99, 0.98, 1))
        a._axinfo["grid"].update(color="#e1e0d9", linewidth=0.6)
    ax.view_init(elev=27, azim=-56)
    ax.set_box_aspect((2.2, 2.0, 1.1), zoom=1.12)
    cax = fig.add_axes([0.9, 0.3, 0.012, 0.38])
    cb = fig.colorbar(plt.cm.ScalarMappable(cmap=cmap, norm=norm), cax=cax)
    if cticks is not None:
        cb.set_ticks(cticks)
    cb.ax.tick_params(labelsize=8, colors=INK2)
    cb.outline.set_visible(False)
    fig.text(0.04, 0.95, title, fontsize=17, color=INK, weight="bold")
    fig.text(0.04, 0.92, subtitle, fontsize=10, color=INK2)
    fig.text(0.04, 0.02, "Data: Yahoo Finance (yfinance), adjusted weekly closes", fontsize=8, color=MUTED)
    fig.savefig(FIG / fname, facecolor=SURF)
    plt.close(fig)


rng = f"{close.index[0]:%Y-%m-%d} to {close.index[-1]:%Y-%m-%d}, {len(close)} weeks"

# 1) normalized: first week = 100, stocks ordered by 1-year return
idx = close / close.iloc[0] * 100
order = idx.iloc[-1].sort_values().index.tolist()
Z = idx[order].T.values
plot(Z, order, div, TwoSlopeNorm(vcenter=100, vmin=Z.min(), vmax=Z.max()),
     "Index (first week = 100)", "20 Tech Stocks: One Year of Weekly Closes (Normalized)",
     f"{rng}; sorted by 1-year return, low to high; blue = above the first week, red = below, light gray = flat",
     "tech20_surface_normalized.png",
     cticks=[t for t in [50, 75, 100, 200, 300, 400, 500] if Z.min() <= t <= Z.max()])

# 2) raw price in USD, stocks ordered by latest price
order_p = close.iloc[-1].sort_values().index.tolist()
Zp = close[order_p].T.values
plot(Zp, order_p, seq, Normalize(Zp.min(), Zp.max()),
     "Price (USD)", "20 Tech Stocks: One Year of Weekly Closes (Raw Price)",
     f"{rng}; sorted by latest price, low to high", "tech20_surface_price.png")

print((idx.iloc[-1] - 100).sort_values(ascending=False).round(1).to_string())
