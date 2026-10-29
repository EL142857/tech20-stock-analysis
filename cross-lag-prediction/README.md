# Can Earlier Moves of 63 Tech Stocks Predict Each One? (Daily, Half-Day, and Minute)

Follow-up to the [weekly analysis](../README.md) in this repository; self-contained (own scripts, data and `run_all.py`).

**Question.** Tech stocks are linked, so maybe stock A's % change today is a linear function of the last few days of % changes of *all* the tech stocks:

```
r_A,t = a_A + Σ_{k=1..L} Σ_j  x_{A,j,k} · r_j,t−k + ε,      r_j,t = P_j,t / P_j,t−1 − 1
```

Stacked over every stock this is a vector autoregression with a 63·L × 63 coefficient matrix **x**. This project tests (1) whether the lagged correlations it needs exist, and (2) whether the regression forecasts out of sample.

**Data.** 63 US-listed tech stocks with a full history since 2015 (internet, software, semiconductors, hardware/networking, IT services; QRVO failed to download) plus QQQ as the market, daily adjusted closes from Yahoo Finance, 2015-01-02 to 2026-10-28. Each cell is the simple daily % change against the previous close; 2,972 days.
Changes, not price levels: regressing a price on yesterday's price gives R² ≈ 99% for any random walk and says nothing about predictability.

## Disclaimer
- **AI-assisted work.** Code, figures and text were produced with Claude (Anthropic). Results have not been independently reviewed.
- **Not investment advice.** This is a statistics exercise.
- **Data** in `data/` (daily, hourly and 1-minute bars) comes from Yahoo Finance and is included only so the results can be reproduced; use and redistribution are subject to Yahoo's terms of service.

## Running
```
cd cross-lag-prediction
pip install -r requirements.txt
python run_all.py            # uses the cached data in data/; add --refresh to re-download
```
The ticker list is in `src/common.py`.

## 1. Correlation tests · `src/02_lag_correlation.py` → `figures/02_lag_correlation.png`, `results/lag_correlation.json`

C0[i,j] = corr(r_i,t, r_j,t), C1[i,j] = corr(r_i,t, r_j,t−1). Each C1 entry gets a heteroskedasticity-robust t-stat. Because the 3,906 off-diagonal tests are strongly dependent, the null for "share significant" comes from permutations that shuffle the days of the lagged block (keeps same-day co-movement, destroys lead-lag).

| test | result |
|---|---|
| mean same-day correlation C0 | **0.41** |
| mean next-day correlation C1 | **−0.045** (noise s.e. 0.018), max \|C1\| 0.17 |
| pairs with \|t\| > 1.96, lag 1 | **39.6%** vs permutation 95th pct 10.2% |
| … lags 2, 3, 4, 5 | 7.9%, 2.1%, 5.7%, 3.0% |
| QQQ yesterday → each stock today | 62% of stocks significant, mean t −2.24; pooled Newey-West t −2.03 |
| **excluding 15 Feb–30 Jun 2020** | mean C1 −0.016, **13.3%** significant vs null 10.0%; QQQ pooled t −1.42 |
| **idiosyncratic returns (same-day QQQ beta removed)** | mean C1 −0.001, **5.8%** significant vs null 5.9% (p = 0.07) |
| stability: C1 in 2015–20 vs 2020–26 | Pearson 0.27; **idiosyncratic −0.02** |
| "leader" stocks (column sums of C1) 1st vs 2nd half | Spearman −0.02, p = 0.87 |

**Reading.** The lag-1 signal is one common effect: after big Nasdaq days, the whole tech group partly reverses the next day, so every C1 entry shifts negative together. It is stronger in tech than in a broad universe, but mostly comes from the COVID crash and rebound; outside that window it is weak and no longer significant at the market level. Once the market is removed, nothing is left: the share of significant pairs equals the noise level, and which stock "leads" which does not repeat between the two halves.

## 2. The regression, walk-forward · `src/03_walk_forward.py` → `figures/03_walk_forward.png`, `results/walk_forward.csv`

Train on the previous 756 days, predict the next 21, roll forward (OOS 2018-01-11 to 2026-10-28, 2,211 days × 63 stocks). Benchmark: "tomorrow's change = 0". Ridge chooses its penalty per stock on the last year of each training window. Clark-West t tests each forecast against zero (pooled across stocks, Newey-West). Long-short = long the 6 highest predictions, short the 6 lowest, daily, 5 bp cost per unit traded.

