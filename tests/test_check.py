import shutil
from pathlib import Path

import pytest

from badapple.check import (
    BINARIES, SAMPLE_FILM, missing_binaries, needs_pillow, film_hint, binary_hint, pillow_hint,
)
from conftest import requires_ffmpeg


def test_needs_pillow_only_for_raster_outputs():
    assert needs_pillow([None, Path("out/poster.svg"), Path("out/poster.txt")]) is False
    assert needs_pillow([Path("out/poster.png")]) is True
    assert needs_pillow([Path("out/clip.mp4"), Path("out/poster.svg")]) is True
    assert needs_pillow([None]) is False


def test_film_hint_mentions_the_path_and_the_command():
    hint = film_hint("assets/bad_apple.mp4")
    assert "assets/bad_apple.mp4" in hint
    assert "curl -L -o assets/bad_apple.mp4" in hint
    assert SAMPLE_FILM in hint


def test_hints_are_usable():
    assert "ffmpeg" in binary_hint()
    assert "ffprobe" in binary_hint()
    assert "pip install" in pillow_hint()


def test_missing_binaries_is_empty_on_a_working_machine():
    if all(shutil.which(name) for name in BINARIES):
        assert missing_binaries() == []


@requires_ffmpeg
def test_missing_binaries_reports_what_is_absent(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert missing_binaries() == list(BINARIES)
