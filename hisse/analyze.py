"""Tek hisse analizi — tüm sayılar deterministik hesaplanır."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from .ortak import _pct, _rsi, fmt_num


# ------------------------------------------------------------------ yardımcılar
def _num(x) -> float | None:
    try:
        v = float(x)
        return None if np.isnan(v) or np.isinf(v) else v
    except (TypeError, ValueError):
        return None


def _row(df: pd.DataFrame, *names: str) -> pd.Series:
    """Mali tablodan satır çek (tarihe göre eskiden yeniye)."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.Series(dtype=float)
    for n in names:
        if n in df.index:
            s = pd.to_numeric(df.loc[n], errors="coerce")
            s.index = pd.to_datetime(s.index)
            return s.sort_index().dropna()
    return pd.Series(dtype=float)


def _interp(x: float | None, pts: list[tuple[float, float]]) -> float | None:
    """Parçalı doğrusal puanlama: pts = [(değer, puan), ...] artan değer sırasıyla."""
    if x is None:
        return None
    xs, ys = zip(*pts)
    return float(np.interp(x, xs, ys))


def _avg(*vals) -> float | None:
    v = [x for x in vals if x is not None]
    return round(float(np.mean(v)), 1) if v else None


# ------------------------------------------------------------------ fiyat & trend
def _atr(h: pd.DataFrame, n: int = 14) -> float:
    pc = h["Close"].shift()
    tr = pd.concat([h["High"] - h["Low"], (h["High"] - pc).abs(), (h["Low"] - pc).abs()], axis=1).max(axis=1)
    return float(tr.tail(n).mean())


def _pivots(h: pd.DataFrame, w: int = 5, lookback: int = 250) -> tuple[list, list]:
    x = h.tail(lookback)
    hi, lo = x["High"].values, x["Low"].values
    highs, lows = [], []
    for i in range(w, len(x) - w):
        if hi[i] == hi[i - w:i + w + 1].max():
            highs.append((x.index[i], float(hi[i])))
        if lo[i] == lo[i - w:i + w + 1].min():
            lows.append((x.index[i], float(lo[i])))
    return highs, lows


def _cluster(levels: list[float], tol: float = 0.015) -> list[float]:
    out: list[list[float]] = []
    for v in sorted(levels):
        if out and abs(v / np.mean(out[-1]) - 1) < tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [float(np.mean(c)) for c in out]