| model | features | in-sample R² | **OOS R²** | OOS R² ex-COVID | hit rate | CW t | L/S Sharpe gross / net | net ex-COVID |
|---|---|---|---|---|---|---|---|---|
| historical mean | — | | +0.07% | +0.08% | 52.4% | 2.72 | 0.37 / 0.36 | 0.32 |
| own yesterday | 1 | | −0.00% | −0.47% | 52.3% | 3.11 | 0.34 / −0.79 | −0.98 |
| QQQ yesterday | 1 | | +0.21% | −0.60% | 52.3% | 3.02 | 1.22 / 0.44 | 0.23 |
| **OLS, all 63 × 1 day** (the proposed model) | 63 | 13.7% | **−10.8%** | −13.1% | 51.0% | 2.67 | 0.86 / −0.74 | −0.92 |
| OLS, all 63 × 5 days | 315 | 47.8% | **−85.8%** | −89.0% | 50.0% | 0.63 | 0.34 / −1.26 | −1.39 |
| ridge, all 63 × 1 day | 63 | | +0.19% | −0.42% | 52.2% | 3.20 | 1.00 / −0.10 | −0.14 |
| ridge, all 63 × 5 days | 315 | | −0.60% | −0.42% | 51.9% | 1.14 | 0.39 / −0.65 | −0.66 |
| 5 principal components of 63 × 5 days | 5 | | −1.29% | −1.15% | 51.3% | 1.71 | 0.85 / −0.48 | −0.56 |
| **placebo: OLS on random noise** | 63 | 8.0% | −8.2% | −8.6% | 49.4% | −1.46 | −0.21 / −1.83 | −1.91 |

52.7% of stock-days were up, so "always predict up" beats every hit rate above.

**Reading.**
- The full OLS version fits well in sample (14% with 63 features, 48% with 315) but forecasts far worse than guessing zero. Random-noise features already give 8% in-sample R² (≈ p/n = 63/756), so most of that fit is overfitting.
- Ridge shrinks the 5-day model toward zero (median chosen penalty 1000·n; the largest value on the grid, 10⁴·n, wins 43% of the time).
- The positive OOS R² values (QQQ yesterday +0.21%, ridge 1-day +0.19%) turn negative once the COVID window is removed. Their large Clark-West t-stats are driven by the same window.
- The one long-short that survives costs, "QQQ yesterday" (net 0.44, 0.23 ex-COVID), does no better than the historical-mean model it contains (net 0.36, 0.32 ex-COVID), which makes no use of yesterday at all: it simply tilts toward the stocks that drifted up most in the past three years, a momentum effect that tech had in this decade. The lagged information itself adds nothing after costs.

## 3. Within the day: morning → afternoon · `src/05_intraday.py` → `figures/05_intraday.png`, `results/intraday.json`, `results/intraday_walk_forward.csv`

Same idea at a shorter horizon, with no overnight break between signal and target. From Yahoo's 60-minute bars (available for about the last 730 trading days; `src/04_download_intraday.py`), 717 full sessions from 2023-12-11 to 2026-10-28 (half days dropped):

```
morning_j   = P_j(12:30) / P_j(09:30 open) − 1          (known at 12:30)
afternoon_i = P_i(16:00 close) / P_i(12:30) − 1
afternoon_i,t = a_i + Σ_j x_ij · morning_j,t + ε
```

Also tested: the "intraday momentum" pattern from the literature (Gao, Han, Li & Zhou 2018), where the overnight gap plus the opening period predicts the last half hour. With hourly bars the opening period is the first hour (09:30–10:30) rather than the first half hour.

With 717 days the noise standard error of a correlation is 0.037, so only correlations above about ±0.07 can be detected. That is enough to see an effect as large as the one reported for intraday momentum (correlation around 0.1 or more), but not much smaller ones.

**Correlation tests**

| test | result |
|---|---|
| mean correlation of afternoons with each other (same time) | **0.47** |
| mean corr(afternoon_i, morning_j) | **−0.003**, max \|corr\| 0.18 |
| pairs with \|t\| > 1.96 | **2.4%** vs permutation 95th pct 9.2% (p = 0.94); BH-FDR survivors: 0 |
| own morning → own afternoon | 6.3% of stocks significant, mean corr −0.02 |
| idiosyncratic (QQQ removed in both halves) | 4.5% significant vs null 6.1%; stability between halves 0.01 |
| QQQ morning → QQQ afternoon | corr 0.017 (NW t 0.31); −0.017 without April 2025 |
| QQQ morning → each stock's afternoon | 0% of stocks significant |
| QQQ overnight gap + first hour → last half hour | corr −0.004 (NW t −0.08) |
| same, each stock on its own | 3.2% significant, mean t −0.28 |

