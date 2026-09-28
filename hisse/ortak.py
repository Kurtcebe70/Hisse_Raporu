"""Ortak yardımcılar: Türkçe sayı biçimi, yüzde, RSI."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi(s: pd.Series, n: int = 14) -> float | None:
    if len(s) < n + 1:
        return None
    d = s.diff().dropna()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up.iloc[-1] / dn.iloc[-1] if dn.iloc[-1] else np.inf
    return round(float(100 - 100 / (1 + rs)), 1)


def _pct(a: float, b: float) -> float:
    return round((a / b - 1) * 100, 2) if b else 0.0


def fmt_num(x: float | None, nd: int | None = None) -> str:
    if x is None:
        return "—"
    if nd is None and isinstance(x, int):
        nd = 0
    if nd is None:
        ax = abs(x)
        nd = 0 if ax >= 10000 else (1 if ax >= 1000 else 2)
    s = f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s.replace("-", "−")

