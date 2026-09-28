"""Bad Apple!!, GitHub'un contribution graph'ına basılmış hâli.

    python3 main.py

Menü açılır, seçtiklerini sorar, işi başlatır. AYAR_SOR = False ise menü
atlanır ve ayarlar olduğu gibi çalışır. Komut satırı yolu da duruyor:
python3 -m badapple --help

Ayarlar:
    VIDEO             basılacak video; yoksa aynı isimli dosya projede aranır
    CIKTI             .svg / .png / .txt; None ise ekrana metin basılır
    PNG_OLCEK         PNG piksel çarpanı
    KARE_SAYISI       filmin kaç anı örneklenir
    BAND_SAYISI       bir kare kaç yıl bandına yayılır, bir bant 7 satırdır
    EN_YENI_YIL       None bu yıl, bir sayı o yılda biter
    KIRPMA            subject mürekkebe göre kırpar, crop oranı korur,
                      squash kareyi olduğu gibi kullanır
    HAVUZ             coverage hücredeki mürekkep oranı, max bir piksel yeter,
                      area gri ortalaması
    BOLGE_PAYI        kırpılan öznenin etrafındaki boşluk
    BOLGE_ESIGI       bu oranın üstü öznenin kendisi sayılır
    HUCRE_ESIGI       hücreyi yakmak için gereken mürekkep oranı
    TONLENDIR         kısmi kapsamı dört yeşil seviyeye böler
    YESIL_SEVIYE      dolu mürekkep hangi yeşil, 0 en açık 4 en koyu
    TUM_YIL           komşu yıllara ait günleri de basar
    GIF, GIF_FPS      GIF yolu ve kare hızı, düşük fps yavaş animasyon
    MP4, MP4_FPS      MP4 yolu ve kare hızı
    TERMINALDE        iş bitince terminalde oynatır
    KARSILASTIR       film ve grafik yan yana video yolu
    KARSILASTIR_KARE  karşılaştırmada kaç an örneklenir
    KARSILASTIR_FPS   karşılaştırmanın kare hızı
    MUZIK             source filmin kendi sesi, generated üretilen döngü,
                      none sessiz, ya da bir dosya yolu
    AYAR_SOR          menüyü açıp açmayacağı
"""

import sys
from pathlib import Path

from badapple import Player, Printer, duration, read_bitmaps, write_output, write_video
from badapple.compare import build_frames
from badapple.sound import resolve_music
from badapple.check import (
    binary_hint, film_hint, has_pillow, missing_binaries, needs_pillow, pillow_hint,
)

VIDEO = "assets/bad_apple.mp4"
CIKTI = "out/bad_apple.png"
PNG_OLCEK = 1

KARE_SAYISI = 53
BAND_SAYISI = 3
EN_YENI_YIL = None

KIRPMA = "subject"
HAVUZ = "coverage"
BOLGE_PAYI = 0.15
BOLGE_ESIGI = 0.35
HUCRE_ESIGI = 0.5
TONLENDIR = False
INVERT = False
YESIL_SEVIYE = 4
TUM_YIL = False

GIF = None
GIF_FPS = 2
MP4 = None
MP4_FPS = 6
TERMINALDE = False

KARSILASTIR = None
KARSILASTIR_KARE = 90
KARSILASTIR_FPS = 12
MUZIK = "source"

AYAR_SOR = True