**Walk-forward.** Train on 250 days, predict the next 21 afternoons, roll forward (467 OOS days from 2024-12-11). The long-short and timing strategies open at 12:30 (or 15:30) and close at 16:00, so they pay to enter and exit every day.

| model | OOS R² | OOS R² ex-Apr 2025 | hit rate | CW t | L/S gross bp/day | Sharpe gross / 1 bp / 5 bp |
|---|---|---|---|---|---|---|
| historical mean | −0.32% | −0.23% | 50.2% | −0.70 | 0.7 | 0.12 / −0.59 / −3.43 |
| own morning | −1.03% | −1.04% | 49.9% | −0.52 | 3.8 | 0.87 / −0.04 / −3.65 |
| QQQ morning | −0.98% | −1.04% | 49.4% | −1.45 | −2.4 | −0.45 / −1.20 / −4.20 |
| **OLS, all 63 mornings** (in-sample R² 28%) | **−43.4%** | −62.8% | 50.4% | 0.63 | −0.4 | −0.08 / −0.84 / −3.87 |
| ridge, all 63 mornings | −1.73% | −2.19% | 49.6% | 0.23 | −1.1 | −0.23 / −1.06 / −4.38 |
| ridge, mornings + overnight gaps | −2.46% | −3.13% | 50.0% | −0.94 | −0.7 | −0.15 / −0.97 / −4.23 |
| placebo: OLS on random noise (in-sample R² 24%) | −31.4% | −44.1% | 49.3% | −0.14 | 1.7 | 0.35 / −0.47 / −3.74 |

50.2% of afternoons were up.

**QQQ timing rules with no fitted parameters** (trade QQQ by the sign of the signal)

| rule | hit rate | gross bp/day | Sharpe gross | gross ex-Apr 2025 | net of 1 bp per side |
|---|---|---|---|---|---|
| afternoon by sign of morning | 51.9% | 1.6 | 0.37 (t 0.60) | −0.03 | −0.08 |
| last half hour by sign of gap + first hour | 48.4% | −0.5 | −0.28 | −0.02 | −1.46 |

**Reading.** Within the day there is even less than across days: the morning-to-afternoon correlation matrix is indistinguishable from noise (fewer significant pairs than the permutation null), and every forecast loses to "the afternoon will be flat". The morning-sign QQQ rule's small gain is one day: on 2025-04-09 (tariff pause) a +1.4% morning was followed by a +10% afternoon; without April 2025 its Sharpe is −0.03. The intraday-momentum pattern does not show up in this 2023–2026 sample at the first-hour resolution available here.

## 4. Minute level: next 1-minute change, model comparison · `src/07_minute.py` → `figures/07_minute.png`, `results/minute.json`, `results/minute_models.csv`

Yahoo keeps 1-minute bars for only about 30 days (`src/06_download_minute.py`), so this section covers 20 sessions, 2026-10-01 to 2026-10-28. **Re-running later downloads a different 20 days, so the numbers will change.** Each value is the last trade price in the minute; r_i,t = P_i(t)/P_i(t−1) − 1, within the day only. The first 5 minutes of each session are used only as lags.

Walk-forward by day: train on the previous 5 sessions, predict every minute of the next one (15 test days, 5,760 minutes × 63 stocks).

| model | inputs |
|---|---|
| own last 5 min | per-stock OLS on its own last 5 one-minute changes |
| QQQ last 5 min | per-stock OLS on QQQ's last 5 |
| own + QQQ | both (10 inputs) |
| **ridge VAR** (the cross-stock idea) | all 63 stocks + QQQ, last 3 min (192 inputs), penalty chosen per stock on the last training day |
| pooled ridge | one linear model shared by all stocks, inputs scaled by each stock's volatility: own lags 1–5, QQQ lags 1–5, group-average lags 1–3, own and QQQ 15/30-minute moves, volume surprise, "no trade last minute" flag, time of day |
| pooled gradient boosting | same inputs, `HistGradientBoostingRegressor` |
| pooled neural net | same inputs, 64-32 MLP |

**Diagnostics** (all 20 days): the median minute move is 11 bp. Own lag-1 autocorrelation averages −0.030 (−0.042 for the less-traded half, the signature of bid-ask bounce). QQQ's last minute correlates +0.034 with the less-traded half's next minute but −0.003 with the most-traded half; across stocks, that lead rises with the share of minutes in which the stock did not trade (Spearman 0.66, panel A). 17% of cross-stock lag-1 pairs are significant vs a permutation 95th percentile of 7%.

