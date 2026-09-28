#!/usr/bin/env python3
"""Hisse raporunun özetini Telegram'a gönderir.

Gerekli GitHub sırları: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Sırlar yoksa sessizce atlar; rapor üretimini asla bozmaz.
"""
from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path

import requests
import yaml

from hisse.ortak import fmt_num

ROOT = Path(__file__).parent


def e(x) -> str:
    return html.escape(str(x), quote=False)


def yuzde(x, nd: int = 1) -> str:
    if x is None:
        return "—"
    if round(abs(x), nd) == 0:
        return "%0"
    return f"{'+' if x > 0 else '−'}%{fmt_num(abs(x), nd)}"


def site_url() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo:
        return ""
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}/"


def _satir(x: dict, url: str, detay: bool) -> list[str]:
    link = f'<a href="{url}{x["sembol"]}.html">{e(x["sembol"])}</a>' if url else f"<b>{e(x['sembol'])}</b>"
    out = [f"{link} {fmt_num(x['fiyat'], 2)} ({yuzde(x['gun'])})"]
    if detay:
        karne = x["karne"] if x.get("karne") is not None else "—"
        out.append(f"   Karne {karne} · Trend {x['trend']} · Adil değer {yuzde(x['adil_fark'], 0)}")
        notlar = []
        if x.get("tez_uyarilari"):
            notlar.append("🔴 Tez uyarısı: " + ", ".join(x["tez_uyarilari"]))
        if x.get("bilanco_gun") is not None and x["bilanco_gun"] <= 7:
            notlar.append(f"📅 Bilanço {x['bilanco_gun']} iş günü sonra")
        out += [f"   {e(n)}" for n in notlar]
    return out


def mesaj() -> str:
    ozet = json.loads((ROOT / "data" / "ozet.json").read_text())
    son = json.loads((ROOT / "data" / "son_calisma.json").read_text())
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    portfoy = cfg.get("portfoy", [])
    url = site_url()
    kayitlar = [ozet[s] for s in son if s in ozet]
    if not kayitlar:
        return ""

    # Elle tek/birkaç hisse analizi: hepsini ayrıntılı yaz
    if len(kayitlar) <= 5:
        satirlar = ["📈 <b>Hisse Analizi</b>", ""]
        for x in kayitlar:
            satirlar += _satir(x, url, True)
            if x.get("ozet"):
                satirlar += [f"   <i>{e(x['ozet'])}</i>"]
            satirlar.append("")
        if url:
            satirlar.append(f'🔗 <a href="{url}">Tüm hisseler</a>')
        return "\n".join(satirlar)[:4000]

    port = [x for x in kayitlar if x["sembol"] in portfoy]
    izl = [x for x in kayitlar if x["sembol"] not in portfoy]
    satirlar = ["📈 <b>Hisse Raporu</b>", ""]
    if port:
        satirlar.append(f"<b>💼 Portföy ({len(port)})</b>")
        for x in sorted(port, key=lambda x: portfoy.index(x["sembol"])):
            satirlar += _satir(x, url, True)
        satirlar.append("")

    if izl:
        satirlar.append(f"<b>👀 İzleme listesi ({len(izl)}) — öne çıkanlar</b>")
        hareket = sorted([x for x in izl if x.get("gun") is not None], key=lambda x: x["gun"])
        yuk = [x for x in reversed(hareket) if x["gun"] > 0][:4]
        dus = [x for x in hareket if x["gun"] < 0][:4]
        if yuk:
            satirlar.append("🟢 Yükselen: " + " · ".join(f"{e(x['sembol'])} {yuzde(x['gun'])}" for x in yuk))
        if dus:
            satirlar.append("🔴 Düşen: " + " · ".join(f"{e(x['sembol'])} {yuzde(x['gun'])}" for x in dus))
        bil = sorted([x for x in izl if x.get("bilanco_gun") is not None and x["bilanco_gun"] <= 5],
                     key=lambda x: x["bilanco_gun"])
        if bil:
            satirlar.append("📅 Bilanço yakın: " + " · ".join(f"{e(x['sembol'])} ({x['bilanco_gun']} gün)" for x in bil))
        guclu = sorted([x for x in izl if (x.get("karne") or 0) >= 75 and x.get("trend", 0) >= 75],
                       key=lambda x: -((x.get("karne") or 0) + x["trend"]))[:6]
        if guclu:
            satirlar.append("⭐ Karne ve trend güçlü: " + ", ".join(e(x["sembol"]) for x in guclu))
        zayif = sorted([x for x in izl if x.get("trend", 100) <= 25], key=lambda x: x["trend"])[:6]
        if zayif:
            satirlar.append("⚠️ Trend zayıf: " + ", ".join(e(x["sembol"]) for x in zayif))
    if url:
        satirlar += ["", f'🔗 <a href="{url}">Tüm hisseler</a>']
    return "\n".join(satirlar)[:4000]


def main() -> None:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(), os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        print("Telegram sırları tanımlı değil — bildirim atlandı.")
        return
    try:
        text = mesaj()
        if not text:
            print("Gönderilecek hisse yok.")
            return
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                                "disable_web_page_preview": True}, timeout=30)
        print("Telegram:", "gönderildi ✓" if r.ok else f"hata {r.status_code} {r.text[:200]}")
    except Exception as ex:
        print(f"Telegram bildirimi gönderilemedi: {ex}", file=sys.stderr)


if __name__ == "__main__":
    main()
