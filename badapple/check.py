"""Preflight checks: what has to be present before the tool can do anything.

The two entry points use this to fail with a sentence the reader can act on,
instead of a traceback from deep inside ffmpeg or Pillow.
"""

from __future__ import annotations

import shutil
from pathlib import Path

BINARIES = ("ffmpeg", "ffprobe")
RASTER_SUFFIXES = (".png", ".gif", ".mp4", ".webm", ".mov")
SAMPLE_FILM = ("https://raw.githubusercontent.com/CalvinLoke/bad-apple/master/"
               "BadApple.mp4")


def missing_binaries() -> list[str]:
    """ffmpeg and ffprobe, which everything here shells out to."""
    return [name for name in BINARIES if shutil.which(name) is None]


def has_pillow() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True


def needs_pillow(outputs: list[Path | None]) -> bool:
    """Whether any of these outputs is a raster format, and so needs Pillow."""
    return any(out is not None and out.suffix.lower() in RASTER_SUFFIXES for out in outputs)


def binary_hint() -> str:
    return ("ffmpeg ve ffprobe bulunamadı. Kur: "
            "  sudo apt install ffmpeg   (Debian/Ubuntu)\n"
            "  brew install ffmpeg        (macOS)")


def pillow_hint() -> str:
    return "Pillow kurulu değil:  pip install -r requirements.txt"


def film_hint(expected: str) -> str:
    """How to get a film into the place the settings file expects."""
    hedef = Path(expected)
    return (f"  {hedef} yok. Elindeki herhangi bir videoyu kullanabilirsin: "
            f"menüde 1) Video yolunu yaz.\n"
            f"  Ya da örnek filmi indir (yazarı tarafından bedava dağıtılıyor):\n"
            f"      curl -L -o {hedef} {SAMPLE_FILM}")
