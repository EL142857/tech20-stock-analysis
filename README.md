# 20 家科技股周线分析：从三维曲面到“弹簧模型”

一步步追问的探索记录：先把 20 家科技股一年的周线画成三维曲面，再换成涨跌幅、方向一致性、趋势延续性，最后搭了一个“弹簧势能”模型，检验它能不能预测下周涨跌。

**股票（20 只）：** AAPL、MSFT、NVDA、GOOGL、AMZN、META、TSLA、AVGO、ORCL、AMD、CRM、ADBE、NFLX、INTC、QCOM、CSCO、IBM、TXN、MU、PLTR
**大盘背景：** QQQ（纳斯达克 100 ETF）
**数据：** Yahoo Finance（经 `yfinance`），复权周收盘价。一年数据为 2025-10-27 至 2026-10-26（最后一周在下载时未收盘）；十年数据为 2016-10-24 至 2026-10-19。

> 本仓库是统计研究与可视化练习，不构成任何投资建议。

## 目录结构

```
src/        分析脚本（按编号顺序运行）
data/       原始周收盘价（缓存，脚本默认直接读取）
results/    计算出的表格（CSV）
figures/    所有图片
run_all.py  一键重新生成全部结果
```

## 运行

```bash
pip install -r requirements.txt
python run_all.py            # 用 data/ 里的缓存数据，结果与本仓库一致
python run_all.py --refresh  # 重新下载最新价格
```

图里的中文用 Windows 的 Microsoft YaHei 字体；在 macOS / Linux 上请把脚本里的 `font.family` 换成本机有的中文字体（如 PingFang SC、Noto Sans CJK SC）。

---

## 1. 一年周线三维曲面 · `01_surface_3d.py`

横轴为周，纵轴为股票，高度为价格。归一化版本以首周 = 100，按一年涨幅排序；原始价格版本按最新股价排序。

| 归一化（首周 = 100） | 原始价格（美元） |
|---|---|
| ![](figures/tech20_surface_normalized.png) | ![](figures/tech20_surface_price.png) |

一年涨跌：MU +333%、INTC +135%、AMD +122%、TXN +93% 领涨；ORCL −50%、NFLX −45%、ADBE −27% 领跌。

## 2. 涨跌幅三种算法 · `02_pct_change.py`

| 参数 | 每格 = | 图 |
|---|---|---|
| `1` | 本周收盘 / 上周收盘 − 1 | [热力图](figures/tech20_pct_heatmap.png) · [曲面](figures/tech20_pct_surface.png) |
| `3` | 本周收盘 / 3 周前收盘 − 1 | [热力图](figures/tech20_pct3w_heatmap.png) · [曲面](figures/tech20_pct3w_surface.png) |
| `3 avg` | 本周收盘 / 前 3 周平均收盘 − 1 | [热力图](figures/tech20_pct3wavg_heatmap.png) · [曲面](figures/tech20_pct3wavg_surface.png) |

![](figures/tech20_pct3wavg_heatmap.png)

2026 年 4–5 月半导体（MU、INTC、AMD、TXN、QCOM）集体大涨在三种算法里都最显眼；INTC 截至 2026-05-04 的 3 周涨幅达 +82.4%。

## 3. 股票之间的方向一致性 · `03_cross_stock_direction.py`

信号 = 本周收盘 / 前 3 周平均收盘 − 1。两只股票逐周比：同向 +1、反向 −1，取平均（= 同向周占比 × 2 − 1）。按聚类排序，另附同信号的 Pearson 相关作对照。

![](figures/tech20_direction_agreement_heatmap.png)

- 两两平均只有 0.15（约 57% 的周同向），190 对里 38 对为负。
- 两个板块：半导体（AMD、INTC、TXN、MU、QCOM）与软件 / 互联网（ORCL、PLTR、ADBE、CRM、MSFT、AMZN），板块之间大多为负。最同步 ADBE–CRM 0.72，最反向 MU–NFLX −0.52。

其他图：[三维曲面](figures/tech20_direction_agreement_surface.png) · [Pearson 对照](figures/tech20_pearson_corr_heatmap.png)

## 4. 同一只股票的趋势延续性 · `04_persistence.py`

本周涨跌方向 vs 前 3 周涨跌的指数加权平均（权重 4:2:1，越近越重）：同向 +1（延续），反向 −1（反转），取平均。

![](figures/tech20_persistence_table.png)

- 整体五五开：20 只平均 −0.02，48.9% 的周延续。
- 只有 NVDA（−0.35）和 IBM（−0.31）显著，且都是**反转**。49 周的样本中 ±0.3 以内基本是噪音。

逐周图：[tech20_persistence_weekly.png](figures/tech20_persistence_weekly.png)

## 5. 弹簧模型

把股票的上涨看成弹簧拉伸、下跌看成压缩。每周的涨跌推动弹簧，旧位移按半衰期指数松弛（一个长期累积过程）；位移 z 标准化后，势能 U = ½·z²，回弹力方向与位移相反。十年数据由 `05_download_10y.py` 下载。

### 5a. 扣除大盘、预测涨跌方向 · `06_spring_vs_market.py`

- 背景板：股票周收益减去 β × QQQ 收益（β 用过去 52 周估计），再除以自身过去 26 周波动率。
- 概率：P(下周跑赢大盘) = σ(a + b·z)，参数只用 2017–2024 训练期拟合；图中全部是 2024-10 至 2026-10 的**样本外**结果（2080 个“股票·周”）。

![](figures/tech20_spring_probability_vs_actual.png)

- 半衰期 13 周时，拟合出的 b = −0.004，概率只在 49.0%–49.7% 之间变动；r(概率, 实际涨跌) = −0.019（p = 0.37），AUC = 0.488。
- 半衰期从 1 周到 52 周，样本外 r 都在 ±0.02 以内。
- 分股票：只有 NVDA 显著（r = +0.38，p = 0.0001），即相对大盘有回弹，与第 4 节的结果一致。[分股票图](figures/tech20_spring_per_stock.png) · [NVDA 示例](figures/tech20_spring_example_NVDA.png)

### 5b. 不扣大盘、对比下周涨跌幅 · `07_spring_raw_pct.py`

弹簧直接由股票自身周涨跌幅（÷ 自身波动率）推动，拿位移 z 与**下周涨跌幅（%）**算相关。无需拟合参数，使用完整十年（9935 个“股票·周”）。

![](figures/tech20_spring2_vs_pct_change.png)

![](figures/tech20_spring2_corr_table.png)

- 20 只合并：r = −0.007（p = 0.52），噪音范围 ±0.02；半衰期 1–52 周全部在 −0.013 至 0 之间。
- 前 5 年（2017–2021）有很弱的回弹（−0.03 至 −0.04），后 5 年（2021–2026）反而是很弱的惯性（约 +0.01），方向不稳定。
- 单只只有 AVGO 在半衰期 1–13 周显著回弹（约 −0.10 至 −0.11）。不扣大盘时，NVDA 的回弹消失（+0.008）。

## 总结

对这 20 只大盘科技股的周线来说，无论扣不扣大盘、记忆长短如何，“弹簧势能”对下周涨跌（方向或幅度）的预测力都接近于零；少数个股（NVDA 相对大盘、AVGO 自身）的回弹信号值得用更长数据进一步检验。

## 数据说明

`data/` 中的价格来自 Yahoo Finance，仅用于个人研究复现；使用和再分发须遵守 Yahoo 的服务条款。
