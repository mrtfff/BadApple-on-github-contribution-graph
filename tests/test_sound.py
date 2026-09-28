import json
import subprocess

import pytest

from badapple.cli import main
from badapple.sound import has_audio, resolve_music
from conftest import requires_ffmpeg


def probe(path, entries="codec_type,codec_name,width,height,nb_frames"):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=" + entries, "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(out.stdout)["streams"]


@requires_ffmpeg
def test_has_audio_detects_the_track(clip, av_clip):
    assert has_audio(av_clip) is True
    assert has_audio(clip) is False


def test_music_none_yields_nothing():
    with resolve_music("none", 1.0) as music:
        assert music is None


@requires_ffmpeg
def test_music_source_yields_the_video(av_clip):
    with resolve_music("source", 1.0, source=av_clip) as music:
        assert music == av_clip


def test_music_source_needs_a_source():
    with pytest.raises(ValueError):
        with resolve_music("source", 1.0):
            pass


@requires_ffmpeg
def test_music_source_says_so_when_the_film_is_silent(clip):
    with pytest.raises(ValueError) as hata:
        with resolve_music("source", 1.0, source=clip):
            pass
    assert "no audio stream" in str(hata.value)


def test_generated_music_is_temporary(tmp_path):
    with resolve_music("generated", 0.5) as music:
        assert music is not None and music.exists() and music.suffix == ".wav"
        assert music.stat().st_size > 1000
        keep = music
    assert not keep.exists()


def test_music_path_must_exist():
    with pytest.raises(FileNotFoundError):
        with resolve_music("yok/bu/yok.mp3", 1.0):
            pass


@requires_ffmpeg
def test_compare_uses_the_film_audio(tmp_path, av_clip, capsys):
    out = tmp_path / "compare.mp4"
    assert main(["compare", str(av_clip), "-o", str(out), "--frames", "2", "--fps", "2",
                 "--bands", "1", "--music", "source"]) == 0
    assert "filmin kendi sesi" in capsys.readouterr().err
    streams = probe(out)
    kinds = [s["codec_type"] for s in streams]
    assert kinds == ["video", "audio"]

    assert streams[0]["width"] > 64
    assert streams[0]["nb_frames"] == "2"


@requires_ffmpeg
def test_compare_can_stay_silent(tmp_path, av_clip):
    out = tmp_path / "silent.mp4"
    assert main(["compare", str(av_clip), "-o", str(out), "--frames", "2", "--fps", "2",
                 "--bands", "1", "--music", "none"]) == 0
    assert [s["codec_type"] for s in probe(out)] == ["video"]


@requires_ffmpeg
def test_compare_reports_a_silent_film(tmp_path, clip, capsys):
    out = tmp_path / "nope.mp4"
    assert main(["compare", str(clip), "-o", str(out), "--frames", "2", "--fps", "2",
                 "--bands", "1", "--music", "source"]) == 1
    assert "no audio stream" in capsys.readouterr().err
