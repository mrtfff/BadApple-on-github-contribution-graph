"""Side by side: the film as it is, next to the film as a contribution graph.

The export is one video, so it plays like a video - the comparison format you
find on YouTube - rather than a poster next to a source clip.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterator

from .frames import duration
from .player import Player
from .render import font, render_png

GAP = 8
BACKGROUND = "#ffffff"
LABEL_FILL = "#000000cc"
LABEL_TEXT = "#ffffff"
LABELS = ("ORIGINAL", "CONTRIBUTION GRAPH")


def read_original(path: str | Path, count: int, height: int) -> list:
    """Decode ``count`` frames of the film, scaled to ``height`` pixels."""
    from PIL import Image

    path = Path(path)
    seconds = duration(path)
    size = _size_for(path, height)
    filters = []
    if seconds > 0:
        filters.append(f"fps={count / seconds:.6f}")
    filters.append(f"scale={size[0]}:{size[1]}:flags=area")
    filters.append("format=rgb24")
    frame_bytes = size[0] * size[1] * 3
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf", ",".join(filters),
         "-frames:v", str(count), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=False, capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.decode(errors='replace').strip()}")
    raw = proc.stdout
    images = [
        Image.frombytes("RGB", size, raw[i:i + frame_bytes])
        for i in range(0, len(raw) - frame_bytes + 1, frame_bytes)
    ]
    if not images:
        raise RuntimeError(f"no frames decoded from {path}")
    if len(images) < count:
        images += [images[-1]] * (count - len(images))
    return images[:count]


def _size_for(path: Path, height: int) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    src_w, src_h = (int(value) for value in out.stdout.strip().split(",")[:2])
    return max(1, round(src_w * height / src_h)), height


def compose(original, graph, *, labels: bool = True):
    """Put the two frames next to each other, each labelled.

    The canvas is padded to even dimensions because yuv420p needs them.
    """
    from PIL import Image, ImageDraw

    width = original.width + graph.width + GAP
    height = max(original.height, graph.height)
    width += width % 2
    height += height % 2
    canvas = Image.new("RGB", (width, height), BACKGROUND)
    canvas.paste(original, (0, 0))
    canvas.paste(graph, (original.width + GAP, 0))
    if labels:
        draw = ImageDraw.Draw(canvas)
        text = font(12)
        for x, caption, anchor in ((8, LABELS[0], "lt"), (original.width + GAP + 8, LABELS[1], "lt")):
            box = draw.textbbox((x, 8), caption, font=text)
            draw.rounded_rectangle(
                [(x - 5, 5), (box[2] + 5, box[3] + 5)], radius=4, fill=LABEL_FILL,
            )
            draw.text((x, 8), caption, font=text, fill=LABEL_TEXT, anchor=anchor)
    return canvas


def build_frames(video: str | Path, player: Player, *, labels: bool = True) -> Iterator:
    """Yield one composited frame per film frame, original first."""
    graph_height = render_png(player.grids(player.frames[0]), scale=1).height
    originals = read_original(video, len(player.frames), graph_height)
    for original, frame in zip(originals, player.frames):
        yield compose(original, render_png(player.grids(frame), scale=1), labels=labels)