**Results**

| model | OOS R² | hit rate | L/S gross bp/min (t) | break-even cost per side | net, best-case cost (t) | gross if filled 1 min late (t) | gross, 32 most-traded (t) |
|---|---|---|---|---|---|---|---|
| own last 5 min | −0.64% | 50.4% | 0.78 (7.1) | 0.24 bp | −0.28 | 0.18 (1.5) | 0.50 (3.7) |
| QQQ last 5 min | −0.59% | 50.4% | 0.34 (2.9) | 0.10 bp | −0.66 | 0.11 (1.0) | 0.01 (0.1) |
| own + QQQ | −1.02% | 51.0% | 1.23 (10.6) | 0.37 bp | +0.22 (1.9) | 0.35 (3.1) | 0.24 (1.8) |
| **ridge VAR, all 63 + QQQ** | −0.17% | 50.7% | 1.20 (11.2) | 0.43 bp | +0.35 (3.2) | **0.44 (4.0)** | −0.03 (−0.2) |
| **pooled ridge** | **−0.04%** | **51.4%** | **1.85 (12.9)** | **0.56 bp** | **+0.82 (5.8)** | 0.21 (1.6) | **0.97 (6.0)** |
| pooled gradient boosting | −3.31% | 50.7% | 1.09 (8.4) | 0.33 bp | +0.06 (0.4) | 0.18 (1.4) | 0.49 (3.2) |
| pooled neural net | −7.58% | 51.1% | 0.88 (7.7) | 0.26 bp | −0.19 | 0.09 (0.7) | 0.58 (3.9) |

L/S = each minute, long the 6 highest predictions and short the 6 lowest (3 and 3 for the 32-stock subset), held one minute, flat overnight; about 3.3 units traded per minute. Costs: the Roll estimate of the half-spread is ~2.1 bp for the names traded, which makes every model lose about 5–6 bp per minute. The "best case" charges only half of a 1¢ tick (~0.3 bp), i.e. assumes every quote is one cent wide.

**Reading.**
- Unlike the daily and half-day tests, the minute data do contain a statistically strong signal: every model's long-short earns money before costs, with t-stats of 3–13. Even so, no model beats "next minute = 0" in R², because the signal is a few percent of the noise.
- **Best model: pooled ridge.** A simple linear model shared across all stocks has the highest R², hit rate, and gross return. The nonlinear models (boosting, neural net) do worse on every measure: with a signal this weak they mostly fit noise, and they take 60–450 times longer to train.
- The signal is mostly microstructure, not information:
  - Most of it is short-lived reversal of the last trade (bid-ask bounce). Filled one minute late, the pooled ridge keeps only 11% of its gross return (0.21 bp, t 1.6).
  - The cross-stock part (ridge VAR) comes from **stale prices** in the less-traded stocks. When QQQ and peers move, a stock with no trades keeps showing its old price and "catches up" when it next trades. This part survives a one-minute delay (t 4.0) but disappears in the 32 most-traded stocks (t −0.2). In practice the quotes of such a stock have usually already moved, so the catch-up cannot be bought at the stale price.
- After costs nothing works. With realistic spreads every model loses. Even under the best-case one-cent spread, the profitable lines rely on being filled at a last-trade price that is already in the past. They also ignore latency, market impact, fees, and the fact that this is 15 days of a single month.

## Conclusion
For 63 large US tech stocks, yesterday's % changes across the group contain no usable stock-to-stock information about today's, and this morning's contain none about this afternoon's. At one minute there is a statistically clear signal, but it comes from bid-ask bounce and stale prices, is worth a fraction of a basis point per trade, and is smaller than the cost of trading. What exists is a market-wide reversal after extreme Nasdaq days, concentrated in 2020. The links between tech stocks are real but **same-day** (average correlation 0.41): they explain shared risk, not tomorrow's move.

Where lead-lag has been found in research: small/illiquid stocks lagging large ones (Lo & MacKinlay 1990), customer–supplier links (Cohen & Frazzini 2008), intraday horizons, and less efficient markets. Natural next steps: true first-half-hour data (needs a minute-bar source beyond Yahoo's 60-day limit) over a longer period, smaller-cap tech, or economically chosen links (e.g. chip suppliers → device makers) instead of all 63 × 63 pairs.
