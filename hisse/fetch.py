"""Tek hisse için veri çekme (Yahoo Finance / yfinance).

Her bölüm ayrı try/except içinde: bir veri gelmezse sadece o bölüm boş kalır.
Sonuç düz bir sözlüktür; test için pickle ile diske yazılıp okunabilir.
"""
from __future__ import annotations

import pickle
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


def _safe(fn, default=None):
    try:
        v = fn()
        return default if v is None else v
    except Exception as e:  # veri kaynağı değişebilir; rapor yine üretilsin
        print(f"    · atlandı: {getattr(fn, '__name__', 'veri')} ({type(e).__name__})")
        return default


def _options(t, price: float, max_days: int = 60, max_exp: int = 4) -> list[dict]:
    out = []
    exps = list(getattr(t, "options", []) or [])
    today = date.today()
    for e in exps:
        d = datetime.strptime(e, "%Y-%m-%d").date()
        if d < today or (d - today).days > max_days:
            continue
        ch = t.option_chain(e)
        keep = ["strike", "openInterest", "volume", "impliedVolatility", "lastPrice", "bid", "ask"]
        calls = ch.calls[[c for c in keep if c in ch.calls.columns]].copy()
        puts = ch.puts[[c for c in keep if c in ch.puts.columns]].copy()
        out.append({"vade": e, "calls": calls, "puts": puts})
        if len(out) >= max_exp:
            break
    return out


def fetch_stock(symbol: str, benchmark: str = "SPY") -> dict:
    import yfinance as yf  # type: ignore

    t = yf.Ticker(symbol)
    hist = _safe(lambda: t.history(period="2y", auto_adjust=False), pd.DataFrame())
    if hist is None or hist.empty:
        raise RuntimeError(f"{symbol} için fiyat verisi alınamadı (sembol doğru mu?)")
    hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
    bench = _safe(lambda: yf.Ticker(benchmark).history(period="2y")["Close"], pd.Series(dtype=float))
    if len(bench):
        bench.index = pd.to_datetime(bench.index).tz_localize(None).normalize()
    price = float(hist["Close"].iloc[-1])
    return {
        "sembol": symbol.upper(),
        "alindi": datetime.now().isoformat(timespec="minutes"),
        "info": _safe(lambda: dict(t.info), {}),
        "hist": hist[["Open", "High", "Low", "Close", "Volume"]],
        "bench": bench,
        "q_income": _safe(lambda: t.quarterly_income_stmt, pd.DataFrame()),
        "a_income": _safe(lambda: t.income_stmt, pd.DataFrame()),
        "q_cash": _safe(lambda: t.quarterly_cashflow, pd.DataFrame()),
        "a_cash": _safe(lambda: t.cashflow, pd.DataFrame()),
        "q_balance": _safe(lambda: t.quarterly_balance_sheet, pd.DataFrame()),
        "calendar": _safe(lambda: t.calendar, {}),
        "earnings_dates": _safe(lambda: t.get_earnings_dates(limit=12), pd.DataFrame()),
        "rec_summary": _safe(lambda: t.recommendations_summary, pd.DataFrame()),
        "updown": _safe(lambda: t.upgrades_downgrades, pd.DataFrame()),
        "targets": _safe(lambda: t.analyst_price_targets, {}),
        "growth_est": _safe(lambda: t.growth_estimates, pd.DataFrame()),
        "eps_est": _safe(lambda: t.earnings_estimate, pd.DataFrame()),
        "insider": _safe(lambda: t.insider_transactions, pd.DataFrame()),
        "options": _safe(lambda: _options(t, price), []),
    }


def save(d: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(d))


def load(path: Path) -> dict:
    return pickle.loads(path.read_bytes())
