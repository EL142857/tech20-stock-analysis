"""Shared data paths, ticker list, loaders, tests and regression helpers."""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, FIG, RES = ROOT / "data", ROOT / "figures", ROOT / "results"

# internet, software, semiconductors, hardware/networking, IT services
TICKERS = """AAPL MSFT GOOGL AMZN META TSLA NFLX EBAY AKAM VRSN
ORCL IBM CRM ADBE INTU NOW ADSK WDAY PANW FTNT SNPS CDNS PTC TYL FICO
NVDA AMD INTC AVGO QCOM TXN MU AMAT LRCX KLAC ADI MCHP NXPI MRVL ON SWKS QRVO TER MPWR ENTG
CSCO ANET FFIV HPQ NTAP STX WDC SMCI APH TEL GLW KEYS ZBRA TRMB CDW
ACN CTSH IT EPAM""".split()


def load_returns():
    """Daily % change vs. the previous close, as fractions: (stocks, QQQ), first day dropped."""
    px = pd.read_csv(DATA / "daily_close.csv", index_col=0, parse_dates=True)
    r = px.pct_change().iloc[1:]
    return r.drop(columns="QQQ"), r["QQQ"]


def newey_west_t(x, lags=5):
    """t-stat of mean(x) with Newey-West (Bartlett) standard error."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n, e = len(x), x - x.mean()
    s = e @ e / n
    for k in range(1, lags + 1):
        s += 2 * (1 - k / (lags + 1)) * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(s / n)


def robust_t(Y, X):
    """t[i, j] for regressing Y[:, i] on X[:, j] (White SE, beta~0 approximation)."""
    Y = Y - Y.mean(0)
    X = X - X.mean(0)
    return (Y.T @ X) / np.sqrt((Y**2).T @ (X**2))


def corr(Y, X):
    Y = (Y - Y.mean(0)) / Y.std(0)
    X = (X - X.mean(0)) / X.std(0)
    return Y.T @ X / len(Y)


def bh_count(p, q=0.05):
    p = np.sort(p.ravel())
    ok = p <= q * np.arange(1, len(p) + 1) / len(p)
    return int(ok.nonzero()[0].max() + 1) if ok.any() else 0


def ridge_path(Xtr, Ytr, Xte, alphas):
    """Predictions on Xte for each ridge penalty (features standardized on train)."""
    mu, sd = Xtr.mean(0), Xtr.std(0)
    Xs, Xt = (Xtr - mu) / sd, (Xte - mu) / sd
    ym = Ytr.mean(0)
    U, s, Vt = np.linalg.svd(Xs, full_matrices=False)
    UtY = U.T @ (Ytr - ym)
    XtV = Xt @ Vt.T
    return [ym + XtV @ ((s / (s**2 + a))[:, None] * UtY) for a in alphas]


def ridge_cv(Xtr, Ytr, Xte, n_val=252):
    """Pick a penalty per target on the last year of the window, then refit on all of it."""
    alphas = len(Xtr) * np.array([0, 1e-2, 1e-1, 1, 10, 100, 1e3, 1e4])
    val = ridge_path(Xtr[:-n_val], Ytr[:-n_val], Xtr[-n_val:], alphas)
    mse = np.array([((Ytr[-n_val:] - p) ** 2).mean(0) for p in val])
    best = mse.argmin(0)
    full = ridge_path(Xtr, Ytr, Xte, alphas)
    return np.choose(best, full), alphas[best] / len(Xtr)


def pcr(Xtr, Ytr, Xte, k=5):
    mu, sd = Xtr.mean(0), Xtr.std(0)
    Xs, Xt = (Xtr - mu) / sd, (Xte - mu) / sd
    _, _, Vt = np.linalg.svd(Xs, full_matrices=False)
    Ztr, Zte = Xs @ Vt[:k].T, Xt @ Vt[:k].T
    ym = Ytr.mean(0)
    B = np.linalg.lstsq(Ztr, Ytr - ym, rcond=None)[0]
    return ym + Zte @ B


def ols(Xtr, Ytr, Xte):
    Z = np.column_stack([np.ones(len(Xtr)), Xtr])
    B = np.linalg.lstsq(Z, Ytr, rcond=None)[0]
    return np.column_stack([np.ones(len(Xte)), Xte]) @ B, Z @ B


def per_stock_ols(xtr, Ytr, xte):
    """Separate one-regressor OLS for each stock; x columns line up with Y columns."""
    xc, yc = xtr - xtr.mean(0), Ytr - Ytr.mean(0)
    b = (xc * yc).sum(0) / (xc**2).sum(0)
    return Ytr.mean(0) + (xte - xtr.mean(0)) * b


def long_short(P, y, n, cost_bp=5, intraday=False):
    """Each day: long the n highest predictions, short the n lowest, equal weight.

    intraday=True: positions are opened and closed within the day, so every
    day pays to enter and to exit.
    """
    rank = P.argsort(1)
    W = np.zeros_like(P)
    rows = np.arange(len(P))[:, None]
    W[rows, rank[:, -n:]] = 1 / n
    W[rows, rank[:, :n]] = -1 / n
    gross = (W * y).sum(1)
    turnover = (2 * np.abs(W).sum(1) if intraday
                else np.abs(np.diff(W, axis=0, prepend=0)).sum(1))
    net = gross - turnover * cost_bp / 1e4
    ann = lambda x: x.mean() / x.std() * np.sqrt(252)
    return gross, net, ann(gross), ann(net), turnover.mean()
