"""
Bursa Hal Fiyat Takip Botu
---------------------------
Bursa Büyükşehir Belediyesi'nin RESMİ ve ÜCRETSİZ açık veri API'sinden
günlük hal fiyatlarını çeker, bir önceki çalıştırmayla karşılaştırır ve
önemli fiyat değişimlerini Telegram'a otomatik mesaj olarak gönderir.

Veri kaynağı: https://bapi.bursa.bel.tr/apigateway/acikveri/hal-fiyatlari
(Bursa Büyükşehir Belediyesi Açık Veri Portalı - tamamen resmi ve yasal)

Bu betik günde 1 kez (örn. sabah 07:00) otomatik çalışacak şekilde
GitHub Actions gibi ücretsiz bir zamanlayıcıya bağlanmak için tasarlandı.
Kurulum adımları için KURULUM.md dosyasına bakın.
"""

import json
import os
import urllib.request
from pathlib import Path

# ---- AYARLAR (bunları kendi bilgilerinle değiştir) ----------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "BURAYA_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "BURAYA_GRUP_ID")
DEGISIM_ESIGI_YUZDE = 15  # bu yüzdenin üstündeki değişimler bildirim gönderir
VERI_URL = "https://bapi.bursa.bel.tr/apigateway/acikveri/hal-fiyatlari"
GECMIS_DOSYA = Path("onceki_fiyatlar.json")
# ---------------------------------------------------------------------------


def hal_verisini_cek():
    """Bursa Belediyesi'nin resmi API'sinden güncel hal fiyatlarını çeker."""
    with urllib.request.urlopen(VERI_URL, timeout=20) as response:
        veri = json.loads(response.read().decode("utf-8"))
    # ürün adına göre sözlük hâline getir: {"Domates": {"min": 8.0, "max": 60.0}, ...}
    sonuc = {}
    for kalem in veri:
        ad = kalem["urun_ad"].strip()
        try:
            minf = float(kalem["min"].replace(",", "."))
            maxf = float(kalem["max"].replace(",", "."))
        except (ValueError, AttributeError):
            continue
        sonuc[ad] = {"min": minf, "max": maxf, "birim": kalem.get("br", "")}
    return sonuc


def onceki_veriyi_yukle():
    if GECMIS_DOSYA.exists():
        return json.loads(GECMIS_DOSYA.read_text(encoding="utf-8"))
    return {}


def veriyi_kaydet(veri):
    GECMIS_DOSYA.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def degisimleri_bul(eski, yeni):
    """Belirlenen eşiğin üzerinde değişen ürünleri bulur."""
    bildirimler = []
    for urun, yeni_fiyat in yeni.items():
        if urun not in eski:
            continue
        eski_min = eski[urun]["min"]
        yeni_min = yeni_fiyat["min"]
        if eski_min <= 0:
            continue
        degisim_yuzde = ((yeni_min - eski_min) / eski_min) * 100
        if abs(degisim_yuzde) >= DEGISIM_ESIGI_YUZDE:
            yon = "📉 UCUZLADI" if degisim_yuzde < 0 else "📈 PAHALANDI"
            bildirimler.append(
                f"{yon}  {urun}: {eski_min:.0f}₺ → {yeni_min:.0f}₺  "
                f"(%{abs(degisim_yuzde):.0f} {'düşüş' if degisim_yuzde < 0 else 'artış'})"
            )
    return bildirimler


def telegram_mesaj_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": mesaj}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read()


def calistir():
    yeni_veri = hal_verisini_cek()
    eski_veri = onceki_veriyi_yukle()

    if not eski_veri:
        # ilk çalıştırma - sadece kaydet, henüz kıyaslama yapılamaz
        veriyi_kaydet(yeni_veri)
        print("İlk veri kaydedildi. Bir sonraki çalıştırmadan itibaren karşılaştırma başlayacak.")
        return

    bildirimler = degisimleri_bul(eski_veri, yeni_veri)
    veriyi_kaydet(yeni_veri)

    if bildirimler:
        baslik = "🥬 BURSA HAL FİYAT UYARISI\n\n"
        mesaj = baslik + "\n".join(bildirimler)
        telegram_mesaj_gonder(mesaj)
        print(f"{len(bildirimler)} değişim bulundu, Telegram'a gönderildi.")
    else:
        print("Önemli bir fiyat değişimi yok, bildirim gönderilmedi.")


if __name__ == "__main__":
    calistir()
