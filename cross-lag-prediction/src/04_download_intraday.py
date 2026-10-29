"""Download hourly bars (regular session) for the same tech stocks plus QQQ.

Yahoo keeps 60-minute bars for about the last 730 days. Bars are labelled by their
start: 09:30, 10:30, ..., 15:30 (the last one is 30 minutes long).
"""
import sys

import yfinance as yf

from common import DATA, TICKERS

OUT_O, OUT_C = DATA / "hourly_open.csv", DATA / "hourly_close.csv"

if OUT_C.exists() and "--refresh" not in sys.argv:
    print(f"{OUT_C.name} exists; pass --refresh to re-download")
    sys.exit()

bars = yf.download(TICKERS + ["QQQ"], period="730d", interval="60m",
                   auto_adjust=True, progress=False, prepost=False)
bars = bars.dropna(how="all")
bars["Open"].to_csv(OUT_O)
bars["Close"].to_csv(OUT_C)
print(f"saved {bars['Close'].shape[1]} series x {len(bars)} bars, "
      f"{bars.index[0]} to {bars.index[-1]}")
