# Hisse Raporu — Kişisel Hisse Analiz Sayfaları

Portföyündeki ve izleme listendeki her hisse için ayrıntılı bir analiz sayfası üretir. Sayfalar her hafta içi sabah 05:45 (TSİ) kendiliğinden güncellenir. İstediğin başka bir hisseyi de tek tıkla analiz ettirebilirsin.

**Maliyet:** Kullandığı tüm veriler ve GitHub ücretsiz. Claude yorumu isteğe bağlı: her hisse başına yaklaşık 1–2 cent.

## Her hisse sayfasında neler var?

| Bölüm | İçerik |
|---|---|
| Özet | Hisse karnesi (0–100), trend skoru (0–100), 3 yöntemli adil değer, kısa yorum |
| Tek bakışta | Piyasa değeri, ciro ve EPS büyümesi, F/K, ileri F/K, PEG, marjlar, RSI, 52 hafta bandı, net nakit, sonraki bilanço |
| 01 Karne | Büyüme, kârlılık, bilanço, değerleme, trend ve beklenti puanları; güçlü ve zayıf yanlar |
| 02 Yatırım tezin | `tezler.yaml` dosyasına yazdığın tez ve "tez bozulursa" kuralların. Kurallar her gün otomatik kontrol edilir. |
| 03 Trend ve çıkış planı | Grafik, trend kontrol listesi, destek/direnç haritası ve 4 çıkış çizgisi |
| 04 Adil değer | F/K–büyüme, indirgenmiş nakit akışı ve analist hedefi; her yöntemin nasıl hesaplandığı |
| 05 Para kazanıyor mu? | Çeyreklik ciro, marjlar, net kâr, EPS, serbest nakit akışı |
| 06 Bilanço | Sonraki tarih, opsiyonların fiyatladığı beklenen hareket, geçmiş sürprizler ve fiyat tepkileri |
| 07 Uzmanlar | Analist Al/Tut/Sat dağılımı, hedef fiyat aralığı, son not değişiklikleri |
| 08 Yöneticiler | Son 90 günde içeriden (insider) alım ve satımlar |
| 09 Büyük para | Opsiyon açık pozisyon haritası: put duvarı, call tavanı, max pain |

Ana sayfada (`index.html`) tüm hisseler kartlar halinde listelenir: önce portföyün, sonra izleme listen.

---

## Kurulum (bir kerelik, ~15 dakika)

Makro raporu kurduysan adımlar aynı. Tek fark, bu proje için **ayrı bir depo** açıyorsun.

### 1. Zip'i aç
`hisse-rapor.zip` dosyasını indir ve bilgisayarında aç.

### 2. Yeni depo oluştur
1. github.com adresinde sağ üstteki **+** işaretine tıkla ve **New repository** seç.
2. Ad olarak `hisse-rapor` yaz, **Public** seç ve **Add a README file** kutusunu işaretle.
3. **Create repository** de.

### 3. Dosyaları yükle
1. **Add file → Upload files** yolunu izle.
2. `hisse-rapor` klasörünün **içindekileri** sürükle bırak: `hisse` ve `templates` klasörleri ile `config.yaml`, `tezler.yaml`, `rapor.py`, `requirements.txt`, `README.md` dosyaları.
3. **Commit changes** de.

### 4. Otomasyon dosyasını oluştur
1. **Add file → Create new file** yolunu izle.
2. Dosya adı olarak tam olarak şunu yaz: `.github/workflows/hisse-raporu.yml`
3. Zip'teki aynı adlı dosyayı Not Defteri ile aç, içeriğini kopyala ve yapıştır.
4. **Commit changes** de.

### 5. Yazma iznini aç
**Settings → Actions → General** bölümüne git. En alttaki **Workflow permissions** kısmında **Read and write permissions** seç ve **Save** de.

### 6. Claude anahtarını ekle (isteğe bağlı)
**Settings → Secrets and variables → Actions → New repository secret** yolunu izle.
- Name: `ANTHROPIC_API_KEY`
- Secret: Anthropic Console'dan aldığın anahtar. Makro rapor için aldığın anahtarı burada da kullanabilirsin.

