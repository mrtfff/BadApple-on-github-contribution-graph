import builtins
from pathlib import Path

import pytest

from badapple.printer import Printer
from conftest import requires_ffmpeg


@pytest.fixture(autouse=True)
def restore_settings():
    """The menu writes straight into the module globals; undo that afterwards."""
    import main as settings

    snapshot = {name: value for name, value in vars(settings).items() if name.isupper()}
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


def answer(monkeypatch, *script):
    answers = iter(script)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(answers))


def row(etiket):
    """Menu row number for a label, so tests survive rows being added."""
    import main as settings

    for index, (baslik, *_rest) in enumerate(settings._MENU, start=1):
        if baslik == etiket:
            return str(index)
    raise AssertionError(f"no menu row labelled {etiket!r}")


def prepare(monkeypatch, tmp_path, **overrides):
    """Point the settings file at a temporary clip and output."""
    import main as settings

    monkeypatch.setattr(settings, "VIDEO", str(overrides.pop("video")))
    monkeypatch.setattr(settings, "CIKTI", overrides.pop("cikti", str(tmp_path / "poster.svg")))
    monkeypatch.setattr(settings, "KARE_SAYISI", 2)
    monkeypatch.setattr(settings, "BAND_SAYISI", 1)
    for name, value in overrides.items():
        monkeypatch.setattr(settings, name, value)
    return settings


@requires_ffmpeg
def test_settings_file_writes_a_poster(tmp_path, clip, monkeypatch, capsys):
    settings = prepare(monkeypatch, tmp_path, video=clip, cikti=str(tmp_path / "poster.svg"))
    settings.calistir()
    svg = (tmp_path / "poster.svg").read_text()
    assert svg.count("<use ") == 2 * 371
    assert "2 yıl bandı" in capsys.readouterr().out


@requires_ffmpeg
def test_settings_file_writes_png(tmp_path, clip, monkeypatch):
    from PIL import Image

    prepare(monkeypatch, tmp_path, video=clip,
            cikti=str(tmp_path / "poster.png"), PNG_OLCEK=1).calistir()
    assert Image.open(tmp_path / "poster.png").size == (716, 233)


@requires_ffmpeg
def test_settings_file_exports_gif_and_mp4(tmp_path, moving, monkeypatch, capsys):
    from PIL import Image

    settings = prepare(monkeypatch, tmp_path, video=moving, cikti=str(tmp_path / "poster.svg"),
                       GIF=str(tmp_path / "slow.gif"), MP4=str(tmp_path / "clip.mp4"),
                       GIF_FPS=2, MP4_FPS=4)
    settings.calistir()
    out = capsys.readouterr().out
    assert (tmp_path / "slow.gif").exists() and (tmp_path / "clip.mp4").exists()
    assert "yazıldı: 2 kare" in out
    with Image.open(tmp_path / "slow.gif") as image:
        assert image.info["duration"] == 500


@requires_ffmpeg
def test_settings_file_writes_the_comparison(tmp_path, moving, monkeypatch, capsys):
    settings = prepare(monkeypatch, tmp_path, video=moving, cikti=str(tmp_path / "poster.svg"),
                       KARSILASTIR=str(tmp_path / "side.mp4"), KARSILASTIR_KARE=2,
                       KARSILASTIR_FPS=2, MUZIK="none")
    settings.calistir()
    assert (tmp_path / "side.mp4").exists()
    assert "yazıldı: 2 kare" in capsys.readouterr().out


@requires_ffmpeg
def test_settings_file_can_print_text(tmp_path, clip, monkeypatch, capsys):
    settings = prepare(monkeypatch, tmp_path, video=clip, cikti=None)
    settings.calistir()
    out = capsys.readouterr().out
    assert "█" in out and "contributions" in out
    assert not (tmp_path / "poster.svg").exists()


def test_settings_defaults_are_in_range():
    import main as settings

    assert settings.VIDEO
    assert settings.BAND_SAYISI >= 1
    assert 0 < settings.HUCRE_ESIGI <= 1
    assert 0 <= settings.YESIL_SEVIYE <= 4
    assert settings.KIRPMA in ("subject", "crop", "squash")
    assert settings.HAVUZ in ("coverage", "max", "area")


def test_printer_helper_follows_the_settings(monkeypatch):
    import main as settings

    monkeypatch.setattr(settings, "KIRPMA", "crop")
    assert isinstance(settings._printer(), Printer)
    assert settings._printer().fit == "crop"
    assert settings._printer().fill_outside is False
    assert settings._printer(fill_outside=True).fill_outside is True
    monkeypatch.setattr(settings, "TUM_YIL", True)
    assert settings._printer().fill_outside is True


def test_menu_lists_every_setting(monkeypatch, capsys):
    import main as settings

    answer(monkeypatch, "")
    assert settings._menu() is True
    out = capsys.readouterr().out
    for baslik, _ad, _tur, _secenekler, _aralik in settings._MENU:
        assert baslik in out