def trend_block(h: pd.DataFrame, bench: pd.Series) -> dict:
    c = h["Close"]
    p = float(c.iloc[-1])
    ma = {n: float(c.tail(n).mean()) for n in (20, 50, 200) if len(c) >= n}
    ma200_prev = float(c.iloc[-221:-21].mean()) if len(c) >= 221 else None
    y = c.tail(252)
    lo52, hi52 = float(h["Low"].tail(252).min()), float(h["High"].tail(252).max())
    pos52 = round((p - lo52) / (hi52 - lo52) * 100) if hi52 > lo52 else 50
    rsi = _rsi(c)
    rel = None
    if bench is not None and len(bench) > 64:
        b = bench.reindex(c.index, method="ffill").dropna()
        a = c.reindex(b.index)
        rel = round(_pct(a.iloc[-1], a.iloc[-64]) - _pct(b.iloc[-1], b.iloc[-64]), 1)

    puan, detay = 0, []
    def add(ok, pts, txt):
        nonlocal puan
        if ok:
            puan += pts
        detay.append({"ok": bool(ok), "puan": pts, "metin": txt})
    add(p > ma.get(20, 1e18), 10, "Fiyat 20 günlük ortalamanın üstünde")
    add(p > ma.get(50, 1e18), 15, "Fiyat 50 günlük ortalamanın üstünde")
    add(p > ma.get(200, 1e18), 15, "Fiyat 200 günlük ortalamanın üstünde")
    add(ma.get(50, 0) > ma.get(200, 1e18), 15, "50G > 200G (yükseliş dizilimi)")
    add(ma200_prev is not None and ma.get(200, 0) > ma200_prev, 10, "200G ortalama yukarı eğimli")
    add(pos52 >= 75, 10, f"52 haftalık bandın üst çeyreğinde (%{pos52})")
    add(rsi is not None and 50 <= rsi < 70, 10, f"RSI sağlıklı momentum bölgesinde (50–70) · {fmt_num(rsi, 0)}")
    add(rel is not None and rel > 0, 15, f"Son 3 ayda SPY'den iyi ({'+' if (rel or 0) >= 0 else ''}{fmt_num(rel, 1)} puan)")

    uzama = _pct(p, ma[200]) if 200 in ma else None
    if p > ma.get(50, 1e18) > ma.get(200, 1e18):
        asama = "Güçlü yükseliş"
    elif p > ma.get(200, 1e18):
        asama = "Yükseliş (düzeltmede)"
    elif p > ma.get(50, 1e18):
        asama = "Toparlanma denemesi"
    else:
        asama = "Düşüş"
    uyarilar = []
    if uzama is not None and uzama > 35:
        uyarilar.append(f"Fiyat 200G'nin %{fmt_num(uzama, 0)} üstünde — trend olgun/uzamış")
    if rsi is not None and rsi >= 70:
        uyarilar.append(f"RSI {fmt_num(rsi, 0)} — aşırı alım bölgesi")

    # seviyeler
    highs, lows = _pivots(h)
    sup = [v for v in _cluster([v for _, v in lows]) if v < p]
    res = [v for v in _cluster([v for _, v in highs]) if v > p]
    seviyeler = ([{"fiyat": v, "tur": "destek", "ad": "Salınım dibi"} for v in sorted(sup, reverse=True)[:3]] +
                 [{"fiyat": v, "tur": "direnc", "ad": "Salınım tepesi"} for v in sorted(res)[:3]])
    for n in (50, 200):
        if n in ma:
            seviyeler.append({"fiyat": ma[n], "tur": "destek" if ma[n] < p else "direnc", "ad": f"{n}G ortalama"})
    seviyeler.append({"fiyat": hi52, "tur": "direnc" if hi52 > p else "destek", "ad": "52H zirve"})
    for s in seviyeler:
        s["mesafe"] = _pct(s["fiyat"], p)
    seviyeler.sort(key=lambda s: -s["fiyat"])

    atr = _atr(h)
    chandelier = float(h["High"].tail(22).max()) - 3 * atr
    son_dip = next((v for d, v in reversed(lows) if v < p), None)
    cikis = [
        {"ad": "ATR takip stopu (Chandelier)", "fiyat": chandelier,
         "aciklama": "Son 22 günün zirvesi − 3 × ATR(14). Kapanış altına inerse kısa vadeli trend bozulmuş sayılır."},
        {"ad": "50 günlük ortalama kuralı", "fiyat": ma.get(50),
         "aciklama": "İki gün üst üste 50G altında kapanış: orta vadeli momentum kaybı."},
        {"ad": "Yapı bozulma seviyesi", "fiyat": son_dip,
         "aciklama": "Son belirgin salınım dibi. Altına iniş, yükselen dip yapısını bozar."},
        {"ad": "200 günlük ortalama", "fiyat": ma.get(200),
         "aciklama": "Uzun vadeli trend çizgisi. Altında kalıcılık, uzun vadeli tezin yeniden sorgulanması demek."},
    ]
    for x in cikis:
        x["mesafe"] = _pct(x["fiyat"], p) if x["fiyat"] else None

    etiket = ("Güçlü" if puan >= 75 else "Olumlu" if puan >= 55 else "Kararsız" if puan >= 40 else "Zayıf")
    ch = {"Fiyat": c, "20G": c.rolling(20).mean(), "50G": c.rolling(50).mean(), "200G": c.rolling(200).mean()}
    seriler = {k: [None if pd.isna(v) else round(float(v), 2) for v in s.tail(120)] for k, s in ch.items()}
    return {"fiyat": p, "gun": _pct(c.iloc[-1], c.iloc[-2]), "ma": ma, "rsi": rsi, "rel_3a": rel,
            "lo52": lo52, "hi52": hi52, "pos52": pos52, "skor": puan, "etiket": etiket, "detay": detay,
            "asama": asama, "uyarilar": uyarilar, "seviyeler": seviyeler, "cikis": cikis, "atr": atr,
            "seriler": seriler, "tarih": c.index[-1].strftime("%Y-%m-%d"),
            "ilk_tarih": c.index[-120].strftime("%d.%m") if len(c) >= 120 else "",
            "son_tarih": c.index[-1].strftime("%d.%m")}


