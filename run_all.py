"""Regenerate every figure and result table. Add --refresh to re-download prices from Yahoo Finance."""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
refresh = ["--refresh"] if "--refresh" in sys.argv else []
STEPS = [
    ["01_surface_3d.py", *refresh],
    ["02_pct_change.py", "1"],
    ["02_pct_change.py", "3"],
    ["02_pct_change.py", "3", "avg"],
    ["03_cross_stock_direction.py"],
    ["04_persistence.py"],
    ["05_download_10y.py", *refresh],
    ["06_spring_vs_market.py"],
    ["07_spring_raw_pct.py"],
]
for script, *args in STEPS:
    print(f"\n=== {script} {' '.join(args)}", flush=True)
    subprocess.run([sys.executable, str(SRC / script), *args], check=True)
