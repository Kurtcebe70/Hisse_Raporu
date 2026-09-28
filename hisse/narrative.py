"""Yorum katmanı: Claude yalnızca hazır sayıları yorumlar. API anahtarı yoksa kural tabanlı şablon."""
from __future__ import annotations

import json
import os
import re

import requests

from .ortak import fmt_num

SYSTEM = """Sen deneyimli bir hisse senedi analistisin ve Türkçe hisse raporu yazıyorsun.
KESİN KURALLAR:
- Sadece sana verilen JSON'daki sayıları kullan. Yeni sayı, tarih, olay, haber veya tahmin UYDURMA.
- Veride olmayan bir şeyden (haber, ürün duyurusu, yönetim açıklaması) bahsetme.
- Yatırım tavsiyesi verme; "al/sat" deme. Kullanıcının kendi tez kurallarını yorumlayabilirsin.
- Sade, akıcı Türkçe. Jargon kullanırsan parantez içinde kısaca açıkla.
- Çıktı yalnızca geçerli JSON olsun, başka hiçbir şey yazma."""

STOCK_USER = 'Bir hisse için deterministik analiz verisi:\n```json\n{facts}\n```\nŞu JSON şemasıyla, Türkçe yanıt ver:\n{{\n  "ozet": "3-4 cümle: şirketin bugünkü resmi — büyüme, kârlılık, değerleme, trend ve beklenti birlikte",\n  "guclu": ["2-4 madde: verideki güçlü yanlar"],\n  "zayif": ["2-4 madde: verideki riskler/zayıf yanlar"],\n  "tez": "Kullanıcının tezi ve kuralları verildiyse 1-2 cümle: veriler tezi destekliyor mu, hangi kural uyarı veriyor. Tez yoksa boş string.",\n  "izle": ["2-4 madde: önümüzdeki dönemde izlenecek somut seviye/olay (bilanço tarihi, çıkış çizgileri, opsiyon duvarları vb.)"]\n}}'


def _stock_facts(s: dict) -> dict:
    t, f = s["trend"], s["finans"]
    return {
        "sembol": s["sembol"], "ad": s["ad"], "sektor": s["sektor"], "fiyat": s["fiyat"],
        "metrikler": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in s["metrikler"].items()},
        "karne": s["karne"], "adil_deger": {"harman": s["adil"].get("deger"), "fark_%": s["adil"].get("fark"),
                                          "guven": s["adil"].get("guven"),
                                          "yontemler": [{"ad": m["ad"], "deger": round(m["deger"], 2)} for m in s["adil"]["yontemler"]]},
        "trend": {"skor": t["skor"], "asama": t["asama"], "uyarilar": t["uyarilar"],
                  "cikis_cizgileri": [{"ad": c["ad"], "fiyat": c["fiyat"] and round(c["fiyat"], 2), "mesafe_%": c["mesafe"]} for c in t["cikis"]],
                  "seviyeler": [{"ad": v["ad"], "fiyat": round(v["fiyat"], 2), "tur": v["tur"]} for v in t["seviyeler"]]},
        "son_ceyrekler": f["ceyrekler"][-4:],
        "analist": {k: s["analist"][k] for k in ("dagilim", "al_orani", "hedef", "yukseltme", "dusurme")},
        "insider_90g": {k: v for k, v in s["insider"].items() if k != "islemler"},
        "bilanco": {k: s["bilanco"][k] for k in ("sonraki", "is_gunu", "tutturma", "ort_tepki")},
        "opsiyon": {k: v for k, v in s["opsiyon"].items() if k != "bars"},
        "kullanici_tezi": {k: s["tez"].get(k) for k in ("tema", "tez", "izlenecek", "bozulma", "kural_sonuc")} if s["tez"].get("var") else None,
        "pozisyon": s["pozisyon"],
    }


def _sp(x: float | None, nd: int = 1) -> str:
    return "—" if x is None else f"{'+' if x >= 0 else '−'}%{fmt_num(abs(x), nd)}"


