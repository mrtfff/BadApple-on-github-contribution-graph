from pathlib import Path

import pytest

from badapple.cli import build_parser, main
from conftest import requires_ffmpeg


@requires_ffmpeg
def test_print_writes_svg(tmp_path, clip):
    out = tmp_path / "grid.svg"
    assert main(["print", str(clip), "-o", str(out), "--frames", "2", "--bands", "3"]) == 0
    svg = out.read_text()
    assert svg.count("<use ") == 2 * 3 * 371
    assert ">2026</text>" in svg and ">2021</text>" in svg


@requires_ffmpeg
def test_print_writes_png(tmp_path, clip):
    from PIL import Image

    out = tmp_path / "grid.png"
    assert main(["print", str(clip), "-o", str(out), "--frames", "2", "--bands", "1",
                 "--scale", "1"]) == 0
    assert Image.open(out).size == (716, 233)


@requires_ffmpeg
def test_print_writes_text_by_default(capsys, clip):
    assert main(["print", str(clip), "--frames", "2", "--bands", "2"]) == 0
    out = capsys.readouterr().out
    assert "2026" in out and "2025" in out
    assert all(len(line) == 53 for line in out.splitlines()[1:8])


@requires_ffmpeg
def test_unknown_extension_falls_back_to_text(tmp_path, clip):
    out = tmp_path / "grid.dat"
    assert main(["print", str(clip), "-o", str(out), "--frames", "1", "--bands", "1"]) == 0
    assert "█" in out.read_text()


@requires_ffmpeg
def test_fill_option_changes_the_printed_area(capsys, clip):
    main(["print", str(clip), "--frames", "1", "--bands", "1", "--fill"])
    filled = capsys.readouterr().out
    main(["print", str(clip), "--frames", "1", "--bands", "1"])
    plain = capsys.readouterr().out
    assert filled.count("█") > plain.count("█")


@requires_ffmpeg
def test_invert_mirrors_the_ink(tmp_path, clip):
    out = tmp_path / "grid.txt"
    main(["print", str(clip), "-o", str(out), "--frames", "1", "--bands", "1", "--invert"])
    assert out.read_text().count("█") > 100


@requires_ffmpeg
def test_stats_report_frames_and_bands(tmp_path, clip, capsys):
    out = tmp_path / "grid.txt"
    main(["print", str(clip), "-o", str(out), "--frames", "2", "--bands", "2", "--stats"])
    err = capsys.readouterr().err
    assert err.startswith("2 frames over 4 bands,")


@requires_ffmpeg
def test_fit_mode_changes_the_rendering(tmp_path, clip):
    subject = tmp_path / "subject.txt"
    squash = tmp_path / "squash.txt"
    main(["print", str(clip), "-o", str(subject), "--frames", "1", "--bands", "1", "--fit", "subject"])
    main(["print", str(clip), "-o", str(squash), "--frames", "1", "--bands", "1", "--fit", "squash"])
    assert subject.read_text() != squash.read_text()


@requires_ffmpeg
def test_play_exports_a_gif(tmp_path, moving, capsys):
    from PIL import Image

    gif = tmp_path / "moving.gif"
    assert main(["play", str(moving), "--frames", "2", "--fps", "2", "--once", "--no-color",
                 "--bands", "2", "--gif", str(gif)]) == 0
    assert "wrote 2 frames" in capsys.readouterr().err
    with Image.open(gif) as image:
        assert image.n_frames == 2
        assert image.size == (716, 233)
        colors = {color for _, color in image.convert("RGB").getcolors(maxcolors=1000)}
        assert (33, 110, 57) in colors


@requires_ffmpeg
def test_play_exports_an_mp4(tmp_path, moving, capsys):
    import json
    import subprocess

    mp4 = tmp_path / "moving.mp4"
    assert main(["play", str(moving), "--frames", "2", "--fps", "4", "--once", "--no-color",
                 "--bands", "1", "--mp4", str(mp4)]) == 0
    assert "wrote 2 frames" in capsys.readouterr().err
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=codec_name,width,height,nb_frames", "-of", "json", str(mp4)],
        check=True, capture_output=True, text=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    assert stream["codec_name"] == "h264"
    assert stream["nb_frames"] == "2"

    assert (stream["width"], stream["height"]) == (716, 122)


def test_export_flag_does_not_shadow_the_input_video(tmp_path, capsys):
    """--mp4 must not overwrite the namespace of the positional video argument."""
    args = build_parser().parse_args(["play", "in.mp4", "--mp4", "out.mp4"])
    assert args.video == Path("in.mp4")
    assert args.mp4 == Path("out.mp4")


def test_missing_video_is_reported(capsys, tmp_path):
    assert main(["print", str(tmp_path / "nope.mp4")]) == 2
    assert "no such file" in capsys.readouterr().err