# ------------------------------------------------------------------ mali tablolar
def financials(d: dict) -> dict:
    qi, qc, ai = d.get("q_income"), d.get("q_cash"), d.get("a_income")
    rev, gp = _row(qi, "Total Revenue", "Operating Revenue"), _row(qi, "Gross Profit")
    op, ni = _row(qi, "Operating Income"), _row(qi, "Net Income", "Net Income Common Stockholders")
    eps = _row(qi, "Diluted EPS", "Basic EPS")
    fcf = _row(qc, "Free Cash Flow")
    rows = []
    for dt in rev.index[-8:]:
        r = rev.get(dt)
        prev = rev[rev.index <= dt - pd.Timedelta(days=330)]
        yoy = _pct(r, prev.iloc[-1]) if len(prev) and prev.iloc[-1] else None
        rows.append({"donem": dt.strftime("%Y-%m"), "ciro": r, "ciro_yoy": yoy,
                     "brut_marj": (gp.get(dt) / r * 100) if gp.get(dt) is not None and r else None,
                     "faaliyet_marj": (op.get(dt) / r * 100) if op.get(dt) is not None and r else None,
                     "net_kar": ni.get(dt), "eps": eps.get(dt), "fcf": fcf.get(dt)})
    arev, ani = _row(ai, "Total Revenue", "Operating Revenue"), _row(ai, "Net Income")
    yillik = [{"yil": dt.year, "ciro": arev.get(dt), "net_kar": ani.get(dt),
               "net_marj": (ani.get(dt) / arev.get(dt) * 100) if ani.get(dt) is not None and arev.get(dt) else None}
              for dt in arev.index[-4:]]
    cagr = None
    if len(arev) >= 2 and arev.iloc[0] > 0:
        n = (arev.index[-1] - arev.index[0]).days / 365.25
        cagr = ((arev.iloc[-1] / arev.iloc[0]) ** (1 / n) - 1) * 100 if n > 0 else None
    fcf_ttm = float(fcf.tail(4).sum()) if len(fcf) >= 4 else None
    return {"ceyrekler": rows, "yillik": yillik, "ciro_cagr": cagr, "fcf_ttm": fcf_ttm,
            "ciro_ttm": float(rev.tail(4).sum()) if len(rev) >= 4 else None}


# ------------------------------------------------------------------ adil değer
def fair_value(d: dict, fin: dict, cfg: dict, price: float, growth_pct: float | None) -> dict:
    info, dv = d.get("info", {}), cfg.get("degerleme", {})
    methods = []
    feps = _num(info.get("forwardEps"))
    if feps and feps > 0 and growth_pct is not None:
        pe = min(max(dv.get("hedef_peg", 1.5) * growth_pct, dv.get("fk_min", 12)), dv.get("fk_max", 45))
        methods.append({"ad": "F/K–büyüme", "deger": feps * pe,
                        "aciklama": f"İleri EPS {fmt_num(feps, 2)} × hedef F/K {fmt_num(pe, 1)} "
                                    f"(= PEG {dv.get('hedef_peg', 1.5)} × beklenen büyüme %{fmt_num(growth_pct, 1)}, {dv.get('fk_min', 12)}–{dv.get('fk_max', 45)} aralığında)"})
    fcf = fin.get("fcf_ttm") or _num(info.get("freeCashflow"))
    shares = _num(info.get("sharesOutstanding"))
    if fcf and fcf > 0 and shares:
        r, tg = dv.get("iskonto", 0.10), dv.get("terminal_buyume", 0.03)
        g1 = min(max((growth_pct or 10) / 100, 0.0), dv.get("dcf_max_buyume", 0.30))
        pv, f = 0.0, fcf
        for yr in range(1, 11):
            g = g1 + (tg - g1) * (yr - 1) / 9  # 10 yılda terminal büyümeye iner
            f *= 1 + g
            pv += f / (1 + r) ** yr
        tv = f * (1 + tg) / (r - tg) / (1 + r) ** 10
        eq = pv + tv + (_num(info.get("totalCash")) or 0) - (_num(info.get("totalDebt")) or 0)
        methods.append({"ad": "İndirgenmiş nakit akışı", "deger": eq / shares,
                        "aciklama": f"Serbest nakit akışı (12 ay) {fmt_num(fcf / 1e9, 1)} mr $ · ilk yıl büyüme %{fmt_num(g1 * 100, 0)}, "
                                    f"10 yılda %{fmt_num(tg * 100, 0)}'e iner · iskonto %{fmt_num(r * 100, 0)}"})
    tgt = d.get("targets") or {}
    at = _num(tgt.get("median")) or _num(tgt.get("mean")) or _num(info.get("targetMedianPrice")) or _num(info.get("targetMeanPrice"))
    if at:
        methods.append({"ad": "Analist medyan hedefi", "deger": at,
                        "aciklama": f"{info.get('numberOfAnalystOpinions', '—')} analistin 12 aylık hedef fiyat medyanı"})
    if not methods:
        return {"yontemler": [], "deger": None}
    vals = np.array([m["deger"] for m in methods])
    blend = float(vals.mean())
    cv = float(vals.std() / blend) if blend else 1
    guven = int(max(0, min(100, 100 - cv * 150 - (3 - len(methods)) * 15)))
    for m in methods:
        m["fark"] = _pct(m["deger"], price)
    return {"yontemler": methods, "deger": blend, "fark": _pct(blend, price), "guven": guven}


