"""HTML üretimi (Jinja2) ve SVG grafikler."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .ortak import fmt_num

TR_MONTHS = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']

LINE_COLORS = {'Fiyat': 'var(--ink)', '10G': 'var(--c1)', '20G': 'var(--c1)', '21G': 'var(--c2)', '50G': 'var(--c3)', '200G': 'var(--c4)'}


def line_chart_svg(seriler: dict, w: int = 640, h: int = 200) -> str:
    """Fiyat + hareketli ortalamalar. 200G görünür aralığın çok dışındaysa ölçeği bozmasın diye kırpılır."""
    price = [v for v in seriler["Fiyat"] if v is not None]
    lo, hi = min(price), max(price)
    pad = (hi - lo) * 0.25 or 1
    lo, hi = lo - pad, hi + pad
    for k, vals in seriler.items():
        vv = [v for v in vals if v is not None]
        if k != "Fiyat" and vv and min(vv) >= lo - pad * 2 and max(vv) <= hi + pad * 2:
            lo, hi = min(lo, min(vv)), max(hi, max(vv))
    rng = (hi - lo) or 1
    n = len(price)
    step = (w - 44) / max(n - 1, 1)
    y = lambda v: 8 + (hi - v) / rng * (h - 30)
    parts = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Fiyat ve hareketli ortalamalar">']
    for frac in (0, 0.5, 1):
        val = hi - frac * rng
        yy = y(val)
        parts.append(f'<line x1="40" x2="{w}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="var(--line)" stroke-dasharray="3 4"/>'
                     f'<text x="0" y="{yy + 4:.1f}" class="ax">{fmt_num(val, 0)}</text>')
    for k in ("200G", "50G", "21G", "20G", "10G", "Fiyat"):
        vals = seriler.get(k) or []
        pts = [(40 + i * step, y(v)) for i, v in enumerate(vals) if v is not None and lo <= v <= hi]
        if len(pts) < 2:
            continue
        d = " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
        sw = 2.2 if k == "Fiyat" else 1.4
        parts.append(f'<polyline points="{d}" fill="none" stroke="{LINE_COLORS[k]}" stroke-width="{sw}" '
                     f'stroke-linejoin="round" stroke-linecap="round"/>')
    last = price[-1]
    parts.append(f'<circle cx="{40 + (n - 1) * step:.1f}" cy="{y(last):.1f}" r="3.5" fill="var(--ink)"/>')
    parts.append("</svg>")
    return "".join(parts)


def oi_svg(bars: list[dict], price: float, w: int = 520) -> str:
    """Opsiyon açık pozisyon haritası: solda put, sağda call, satırlar kullanım fiyatı."""
    if not bars:
        return ""
    rh, mid = 16, w / 2
    h = rh * len(bars) + 8
    mx = max(max(b["call"], b["put"]) for b in bars) or 1
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Opsiyon açık pozisyon haritası">']
    for i, b in enumerate(sorted(bars, key=lambda b: -b["strike"])):
        y = 4 + i * rh
        pw, cw = b["put"] / mx * (mid - 50), b["call"] / mx * (mid - 50)
        out.append(f'<rect x="{mid - 25 - pw:.1f}" y="{y}" width="{pw:.1f}" height="{rh - 4}" rx="2" fill="var(--neg)" opacity=".75"/>')
        out.append(f'<rect x="{mid + 25:.1f}" y="{y}" width="{cw:.1f}" height="{rh - 4}" rx="2" fill="var(--pos)" opacity=".75"/>')
        near = abs(b["strike"] / price - 1) < 0.012
        out.append(f'<text x="{mid}" y="{y + rh - 6}" text-anchor="middle" class="ax" '
                   f'style="{"fill:var(--ink);font-weight:700" if near else ""}">{fmt_num(b["strike"], 0)}</text>')
    out.append("</svg>")
    return "".join(out)


def rev_bars_svg(vals: list[float | None], labels: list[str], w: int = 1000, h: int = 170) -> str:
    v = [x or 0 for x in vals]
    if not v:
        return ""
    mx = max(v) or 1
    bw = w / len(v)
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Çeyreklik ciro">']
    for i, x in enumerate(v):
        bh = x / mx * (h - 40)
        out.append(f'<rect x="{i * bw + 6:.1f}" y="{h - 20 - bh:.1f}" width="{bw - 12:.1f}" height="{bh:.1f}" rx="3" '
                   f'fill="{"var(--acc)" if i == len(v) - 1 else "var(--bar)"}"/>')
        out.append(f'<text x="{i * bw + bw / 2:.1f}" y="{h - 20 - bh - 5:.1f}" text-anchor="middle" class="ax">{big_num(x)}</text>')
        out.append(f'<text x="{i * bw + bw / 2:.1f}" y="{h - 5}" text-anchor="middle" class="ax">{labels[i]}</text>')
    out.append("</svg>")
    return "".join(out)


def big_num(x: float | None) -> str:
    if x is None:
        return "—"
    for lim, suf in ((1e12, " Tn"), (1e9, " Mr"), (1e6, " Mn"), (1e3, " B")):
        if abs(x) >= lim:
            return fmt_num(x / lim, 1) + suf
    return fmt_num(x, 0)


def pct_tone(x: float | None) -> str:
    if x is None or x == 0:
        return "neu"
    return "pos" if x > 0 else "neg"


def signed_pct(x: float | None, nd: int = 1) -> str:
    if x is None:
        return "—"
    sign = "+" if x > 0 else ("−" if x < 0 else "")
    return f"{sign}%{fmt_num(abs(x), nd)}"


def short_date(iso: str | None) -> str:
    if not iso:
        return "—"
    y, m, d = iso.split("-")
    return f"{int(d)} {TR_MONTHS[int(m) - 1][:3]}"


def render(template: str, ctx: dict, template_dir: Path) -> str:
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=select_autoescape(["html"]))
    env.filters.update(num=fmt_num, pct_tone=pct_tone, spct=signed_pct, sdate=short_date, big=big_num)
    env.globals.update(line_chart=line_chart_svg, oi=oi_svg, rev_bars=rev_bars_svg)
    return env.get_template(template).render(**ctx)
