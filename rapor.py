#!/usr/bin/env python3
"""Hisse raporu üretir.

Kullanım:
  python rapor.py                 # portföy + izleme listesindeki tüm hisseler
  python rapor.py AMD PLTR        # sadece verilen semboller
  python rapor.py --snapshot dosya.pkl   # (test) kayıtlı veriyle
"""
from __future__ import annotations

import argparse
import json
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from hisse.analyze import analyze_stock
from hisse.fetch import fetch_stock, load, save
from hisse.narrative import stock_narrative
from hisse.render import render

ROOT = Path(__file__).parent
DOCS, DATA, TPL = ROOT / "docs", ROOT / "data", ROOT / "templates"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("semboller", nargs="*")
    ap.add_argument("--snapshot", type=Path, nargs="*")
    ap.add_argument("--save-raw", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    tezler = yaml.safe_load((ROOT / "tezler.yaml").read_text(encoding="utf-8")) or {} if (ROOT / "tezler.yaml").exists() else {}

    liste_modu = not args.snapshot and not args.semboller
    if args.snapshot:
        kaynaklar = [("snap", p) for p in args.snapshot]
    else:
        syms = [s.strip().upper() for s in args.semboller if s.strip()]
        if not syms:
            syms = list(dict.fromkeys([*cfg.get("portfoy", []), *cfg.get("izleme_listesi", [])]))
        kaynaklar = [("yf", s) for s in syms]

    DOCS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    ozet_path = DATA / "ozet.json"
    ozet = json.loads(ozet_path.read_text()) if ozet_path.exists() else {}
    listeler = set(cfg.get("portfoy", [])) | set(cfg.get("izleme_listesi", []))
    portfoy = set(cfg.get("portfoy", []))
    bu_calisma: list[str] = []
    ortak = {"cfg": cfg, "makro_url": cfg.get("makro_rapor_url") or ""}

    for kind, src in kaynaklar:
        try:
            print(f"→ {src}")
            d = load(src) if kind == "snap" else fetch_stock(src, cfg.get("benchmark", "SPY"))
            if args.save_raw and kind == "yf":
                save(d, DATA / f"{d['sembol']}.pkl")
            s = analyze_stock(d, cfg, tezler.get(d["sembol"]))
            yorum = stock_narrative(s, cfg)
            (DOCS / f"{s['sembol']}.html").write_text(render("hisse.html.j2", {**ortak, "s": s, "yorum": yorum}, TPL),
                                                      encoding="utf-8")
            ozet[s["sembol"]] = {"sembol": s["sembol"], "ad": s["ad"], "fiyat": s["fiyat"], "gun": s["gun"],
                                 "karne": s["karne"]["skor"], "trend": s["trend"]["skor"], "asama": s["trend"]["asama"],
                                 "adil_fark": s["adil"].get("fark"), "tarih": s["trend"]["tarih"],
                                 "bilanco": s["bilanco"]["sonraki"], "ozet": yorum.get("ozet", ""),
                                 "tez": s["tez"]["saglam"] if s["tez"].get("var") and s["tez"].get("kural_sonuc") else None,
                                 "tez_uyarilari": [r["ad"] for r in s["tez"].get("kural_sonuc", []) if r["durum"] == "UYARI"],
                                 "bilanco_gun": s["bilanco"].get("is_gunu"),
                                 "trend_uyarilari": s["trend"]["uyarilar"]}
            ozet[s["sembol"]]["kaynak"] = "liste" if s["sembol"] in listeler else "elle"
            bu_calisma.append(s["sembol"])
            print(f"  ✓ karne {s['karne']['skor']} · trend {s['trend']['skor']} · adil değer {s['adil'].get('fark')}")
        except Exception as e:
            print(f"  ! {src} atlandı: {e}")
            traceback.print_exc(limit=3)

    if liste_modu:
        # Listelerden çıkarılan hisseleri kaldır; elle analiz ettirilenler (kaynak=elle) kalır.
        for sym in [k for k, v in ozet.items() if k not in listeler and v.get("kaynak", "liste") == "liste"]:
            del ozet[sym]
            (DOCS / f"{sym}.html").unlink(missing_ok=True)
            print(f"  − {sym} listeden çıkarıldı")
    ozet_path.write_text(json.dumps(ozet, ensure_ascii=False, indent=1))
    (DATA / "son_calisma.json").write_text(json.dumps(bu_calisma))
    for e in ozet.values():
        e["portfoyde"] = e["sembol"] in portfoy
    entries = sorted(ozet.values(), key=lambda e: (not e["portfoyde"], -(e.get("karne") or 0)))
    simdi = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")
    (DOCS / "index.html").write_text(render("index.html.j2", {**ortak, "entries": entries, "simdi": simdi}, TPL),
                                     encoding="utf-8")
    print("Tamam → docs/index.html")


if __name__ == "__main__":
    main()