# ------------------------------------------------------------------ analist / insider / bilanço / opsiyon
def analysts(d: dict, price: float) -> dict:
    rs = d.get("rec_summary")
    dag = None
    if isinstance(rs, pd.DataFrame) and not rs.empty:
        r = rs[rs["period"] == "0m"].iloc[0] if "period" in rs.columns and (rs["period"] == "0m").any() else rs.iloc[0]
        dag = {k: int(r.get(k, 0) or 0) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")}
    tgt = d.get("targets") or {}
    info = d.get("info", {})
    hedef = {k: _num(tgt.get(k)) or _num(info.get(f"target{k.capitalize()}Price")) for k in ("low", "mean", "median", "high")}
    ud = d.get("updown")
    son = []
    if isinstance(ud, pd.DataFrame) and not ud.empty:
        x = ud.copy()
        x.index = pd.to_datetime(x.index).tz_localize(None) if x.index.tz is not None else pd.to_datetime(x.index)
        x = x[x.index >= pd.Timestamp(date.today() - timedelta(days=90))].sort_index(ascending=False)
        for dt, r in x.head(8).iterrows():
            son.append({"tarih": dt.strftime("%Y-%m-%d"), "kurum": r.get("Firm"), "aksiyon": r.get("Action"),
                        "eski": r.get("FromGrade"), "yeni": r.get("ToGrade")})
        ups = int((x.get("Action") == "up").sum()) if "Action" in x else 0
        downs = int((x.get("Action") == "down").sum()) if "Action" in x else 0
    else:
        ups = downs = 0
    toplam = sum(dag.values()) if dag else 0
    al = (dag["strongBuy"] + dag["buy"]) if dag else 0
    return {"dagilim": dag, "toplam": toplam, "al_orani": round(al / toplam * 100) if toplam else None,
            "hedef": hedef, "hedef_fark": {k: (_pct(v, price) if v else None) for k, v in hedef.items()},
            "son": son, "yukseltme": ups, "dusurme": downs}


def insiders(d: dict) -> dict:
    df = d.get("insider")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"var": False}
    x = df.copy()
    col = "Start Date" if "Start Date" in x.columns else None
    if col:
        x[col] = pd.to_datetime(x[col], errors="coerce")
        x = x[x[col] >= pd.Timestamp(date.today() - timedelta(days=90))]
    text = x.get("Text", pd.Series([""] * len(x), index=x.index)).fillna("").str.lower()
    tr = x.get("Transaction", pd.Series([""] * len(x), index=x.index)).fillna("").str.lower()
    is_buy = text.str.contains("purchase") | tr.str.contains("purchase|buy")
    is_sell = text.str.contains("sale") | tr.str.contains("sale|sell")
    val = pd.to_numeric(x.get("Value"), errors="coerce").fillna(0)
    rows = []
    for i, r in x.head(10).iterrows():
        rows.append({"tarih": r[col].strftime("%Y-%m-%d") if col and pd.notna(r[col]) else "",
                     "kisi": r.get("Insider"), "pozisyon": r.get("Position"),
                     "islem": "Alım" if is_buy[i] else ("Satış" if is_sell[i] else (r.get("Text") or "Diğer")),
                     "deger": _num(r.get("Value")), "adet": _num(r.get("Shares"))})
    return {"var": True, "alim_sayi": int(is_buy.sum()), "alim_deger": float(val[is_buy].sum()),
            "satis_sayi": int(is_sell.sum()), "satis_deger": float(val[is_sell].sum()), "islemler": rows}


