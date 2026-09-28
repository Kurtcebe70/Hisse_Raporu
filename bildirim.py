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


def mesaj() -> str:
    ozet = json.loads((ROOT / "data" / "ozet.json").read_text())
    son = json.loads((ROOT / "data" / "son_calisma.json").read_text())
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    portfoy = cfg.get("portfoy", [])
    url = site_url()
    kayitlar = [ozet[s] for s in son if s in ozet]
    if not kayitlar:
        return ""
    sirali = sorted(kayitlar, key=lambda x: (x["sembol"] not in portfoy, x["sembol"]))
    tek = len(kayitlar) == 1
    satirlar = [f"📈 <b>Hisse Raporu</b>" + (f" · {e(kayitlar[0]['sembol'])}" if tek else ""), ""]
    for x in sirali:
        link = f'<a href="{url}{x["sembol"]}.html">{e(x["sembol"])}</a>' if url else f"<b>{e(x['sembol'])}</b>"
        satirlar.append(f"{link} {fmt_num(x['fiyat'], 2)} ({yuzde(x['gun'])})")
        satirlar.append(f"   Karne {x['karne'] if x['karne'] is not None else '—'} · Trend {x['trend']} · "
                        f"Adil değer {yuzde(x['adil_fark'], 0)}")
        notlar = []
        if x.get("tez_uyarilari"):
            notlar.append("🔴 Tez uyarısı: " + ", ".join(x["tez_uyarilari"]))
        if x.get("bilanco_gun") is not None and x["bilanco_gun"] <= 7:
            notlar.append(f"📅 Bilanço {x['bilanco_gun']} iş günü sonra")
        for u in x.get("trend_uyarilari", [])[:1]:
            notlar.append(f"⚠️ {u}")
        satirlar += [f"   {e(n)}" for n in notlar]
        if tek and x.get("ozet"):
            satirlar += ["", e(x["ozet"])]
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
