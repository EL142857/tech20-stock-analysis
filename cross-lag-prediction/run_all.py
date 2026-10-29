"""Regenerate every figure and result table. Add --refresh to re-download prices from Yahoo Finance."""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
refresh = ["--refresh"] if "--refresh" in sys.argv else []
STEPS = [
    ["01_download.py", *refresh],
    ["02_lag_correlation.py"],
    ["03_walk_forward.py"],
    ["04_download_intraday.py", *refresh],
    ["05_intraday.py"],
    ["06_download_minute.py", *refresh],
    ["07_minute.py"],
]
for script, *args in STEPS:
    print(f"\n=== {script} {' '.join(args)}", flush=True)
    subprocess.run([sys.executable, str(SRC / script), *args], check=True)