def earnings(d: dict, h: pd.DataFrame) -> dict:
    cal, ed = d.get("calendar") or {}, d.get("earnings_dates")
    nxt = None
    if isinstance(cal, dict) and cal.get("Earnings Date"):
        v = cal["Earnings Date"]
        nxt = pd.Timestamp(v[0] if isinstance(v, (list, tuple)) else v).date()
    hist_rows = []
    if isinstance(ed, pd.DataFrame) and not ed.empty:
        e = ed.copy()
        e.index = pd.to_datetime(e.index).tz_localize(None) if getattr(e.index, "tz", None) else pd.to_datetime(e.index)
        fut = e[e.index.normalize() >= pd.Timestamp(date.today())]
        if nxt is None and len(fut):
            nxt = fut.index.min().date()
        past = e[e.get("Reported EPS").notna()] if "Reported EPS" in e else e.iloc[0:0]
        c = h["Close"]
        for dt, r in past.sort_index(ascending=False).head(8).iterrows():
            d0 = dt.normalize()
            before = c[c.index < d0] if dt.hour < 12 else c[c.index <= d0]
            after = c[c.index >= d0] if dt.hour < 12 else c[c.index > d0]
            tepki = _pct(after.iloc[0], before.iloc[-1]) if len(before) and len(after) else None
            hist_rows.append({"tarih": dt.strftime("%Y-%m-%d"), "beklenti": _num(r.get("EPS Estimate")),
                              "gercek": _num(r.get("Reported EPS")), "surpriz": _num(r.get("Surprise(%)")),
                              "tepki": tepki})
    kalan = int(np.busday_count(date.today(), nxt)) if nxt and nxt >= date.today() else None
    beat = [r for r in hist_rows if r["surpriz"] is not None]
    tepkiler = [abs(r["tepki"]) for r in hist_rows if r["tepki"] is not None]
    return {"sonraki": nxt.isoformat() if nxt else None, "is_gunu": kalan, "gecmis": hist_rows,
            "tutturma": f"{sum(r['surpriz'] > 0 for r in beat)}/{len(beat)}" if beat else None,
            "ort_tepki": round(float(np.mean(tepkiler)), 1) if tepkiler else None}


def _mid(df: pd.DataFrame, strike: float) -> float | None:
    r = df.iloc[(df["strike"] - strike).abs().argsort()[:1]]
    if r.empty:
        return None
    r = r.iloc[0]
    bid, ask, last = _num(r.get("bid")), _num(r.get("ask")), _num(r.get("lastPrice"))
    return (bid + ask) / 2 if bid and ask else last


