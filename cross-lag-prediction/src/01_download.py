"""Download daily adjusted closes for US tech stocks plus QQQ from Yahoo Finance."""
import sys

import yfinance as yf

from common import DATA, TICKERS

OUT = DATA / "daily_close.csv"

if OUT.exists() and "--refresh" not in sys.argv:
    print(f"{OUT.name} exists; pass --refresh to re-download")
    sys.exit()

px = yf.download(TICKERS + ["QQQ"], start="2015-01-01", end="2026-10-29",
                 auto_adjust=True, progress=False)["Close"]
# keep only stocks with a full history so every model sees the same universe
start_ok = px.iloc[:5].notna().all()
px = px.loc[:, start_ok].dropna(how="all")
dropped = sorted(set(TICKERS) - set(px.columns))
px.to_csv(OUT)
print(f"saved {px.shape[1]} series x {px.shape[0]} days to {OUT.name}; dropped: {dropped}")