def test_menu_accepts_frame_rates_above_one(monkeypatch):
    import main as settings

    answer(monkeypatch, row("MP4 fps"), "24", row("GIF fps"), "30",
            row("Karşılaştırma fps"), "25", "")
    assert settings._menu() is True
    assert settings.MP4_FPS == 24
    assert settings.GIF_FPS == 30
    assert settings.KARSILASTIR_FPS == 25


def test_menu_still_guards_the_thresholds(monkeypatch, capsys):
    import main as settings

    answer(monkeypatch, row("Eşik (hücre)"), "0", "", row("Eşik (hücre)"), "1.5", "")
    assert settings._menu() is True
    assert settings.HUCRE_ESIGI == 0.5
    assert "0 ile 1 arası olmalı" in capsys.readouterr().out


def test_menu_rejects_a_negative_frame_rate(monkeypatch, capsys):
    import main as settings

    answer(monkeypatch, row("MP4 fps"), "-5", "")
    assert settings._menu() is True
    assert settings.MP4_FPS == 6
    assert "0 ile sonsuz arası olmalı" in capsys.readouterr().out


def test_video_path_is_used_as_given(tmp_path, clip, monkeypatch):
    import main as settings

    monkeypatch.setattr(settings, "VIDEO", str(clip))
    assert settings._videoyu_coz() == clip


def test_video_path_is_found_by_name(tmp_path, monkeypatch):
    """The search walks ``Path('.')``, so the probe has to live in a scratch cwd."""
    import main as settings

    probe = tmp_path / "gecici_video_testi.mp4"
    probe.write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "VIDEO", f"olmayan_klasor/{probe.name}")
    assert settings._videoyu_coz() == Path(probe.name)


def test_missing_video_names_the_ones_that_exist(clip, monkeypatch, capsys):
    import main as settings

    monkeypatch.setattr(settings, "VIDEO", "boyle-bir-video-yok.mp4")
    with pytest.raises(FileNotFoundError) as hata:
        settings._videoyu_coz()
    assert "video bulunamadı" in str(hata.value)
    assert "bulunan videolar" in str(hata.value)


def test_menu_warns_when_the_video_is_missing(monkeypatch, capsys):
    import main as settings

    monkeypatch.setattr(settings, "VIDEO", "boyle-bir-video-yok.mp4")
    answer(monkeypatch, "")
    assert settings._menu() is True
    out = capsys.readouterr().out
    assert "video yok" in out


def test_menu_edits_settings_and_returns(monkeypatch, capsys):
    import main as settings

    answer(monkeypatch, row("Kare sayısı"), "8", row("Karşılaştırma MP4"), "out/x.mp4",
            row("Yeşil seviye"), "2", row("Tonlandır"), "e", row("Müzik"), "none", "")
    assert settings._menu() is True
    assert settings.KARE_SAYISI == 8
    assert settings.KARSILASTIR == "out/x.mp4"
    assert settings.YESIL_SEVIYE == 2
    answer(monkeypatch, row("Kırpma"), "bulut", row("Kırpma"), "squash", "")
    assert settings.TONLENDIR is True
    assert settings.MUZIK == "none"
    assert "Kare sayısı" in capsys.readouterr().out


def test_menu_can_quit_without_running(monkeypatch):
    import main as settings

    answer(monkeypatch, "q")
    assert settings._menu() is False


def test_menu_rejects_bad_input(monkeypatch, capsys):
    import main as settings


    answer(monkeypatch, "99", row("Kare sayısı"), "abc", row("Bant sayısı"), "-2",
            row("Eşik (hücre)"), "5", "")
    assert settings._menu() is True
    assert settings.KARE_SAYISI == 53
    out = capsys.readouterr().out
    assert "arası bir numara gir" in out
    assert "sayı olmalı" in out
    assert "negatif olamaz" in out
    assert "0 ile 1 arası" in out


def test_menu_rejects_a_value_outside_the_choices(monkeypatch, capsys):
    import main as settings

    answer(monkeypatch, row("Kırpma"), "bulut", row("Kırpma"), "squash", "")
    assert settings._menu() is True
    assert settings.KIRPMA == "squash"
    assert "seçeneklerden biri olmalı" in capsys.readouterr().out


def test_menu_item_can_be_cleared(monkeypatch):
    import main as settings

    monkeypatch.setattr(settings, "GIF", "out/a.gif")
    answer(monkeypatch, row("GIF"), "yok", "")
    assert settings._menu() is True
    assert settings.GIF is None


def test_menu_keeps_the_value_on_an_empty_answer(monkeypatch):
    import main as settings

    answer(monkeypatch, row("Kare sayısı"), "", "")
    assert settings._menu() is True
    assert settings.KARE_SAYISI == 53


def test_menu_is_skipped_without_a_terminal(monkeypatch):
    import main as settings

    monkeypatch.setattr(settings, "AYAR_SOR", True)
    assert settings._menu_acik() is False


def test_menu_is_skipped_when_asked_to(monkeypatch):
    import main as settings

    monkeypatch.setattr(settings, "AYAR_SOR", False)
    monkeypatch.setattr(settings.sys.stdin, "isatty", lambda: True, raising=False)
    assert settings._menu_acik() is False
