import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badapple.frames import Bitmap

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

requires_ffmpeg = pytest.mark.skipif(not FFMPEG or not FFPROBE, reason="ffmpeg/ffprobe not installed")


def art(*rows: str) -> Bitmap:
    """Build a bitmap from ASCII art: '#' is ink, '.' is empty."""
    if any(len(row) != len(rows[0]) for row in rows):
        raise ValueError(f"ragged art: {rows}")
    width = len(rows[0])
    pixels = bytes(255 if c == "#" else 0 for row in rows for c in row)
    return Bitmap(width, len(rows), pixels)


def grey(width: int, height: int, value: int) -> Bitmap:
    return Bitmap(width, height, bytes([value]) * (width * height))


@pytest.fixture(scope="session")
def clip(tmp_path_factory) -> Path:
    """One-second 64x48 clip: a white block covering the top-left quarter."""
    from PIL import Image, ImageDraw

    if not FFMPEG:
        pytest.skip("ffmpeg is not installed")
    media = tmp_path_factory.mktemp("media")
    still = media / "still.png"
    image = Image.new("L", (64, 48), 0)
    ImageDraw.Draw(image).rectangle([0, 0, 31, 23], fill=255)
    image.save(still)
    video = media / "clip.mp4"
    subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-loop", "1", "-i", str(still), "-t", "1", "-r", "5",
         "-c:v", "libx264", "-crf", "0", "-pix_fmt", "yuv420p", str(video)],
        check=True,
    )
    return video


@pytest.fixture(scope="session")
def av_clip(tmp_path_factory) -> Path:
    """A one-second clip that also has a 440 Hz tone, for the audio paths."""
    from PIL import Image, ImageDraw

    if not FFMPEG:
        pytest.skip("ffmpeg is not installed")
    media = tmp_path_factory.mktemp("av")
    still = media / "still.png"
    image = Image.new("L", (64, 48), 0)
    ImageDraw.Draw(image).rectangle([0, 0, 31, 23], fill=255)
    image.save(still)
    video = media / "av.mp4"
    subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-loop", "1", "-i", str(still),
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-t", "1",
         "-c:v", "libx264", "-crf", "0", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(video)],
        check=True,
    )
    return video


@pytest.fixture(scope="session")
def moving(tmp_path_factory) -> Path:
    """A one-second clip whose two frames differ: block left, then block right."""
    from PIL import Image, ImageDraw

    if not FFMPEG:
        pytest.skip("ffmpeg is not installed")
    media = tmp_path_factory.mktemp("moving")
    for index, box in enumerate(([0, 0, 31, 23], [32, 24, 63, 47]), start=1):
        image = Image.new("L", (64, 48), 0)
        ImageDraw.Draw(image).rectangle(box, fill=255)
        image.save(media / f"frame{index}.png")
    video = media / "moving.mp4"
    subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-framerate", "2", "-i", str(media / "frame%d.png"),
         "-c:v", "libx264", "-crf", "0", "-pix_fmt", "yuv420p", str(video)],
        check=True,
    )
    return video


@pytest.fixture(scope="session")
def indexed_clip(tmp_path_factory) -> Path:
    """Eight frames at 2 fps, frame n carrying a white bar in column n."""
    from PIL import Image, ImageDraw

    if not FFMPEG:
        pytest.skip("ffmpeg is not installed")
    media = tmp_path_factory.mktemp("indexed")
    for n in range(8):
        image = Image.new("L", (64, 48), 0)
        ImageDraw.Draw(image).rectangle([n * 8, 0, n * 8 + 7, 47], fill=255)
        image.save(media / f"f{n:02d}.png")
    video = media / "indexed.mp4"
    subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-framerate", "2", "-i", str(media / "f%02d.png"),
         "-c:v", "libx264", "-crf", "0", "-pix_fmt", "yuv420p", str(video)],
        check=True,
    )
    return video