"""Menu entries: (label, variable, type, choices, range).

``range`` is ``(low, high)`` with ``low`` exclusive, so ``(0, 1)`` accepts
``0 < value <= 1``; ``high`` may be None for an open end.
"""
_MENU = [
    ("Video", "VIDEO", str, None, None),
    ("Çıktı dosyası", "CIKTI", str, None, None),
    ("Kare sayısı", "KARE_SAYISI", int, None, None),
    ("Bant sayısı", "BAND_SAYISI", int, None, None),
    ("En yeni yıl", "EN_YENI_YIL", str, None, None),
    ("Kırpma", "KIRPMA", str, ["subject", "crop", "squash"], None),
    ("Havuz", "HAVUZ", str, ["coverage", "max", "area"], None),
    ("Eşik (hücre)", "HUCRE_ESIGI", float, None, (0, 1)),
    ("Kırpma payı", "BOLGE_PAYI", float, None, (0, 1)),
    ("Yeşil seviye", "YESIL_SEVIYE", int, [0, 1, 2, 3, 4], None),
    ("Tonlandır", "TONLENDIR", bool, [True, False], None),
    ("Ters", "INVERT", bool, [True, False], None),
    ("Komşu yıl günleri", "TUM_YIL", bool, [True, False], None),
    ("PNG ölçek", "PNG_OLCEK", int, [1, 2, 3], None),
    ("GIF", "GIF", str, None, None),
    ("GIF fps", "GIF_FPS", float, None, (0, None)),
    ("MP4", "MP4", str, None, None),
    ("MP4 fps", "MP4_FPS", float, None, (0, None)),
    ("Karşılaştırma MP4", "KARSILASTIR", str, None, None),
    ("Karşılaştırma kare", "KARSILASTIR_KARE", int, None, None),
    ("Karşılaştırma fps", "KARSILASTIR_FPS", float, None, (0, None)),
    ("Müzik", "MUZIK", str, ["source", "generated", "none"], None),
    ("Terminalde oynat", "TERMINALDE", bool, [True, False], None),
]
_YOK = ("yok", "none", "-", "kapali", "kapalı")


def _goster(deger: bool | str | int | float | None) -> str:
    if isinstance(deger, bool):
        return "evet" if deger else "hayır"
    return "yok" if deger is None else str(deger)


def _menu_acik() -> bool:
    return AYAR_SOR and sys.stdin.isatty() and sys.stdout.isatty()


def _menu() -> bool:
    """Ayar menüsü. True dönerse iş başlar, False dönerse çıkılır."""
    while True:
        print("\n  Bad Apple!! -> GitHub contribution graph")
        print("  " + "-" * 52)
        for index, (baslik, ad, _tur, secenekler, _aralik) in enumerate(_MENU, start=1):
            satirlar = f" {secenekler}" if secenekler else ""
            print(f" {index:2}) {baslik:<22} {_goster(globals()[ad]):<24}{satirlar}")
        print("  " + "-" * 52)
        if not Path(VIDEO).expanduser().exists():
            print(f"  ! video yok: {VIDEO}  (1) ile yolunu düzelt")
        print("  numara gir, sonra değeri soracak | 'b' boş bırak (başlat) | 'q' çık")
        try:
            secim = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if secim in ("", "b", "baslat"):
            return True
        if secim in ("q", "cik", "çık"):
            return False
        if not secim.isdigit() or not 1 <= int(secim) <= len(_MENU):
            print("  1 ile", len(_MENU), "arası bir numara gir.")
            continue
        _duzenle(_MENU[int(secim) - 1])


