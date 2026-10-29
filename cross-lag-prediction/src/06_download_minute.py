"""Download 1-minute bars (regular session) for the same tech stocks plus QQQ.

Yahoo keeps 1-minute bars for only about the last 30 days and serves at most
8 days per request, so the window is fetched in 7-day chunks.
"""
import sys

import pandas as pd
import yfinance as yf

from common import DATA, TICKERS

OUT_C, OUT_V = DATA / "minute_close.csv", DATA / "minute_volume.csv"

if OUT_C.exists() and "--refresh" not in sys.argv:
    print(f"{OUT_C.name} exists; pass --refresh to re-download")
    sys.exit()

# up to yesterday: a session still in progress would leave a partial day
end = pd.Timestamp.now(tz="America/New_York").normalize()
start = end - pd.Timedelta(days=28)
chunks = []
while start < end:
    stop = min(start + pd.Timedelta(days=7), end)
    bars = yf.download(TICKERS + ["QQQ"], start=start.date(), end=stop.date(), interval="1m",
                       auto_adjust=True, progress=False, prepost=False)
    if len(bars):
        chunks.append(bars)
    start = stop
bars = pd.concat(chunks).sort_index()
bars = bars[~bars.index.duplicated()].dropna(how="all")
bars["Close"].to_csv(OUT_C)
bars["Volume"].to_csv(OUT_V)
print(f"saved {bars['Close'].shape[1]} series x {len(bars)} minutes, "
      f"{bars.index.normalize().nunique()} days, {bars.index[0]} to {bars.index[-1]}")
