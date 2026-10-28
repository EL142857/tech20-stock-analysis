"""Download 10 years of weekly closes for the 20 stocks plus QQQ (the market background) for the spring models.

Skips the download when data/tech20_qqq_weekly_10y.csv exists; pass --refresh to download again.
"""
import sys
import pandas as pd

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, RES, FIG = ROOT / "data", ROOT / "results", ROOT / "figures"
for _d in (DATA, RES, FIG):
    _d.mkdir(exist_ok=True)
TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "ORCL", "AMD",
           "CRM", "ADBE", "NFLX", "INTC", "QCOM", "CSCO", "IBM", "TXN", "MU", "PLTR"]
CACHE = DATA / "tech20_qqq_weekly_10y.csv"

if CACHE.exists() and "--refresh" not in sys.argv:
    print("cached:", CACHE.name)
    sys.exit()

import yfinance as yf
raw = yf.download(TICKERS + ["QQQ"], period="10y", interval="1wk", auto_adjust=True,
                  progress=False, threads=False)
close = raw["Close"][TICKERS + ["QQQ"]].dropna(how="all")
if close.index[-1] + pd.Timedelta(days=7) > pd.Timestamp.today():
    close = close.iloc[:-1]                       # drop the unfinished current week
print(close.shape, close.index[0].date(), "->", close.index[-1].date())
print(close.notna().sum().sort_values().head(3).to_string())
close.to_csv(CACHE, float_format="%.4f")