def _duzenle(ayar) -> None:
    baslik, ad, tur, secenekler, aralik = ayar
    mevcut = globals()[ad]
    if secenekler:
        print("   seçenekler: " + " / ".join(_goster(s) for s in secenekler))
    ipucu = "yok yazılırsa silinir" if tur is str else ""
    try:
        ham = input(f"   {baslik} [{_goster(mevcut)}] {ipucu}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if not ham:
        return
    if tur is str and secenekler is None and ham.lower() in _YOK:
        globals()[ad] = None
        return
    if tur is bool:
        if ham.lower() in ("e", "evet", "y", "hayir", "hayır", "1", "0", "true", "false"):
            globals()[ad] = ham.lower() in ("e", "evet", "y", "1", "true")
        else:
            print("   evet/hayır yaz.")
        return
    try:
        deger = tur(ham)
    except ValueError:
        print("   sayı olmalı.")
        return
    if secenekler and deger not in secenekler:
        print("   seçeneklerden biri olmalı.")
        return
    if tur is int and deger < 0:
        print("   negatif olamaz.")
        return
    if aralik is not None:
        alt, ust = aralik
        if (alt is not None and deger <= alt) or (ust is not None and deger > ust):
            ust_metin = "sonsuz" if ust is None else f"{ust:g}"
            print(f"   {alt:g} ile {ust_metin} arası olmalı.")
            return
    globals()[ad] = deger


_VIDEO_UZANTI = (".mp4", ".mkv", ".webm", ".avi", ".mov", ".mpg", ".gif", ".webp")


def _videolar() -> list[Path]:
    return sorted(p for p in Path(".").rglob("*")
                  if p.is_file() and p.suffix.lower() in _VIDEO_UZANTI)


def _videoyu_coz() -> Path:
    """VIDEO yolunu çöz: yoksa aynı isimli dosyayı projede ara."""
    yol = Path(VIDEO).expanduser()
    if yol.exists():
        return yol
    for aday in _videolar():
        if aday.name.lower() == yol.name.lower():
            return aday
    bulunan = _videolar()
    ipucu = ("bulunan videolar: " + ", ".join(str(p) for p in bulunan)) if bulunan \
        else "bu klasörde hiç video yok"
    raise FileNotFoundError(f"video bulunamadı: {VIDEO}\n{film_hint(VIDEO)}"
                            + (f"\n       {ipucu}" if bulunan else ""))


def _hazirlik() -> None:
    """Ne eksikse başlamadan söyle."""
    eksik = missing_binaries()
    if eksik:
        raise RuntimeError(binary_hint())
    if needs_pillow([_yol(CIKTI), _yol(GIF), _yol(MP4), _yol(KARSILASTIR)]):
        if not has_pillow():
            raise RuntimeError(pillow_hint())


def _yol(deger: str | None) -> Path | None:
    return Path(deger) if deger else None


def _printer(fill_outside: bool = False) -> Printer:
    return Printer(
        start_year=EN_YENI_YIL,
        fit=KIRPMA,
        shade=TONLENDIR,
        invert=INVERT,
        level=YESIL_SEVIYE,
        fill_outside=fill_outside or TUM_YIL,
    )


def calistir() -> None:
    _hazirlik()
    video = _videoyu_coz()
    frames = read_bitmaps(
        video,
        count=KARE_SAYISI,
        size=(53, 7 * BAND_SAYISI),
        bands=BAND_SAYISI,
        fit=KIRPMA,
        pool=HAVUZ,
        crop_threshold=BOLGE_ESIGI,
        margin=BOLGE_PAYI,
    )

    printer = _printer()
    grids = printer.print_film(frames, years=KARE_SAYISI).bands()
    stats = printer.stats()
    print(f"{KARE_SAYISI} kare, {stats.years} yıl bandı, "
          f"{stats.lit_cells}/{stats.total_cells} hücre dolu ({stats.ink_ratio:.1%})")

    sonuc = write_output(grids, CIKTI, scale=PNG_OLCEK)
    print(sonuc, end="" if sonuc.endswith("\n") else "\n")

    if GIF or MP4 or TERMINALDE:
        player = Player(frames, fps=GIF_FPS, printer=_printer(fill_outside=True))
        if GIF:
            print(f"yazıldı: {player.write_gif(GIF)} kare -> {GIF} ({GIF_FPS} fps)")
        if MP4:
            print(f"yazıldı: {player.write_video(MP4, fps=MP4_FPS)} kare -> {MP4} ({MP4_FPS} fps)")
        if TERMINALDE:
            player.run(once=True)

    if KARSILASTIR:
        _karsilastir()


def _karsilastir() -> None:
    """Filmi ve grafiği tek bir MP4'te yan yana birleştir."""
    video = _videoyu_coz()
    frames = read_bitmaps(
        video,
        count=KARSILASTIR_KARE,
        size=(53, 7 * BAND_SAYISI),
        bands=BAND_SAYISI,
        fit=KIRPMA,
        pool=HAVUZ,
        crop_threshold=BOLGE_ESIGI,
        margin=BOLGE_PAYI,
    )
    player = Player(frames, fps=KARSILASTIR_FPS, printer=_printer(fill_outside=True))
    with resolve_music(MUZIK, duration(video), source=video) as music:
        written = write_video(build_frames(video, player), KARSILASTIR,
                              fps=KARSILASTIR_FPS, audio=music)
    etiket = {"source": "filmin kendi sesi", "generated": "üretilen döngü",
              "none": "sessiz"}.get(MUZIK) or Path(MUZIK).name
    print(f"yazıldı: {written} kare -> {KARSILASTIR} ({Path(KARSILASTIR).name}, {etiket})")


if __name__ == "__main__":
    if _menu() if _menu_acik() else True:
        try:
            calistir()
        except (ValueError, RuntimeError, OSError) as hata:
            print(f"\nhata: {hata}", file=sys.stderr)
            raise SystemExit(1)