def stock_template(s: dict) -> dict:
    m, t, fv, an, ins = s["metrikler"], s["trend"], s["adil"], s["analist"], s["insider"]
    guclu, zayif = [], []
    cb = m.get("ciro_buyume")
    if cb is not None:
        (guclu if cb >= 20 else zayif if cb < 5 else []).append(f"Ciro bir yıl öncesine göre {_sp(cb)} değişti.")
    if m.get("brut_marj") is not None and m.get("faaliyet_marj") is not None:
        txt = f"Brüt marj %{fmt_num(m['brut_marj'], 1)}, faaliyet marjı %{fmt_num(m['faaliyet_marj'], 1)}."
        (guclu if m["faaliyet_marj"] >= 25 else zayif if m["faaliyet_marj"] < 8 else []).append(txt)
    if m.get("net_nakit") is not None:
        (guclu if m["net_nakit"] > 0 else zayif).append(
            f"{'Net nakit' if m['net_nakit'] > 0 else 'Net borç'} {fmt_num(abs(m['net_nakit']) / 1e9, 1)} milyar $.")
    if m.get("peg"):
        (guclu if m["peg"] <= 1.5 else zayif if m["peg"] > 2.5 else []).append(
            f"PEG {fmt_num(m['peg'], 2)} — F/K beklenen büyümeye göre {'makul' if m['peg'] <= 1.5 else 'yüksek'}.")
    if fv.get("fark") is not None:
        (guclu if fv["fark"] >= 15 else zayif if fv["fark"] <= -15 else []).append(
            f"Adil değer harmanı fiyata göre {_sp(fv['fark'])} (güven {fv['guven']}/100).")
    if an.get("al_orani") is not None:
        (guclu if an["al_orani"] >= 70 else zayif if an["al_orani"] < 40 else []).append(
            f"Analistlerin %{an['al_orani']}'i 'Al' diyor; ortalama hedef {_sp(an['hedef_fark'].get('mean'))}.")
    if t["skor"] >= 70:
        guclu.append(f"Trend skoru {t['skor']}/100 ({t['asama']}).")
    elif t["skor"] < 40:
        zayif.append(f"Trend skoru {t['skor']}/100 ({t['asama']}).")
    zayif += t["uyarilar"]
    if ins.get("var") and ins["alim_sayi"] == 0 and ins["satis_sayi"] > 0:
        zayif.append(f"Son 90 günde yönetici alımı yok; {ins['satis_sayi']} satış ({fmt_num(ins['satis_deger'] / 1e6, 1)} milyon $).")
    ozet = (f"{s['sembol']} karne puanı {s['karne']['skor']}/100, trend skoru {t['skor']}/100 ({t['asama']}). "
            + (f"Adil değer harmanı {fmt_num(fv['deger'], 2)} $ — fiyata göre {_sp(fv['fark'])} (güven {fv['guven']}/100). " if fv.get("deger") else "")
            + (f"Analistlerin %{an['al_orani']}'i 'Al' diyor." if an.get("al_orani") is not None else ""))
    izle = []
    if s["bilanco"]["sonraki"]:
        izle.append(f"Bilanço {s['bilanco']['sonraki']} ({s['bilanco']['is_gunu']} iş günü)"
                    + (f"; opsiyonların fiyatladığı hareket ±%{fmt_num(s['opsiyon']['beklenen_hareket'], 1)}" if s["opsiyon"].get("beklenen_hareket") else "") + ".")
    for c in t["cikis"][:2]:
        if c["fiyat"]:
            izle.append(f"{c['ad']}: {fmt_num(c['fiyat'], 2)} $ ({_sp(c['mesafe'])}).")
    if s["opsiyon"].get("put_duvar") and s["opsiyon"].get("call_duvar"):
        izle.append(f"Opsiyon duvarları: put {fmt_num(s['opsiyon']['put_duvar'], 0)} $ · call {fmt_num(s['opsiyon']['call_duvar'], 0)} $.")
    tez = ""
    if s["tez"].get("var") and s["tez"]["kural_sonuc"]:
        uy = [r for r in s["tez"]["kural_sonuc"] if r["durum"] == "UYARI"]
        tez = ("Tez kurallarının hepsi sağlam." if not uy else
               "Tez kuralı uyarısı: " + "; ".join(f"{r['ad']} ({fmt_num(r['mevcut'], 1)})" for r in uy) + ".")
    return {"ozet": ozet, "guclu": guclu, "zayif": zayif, "tez": tez, "izle": izle, "kaynak": "şablon"}


def stock_narrative(s: dict, cfg: dict) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    model = cfg.get("claude_model", "claude-sonnet-5")
    if key:
        try:
            facts = json.dumps(_stock_facts(s), ensure_ascii=False, default=str)
            r = requests.post("https://api.anthropic.com/v1/messages",
                              headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                              json={"model": model, "max_tokens": 1500, "system": SYSTEM,
                                    "messages": [{"role": "user", "content": STOCK_USER.format(facts=facts)}]}, timeout=120)
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")
            out = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
            out["kaynak"] = f"Claude ({model})"
            return out
        except Exception as e:
            print(f"  ! Claude hisse yorumu alınamadı, şablona dönülüyor: {e}")
    return stock_template(s)