def options_map(d: dict, price: float, earn_date: str | None) -> dict:
    ex = d.get("options") or []
    if not ex:
        return {"var": False}
    calls = pd.concat([e["calls"] for e in ex[:3]]).groupby("strike")["openInterest"].sum()
    puts = pd.concat([e["puts"] for e in ex[:3]]).groupby("strike")["openInterest"].sum()
    band = lambda s: s[(s.index > price * 0.8) & (s.index < price * 1.2)].fillna(0)
    cb, pb = band(calls), band(puts)
    call_wall = float(cb[cb.index > price].idxmax()) if (cb.index > price).any() and cb[cb.index > price].max() > 0 else None
    put_wall = float(pb[pb.index < price].idxmax()) if (pb.index < price).any() and pb[pb.index < price].max() > 0 else None
    pcr = float(puts.sum() / calls.sum()) if calls.sum() else None
    # max pain (en yakın vade)
    e0 = ex[0]
    strikes = sorted(set(e0["calls"]["strike"]) | set(e0["puts"]["strike"]))
    c0 = e0["calls"].set_index("strike")["openInterest"].fillna(0)
    p0 = e0["puts"].set_index("strike")["openInterest"].fillna(0)
    ck, pk = c0.index.to_numpy(dtype=float), p0.index.to_numpy(dtype=float)
    pain = {k: float((np.clip(k - ck, 0, None) * c0.to_numpy()).sum() + (np.clip(pk - k, 0, None) * p0.to_numpy()).sum())
            for k in strikes}
    max_pain = min(pain, key=pain.get) if pain else None
    # beklenen hareket: bilanço sonrası ilk vade (yoksa en yakın vade) ATM straddle
    hedef_vade = ex[0]
    if earn_date:
        after = [e for e in ex if e["vade"] >= earn_date]
        if after:
            hedef_vade = after[0]
    cm, pm = _mid(hedef_vade["calls"], price), _mid(hedef_vade["puts"], price)
    move = round((cm + pm) / price * 100, 1) if cm and pm else None
    strikes_all = sorted(set(cb.index) | set(pb.index))
    step = max(1, len(strikes_all) // 24)
    bars = [{"strike": k, "call": float(cb.get(k, 0)), "put": float(pb.get(k, 0))} for k in strikes_all[::step]]
    return {"var": True, "vadeler": [e["vade"] for e in ex[:3]], "call_duvar": call_wall, "put_duvar": put_wall,
            "pcr": round(pcr, 2) if pcr else None, "max_pain": max_pain, "max_pain_vade": e0["vade"],
            "beklenen_hareket": move, "beklenen_vade": hedef_vade["vade"], "bars": bars}


# ------------------------------------------------------------------ karne
def scorecard(cfg: dict, m: dict, fv: dict, tr: dict, an: dict) -> dict:
    w = cfg.get("karne_agirliklari", {"Büyüme": 20, "Kârlılık": 20, "Bilanço": 10, "Değerleme": 20, "Trend": 15, "Beklenti": 15})
    g = lambda x: _interp(x, [(-10, 0), (0, 2), (5, 4), (10, 6), (20, 8), (30, 10)])
    parts = {
        "Büyüme": _avg(g(m["ciro_buyume"]), g(m["eps_buyume"])),
        "Kârlılık": _avg(_interp(m["brut_marj"], [(20, 2), (40, 5), (60, 8), (70, 10)]),
                         _interp(m["faaliyet_marj"], [(0, 1), (10, 4), (20, 7), (30, 10)]),
                         _interp(m["fcf_marj"], [(0, 1), (10, 5), (20, 8), (30, 10)])),
        "Bilanço": (10.0 if m["net_nakit"] is not None and m["net_nakit"] >= 0 else
                    _interp(m["borc_favok"], [(0, 9), (1, 8), (2, 6), (3, 4), (5, 1)])),
        "Değerleme": _avg(_interp(-(m["peg"] or 0) if m["peg"] and m["peg"] > 0 else None, [(-4, 1), (-3, 3), (-2, 6), (-1.5, 8), (-1, 10)]),
                          _interp(fv.get("fark"), [(-30, 1), (-10, 4), (0, 6), (15, 8), (30, 10)])),
        "Trend": round(tr["skor"] / 10, 1),
        "Beklenti": _avg(_interp(an["hedef_fark"].get("median") or an["hedef_fark"].get("mean"), [(-10, 1), (0, 3), (10, 6), (25, 8), (40, 10)]),
                         (an["al_orani"] / 10) if an["al_orani"] is not None else None),
    }
    parts = {k: (round(v, 1) if v is not None else None) for k, v in parts.items()}
    tw = sum(w[k] for k, v in parts.items() if v is not None)
    skor = round(sum(v * w[k] for k, v in parts.items() if v is not None) / tw * 10) if tw else None
    return {"skor": skor, "ayaklar": parts, "agirlik": w}


# ------------------------------------------------------------------ tez kuralları
def thesis(tez: dict | None, m: dict) -> dict:
    if not tez:
        return {"var": False}
    sonuc = []
    for k in tez.get("kurallar", []) or []:
        v = m.get(k["metrik"])
        if v is None:
            sonuc.append({**k, "mevcut": None, "durum": "veri yok"})
            continue
        bozuk = (v < k["deger"]) if k["op"] == "<" else (v > k["deger"])
        sonuc.append({**k, "mevcut": v, "durum": "UYARI" if bozuk else "sağlam"})
    return {"var": True, **tez, "kural_sonuc": sonuc,
            "saglam": all(r["durum"] != "UYARI" for r in sonuc)}


# ------------------------------------------------------------------ ana giriş
def analyze_stock(d: dict, cfg: dict, tez: dict | None) -> dict:
    info, h = d.get("info", {}), d["hist"]
    tr = trend_block(h, d.get("bench"))
    price = tr["fiyat"]
    fin = financials(d)

    ge = d.get("growth_est")
    g_next = None
    if isinstance(ge, pd.DataFrame) and not ge.empty:
        for idx in ("+1y", "0y"):
            if idx in ge.index:
                col = "stockTrend" if "stockTrend" in ge.columns else ge.columns[0]
                g_next = _num(ge.loc[idx, col])
                if g_next is not None:
                    g_next *= 100
                    break
    eg = _num(info.get("earningsQuarterlyGrowth")) or _num(info.get("earningsGrowth"))
    growth_for_val = g_next if g_next is not None else (min(eg * 100, 50) if eg else None)

    rev_ttm = fin.get("ciro_ttm") or _num(info.get("totalRevenue"))
    fcf = fin.get("fcf_ttm") or _num(info.get("freeCashflow"))
    cash, debt, ebitda = _num(info.get("totalCash")), _num(info.get("totalDebt")), _num(info.get("ebitda"))
    fpe = _num(info.get("forwardPE"))
    peg = _num(info.get("trailingPegRatio")) or _num(info.get("pegRatio"))
    if peg is None and fpe and growth_for_val and growth_for_val > 0:
        peg = fpe / growth_for_val
    m = {
        "piyasa_degeri": _num(info.get("marketCap")),
        "ciro_buyume": (_num(info.get("revenueGrowth")) or 0) * 100 if info.get("revenueGrowth") is not None else
                       (fin["ceyrekler"][-1]["ciro_yoy"] if fin["ceyrekler"] else None),
        "eps_buyume": eg * 100 if eg is not None else None,
        "fk": _num(info.get("trailingPE")), "fk_ileri": fpe, "peg": peg,
        "fs": _num(info.get("priceToSalesTrailing12Months")),
        "brut_marj": (_num(info.get("grossMargins")) or 0) * 100 if info.get("grossMargins") is not None else None,
        "faaliyet_marj": (_num(info.get("operatingMargins")) or 0) * 100 if info.get("operatingMargins") is not None else None,
        "net_marj": (_num(info.get("profitMargins")) or 0) * 100 if info.get("profitMargins") is not None else None,
        "roe": (_num(info.get("returnOnEquity")) or 0) * 100 if info.get("returnOnEquity") is not None else None,
        "fcf_marj": (fcf / rev_ttm * 100) if fcf and rev_ttm else None,
        "net_nakit": (cash - debt) if cash is not None and debt is not None else None,
        "borc_favok": ((debt - (cash or 0)) / ebitda) if debt and ebitda and ebitda > 0 else None,
        "beta": _num(info.get("beta")), "rsi": tr["rsi"], "trend_skoru": tr["skor"],
        "zirveden": _pct(price, tr["hi52"]), "beklenen_buyume": growth_for_val,
        "aciga_satis": (_num(info.get("shortPercentOfFloat")) or 0) * 100 if info.get("shortPercentOfFloat") is not None else None,
        "kurumsal": (_num(info.get("heldPercentInstitutions")) or 0) * 100 if info.get("heldPercentInstitutions") is not None else None,
    }
    fv = fair_value(d, fin, cfg, price, growth_for_val)
    an = analysts(d, price)
    er = earnings(d, h)
    op = options_map(d, price, er["sonraki"])
    sc = scorecard(cfg, m, fv, tr, an)
    th = thesis(tez, {**m, "adil_deger_fark": fv.get("fark"), "karne": sc["skor"]})
    maliyet = _num((tez or {}).get("maliyet"))
    return {
        "sembol": d["sembol"], "alindi": d["alindi"], "ad": info.get("longName") or info.get("shortName") or d["sembol"],
        "borsa": info.get("exchange"), "sektor": info.get("sector"), "endustri": info.get("industry"),
        "ozet_is": (info.get("longBusinessSummary") or "")[:700], "fiyat": price, "gun": tr["gun"],
        "metrikler": m, "trend": tr, "finans": fin, "adil": fv, "analist": an, "insider": insiders(d),
        "bilanco": er, "opsiyon": op, "karne": sc, "tez": th,
        "pozisyon": {"maliyet": maliyet, "kz": _pct(price, maliyet) if maliyet else None,
                     "adet": _num((tez or {}).get("adet"))},
    }