### 7. İlk çalıştırma
**Actions → Hisse Raporu → Run workflow** yolunu izle, kutuyu boş bırak ve yeşil butona bas. 3–5 dakika sonra yeşil tik görünmeli.

### 8. Sayfayı yayına al
**Settings → Pages** bölümünde Source olarak **Deploy from a branch**, Branch olarak `main` ve klasör olarak `/docs` seç, sonra **Save** de. Birkaç dakika sonra raporun şu adreste olur:
`https://KULLANICI-ADIN.github.io/hisse-rapor/`

### 9. Makro raporla birbirine bağla (isteğe bağlı)
- **Makro rapor → hisse raporu:** makro-rapor deposunda `config.yaml` dosyasını aç. `hisse_raporu_url` satırına bu adresi yaz. Portföy tablosundaki hisse adları tıklanabilir hale gelir.
- **Hisse raporu → makro rapor:** bu depoda `config.yaml` dosyasını aç. `makro_rapor_url` satırına makro raporunun adresini yaz. Hisse sayfalarının üstüne "Makro rapor" bağlantısı eklenir.

---

## Günlük kullanım

| Ne yapmak istiyorsun? | Nasıl |
|---|---|
| Yeni bir hisseyi analiz etmek | **Actions → Hisse Raporu → Run workflow**, kutuya sembolü yaz (örn. `AMD` veya `AMD PLTR`) |
| Hisseyi her gün otomatik takip etmek | `config.yaml` → `portfoy` veya `izleme_listesi` listesine ekle |
| Tezini yazmak ve kural koymak | `tezler.yaml` → "BURAYA KENDİ TEZİNİ YAZ" yerlerini doldur, kuralları ayarla |
| Pozisyonunun kâr/zararını görmek | `tezler.yaml` → ilgili hissede `maliyet:` ve `adet:` satırlarının başındaki `#` işaretini kaldırıp doldur |
| Karne ağırlıklarını / adil değer varsayımlarını değiştirmek | `config.yaml` → `karne_agirliklari`, `degerleme` |

Dosyaları GitHub'da açıp kalem simgesine basarak düzenleyebilirsin. Değişiklik bir sonraki çalıştırmada rapora yansır.

## Tez kuralları nasıl yazılır?

```yaml
NVDA:
  tez: "Veri merkezi talebi sürdükçe..."
  kurallar:
    - {ad: "Brüt marj %65 altı", metrik: brut_marj, op: "<", deger: 65}
```
Bu kural şu demek: brüt marj 65'in altına düşerse raporda kırmızı **UYARI** çıksın.

Kullanılabilecek metrikler şunlar:
- **Büyüme:** `ciro_buyume`, `eps_buyume`
- **Marjlar ve getiri:** `brut_marj`, `faaliyet_marj`, `net_marj`, `fcf_marj`, `roe`
- **Değerleme:** `fk`, `fk_ileri`, `peg`, `adil_deger_fark`
- **Fiyat ve trend:** `trend_skoru`, `rsi`, `zirveden`
- **Genel puan:** `karne`

## Bilinen sınırlar
- Veriler Yahoo Finance'ten gelir (`yfinance` kütüphanesi). Bazı hisselerde bazı alanlar boş olabilir; o bölüm "veri yok" gösterir, rapor yine üretilir.
- Yahoo çoğu hisse için yalnızca son 4–6 çeyreği verir.
- Adil değer bir tahmindir; varsayımlardaki küçük değişiklikler sonucu belirgin biçimde değiştirir.
- GitHub zamanlanmış görevleri yoğun saatlerde 10–30 dakika gecikebilir.
- Rapor kişisel kullanım içindir, yatırım tavsiyesi değildir.

## Bilgisayarında çalıştırmak (isteğe bağlı)
```bash
pip install -r requirements.txt
python rapor.py            # portföy + izleme listesi
python rapor.py AMD        # tek hisse
```
