"""Video -> cell-sized greyscale frames.

The film is decoded exactly once, at probe resolution, and everything else
happens here: finding the subject, choosing the window that is printed, and
reducing that window to the 53 x (7 * bands) cell grid.

Two details matter for silhouette animation like Bad Apple!!:

* the subject is cropped automatically, so a figure that occupies a third of
  the frame is not shrunk to a third of the band;
* cells count their ink rather than their brightness, because a silhouette is
  solid white and an antialiased edge pixel is as bright as the figure itself,
  so averaging greys the shape away and max-pooling inflates the glow around it.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from .calendar import WEEKDAYS, WEEKS

PROBE_WIDTH = 240
PROBE_HEIGHT = 180
FITS = ("squash", "crop", "subject")
POOLS = ("coverage", "max", "area")


@dataclass(frozen=True)
class Bitmap:
    """Greyscale pixels, row-major, ``width * height`` bytes, 0=black..255=white."""

    width: int
    height: int
    pixels: bytes

    def __post_init__(self) -> None:
        if len(self.pixels) != self.width * self.height:
            raise ValueError("pixel count does not match the bitmap size")

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    def coverage(self, x: int, y: int, *, invert: bool = False) -> float:
        """Ink coverage of cell (x, y) in 0..1 (1 = fully lit)."""
        return 1.0 - self.at(x, y) / 255.0 if invert else self.at(x, y) / 255.0

    def at(self, x: int, y: int) -> int:
        if not 0 <= x < self.width or not 0 <= y < self.height:
            raise IndexError(f"({x},{y}) is outside the {self.width}x{self.height} bitmap")
        return self.pixels[y * self.width + x]



def _subject_box(gray: bytes, width: int, height: int, threshold: float,
                 margin: float) -> tuple[int, int, int, int] | None:
    """Square window around the ink, or None when the frame is empty."""
    level = int(threshold * 255)
    x0, x1, y0, y1 = width, -1, height, -1
    for y in range(height):
        row = gray[y * width:(y + 1) * width]
        if max(row) < level:
            continue
        y0, y1 = min(y0, y), y
        for x in range(width):
            if row[x] >= level:
                x0, x1 = min(x0, x), max(x1, x)
    if x1 < x0:
        return None
    cx, cy = (x0 + x1) / 2 + 0.5, (y0 + y1) / 2 + 0.5
    side = max(x1 - x0 + 1, y1 - y0 + 1) / 2 * (1 + 2 * margin)
    side = max(4.0, min(side, width / 2, height / 2))
    left = min(max(cx - side, 0.0), width - 2 * side)
    top = min(max(cy - side, 0.0), height - 2 * side)
    return int(left), int(top), int(round(2 * side)), int(round(2 * side))


def window_for(gray: bytes, size: tuple[int, int], mode: str = "squash", *,
                grid: tuple[int, int] = (WEEKS, WEEKDAYS),
                threshold: float = 0.35, margin: float = 0.08) -> tuple[int, int, int, int]:
    """Region of a ``width x height`` frame to print, as ``(x, y, w, h)``.

    ``squash`` takes the whole frame, ``crop`` takes the largest strip with
    the cell grid's aspect ratio, and ``subject`` takes a square window around
    the ink - which is what lets a figure fill the band instead of a third of
    it.  The subject window is square because the band is 7.5:1, so a square
    crop loses the least of the subject.
    """
    if mode not in FITS:
        raise ValueError(f"fit must be one of {FITS}")
    width, height = size
    if mode == "squash":
        return 0, 0, width, height
    if mode == "subject":
        box = _subject_box(gray, width, height, threshold, margin)
        return box if box is not None else (0, 0, width, height)
    grid_w, grid_h = grid
    if width * grid_h < height * grid_w:
        w, h = width, max(1, round(width * grid_h / grid_w))
    else:
        h, w = height, max(1, round(height * grid_w / grid_h))
    return (width - w) // 2, (height - h) // 2, w, h


def reduce_to_cells(gray: bytes, width: int, height: int, box: tuple[int, int, int, int],
                    size: tuple[int, int], pool: str = "coverage", level: float = 0.35) -> bytes:
    """Reduce a region of a frame to the cell grid.

    ``coverage`` counts the pixels of a cell that are ink and scales that to
    0..255, so the printer's own threshold decides what counts; ``max`` lights
    a cell if any pixel is ink; ``area`` averages the greys.
    """
    if pool not in POOLS:
        raise ValueError(f"pool must be one of {POOLS}")
    x0, y0, bw, bh = box
    tw, th = size
    cut = int(level * 255)
    out = bytearray(tw * th)
    for ty in range(th):
        sy0 = y0 + (ty * bh) // th
        sy1 = y0 + ((ty + 1) * bh) // th
        for tx in range(tw):
            sx0 = x0 + (tx * bw) // tw
            sx1 = x0 + ((tx + 1) * bw) // tw
            best, total, hits, count = 0, 0, 0, 0
            for sy in range(sy0, sy1):
                row = gray[sy * width + sx0: sy * width + sx1]
                count += len(row)
                if pool == "max":
                    best = max(best, max(row))
                else:
                    total += sum(row)
                    hits += sum(1 for value in row if value >= cut)
            if pool == "max":
                out[ty * tw + tx] = best
            elif pool == "area":
                out[ty * tw + tx] = total // max(1, count)
            else:
                out[ty * tw + tx] = 255 * hits // max(1, count)
    return bytes(out)



def duration(path: str | Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError as exc:
        raise ValueError(f"cannot read duration of {path}") from exc


def read_bitmaps(
    path: str | Path,
    *,
    count: int,
    size: tuple[int, int],
    bands: int = 1,
    fit: str = "subject",
    pool: str = "coverage",
    crop_threshold: float = 0.35,
    margin: float = 0.15,
    start: float = 0.0,
) -> list[Bitmap]:
    """Sample ``count`` frames spread evenly over the video from ``start``.

    Each returned frame is ``size`` - normally 53 x (7 * bands) cells.  The fps
    filter rounds to whole frames, so a short film can decode fewer than asked
    for; the last frame is then held to keep the count exact.
    """
    path = Path(path)
    if count < 1:
        raise ValueError("count must be >= 1")
    if bands < 1:
        raise ValueError("bands must be >= 1")
    if not path.exists():
        raise FileNotFoundError(path)
    seconds = duration(path)
    if not 0 <= start < seconds:
        raise ValueError(f"start must be inside the film: 0 <= start < {seconds:.2f}")
    usable = seconds - start
    filters = [f"fps={count / usable:.6f}"] if usable > 0 else []
    filters.append(f"scale={PROBE_WIDTH}:{PROBE_HEIGHT}:flags=area")
    filters.append("format=gray")
    frame_size = PROBE_WIDTH * PROBE_HEIGHT
    command = ["ffmpeg", "-v", "error", "-y"]
    if start > 0:
        command += ["-ss", f"{start:.3f}"]
    command += ["-i", str(path), "-vf", ",".join(filters),
                "-frames:v", str(count), "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    proc = subprocess.run(command, check=False, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.decode(errors='replace').strip()}")
    raw = proc.stdout
    chunks = [raw[i:i + frame_size] for i in range(0, len(raw) - frame_size + 1, frame_size)]
    if not chunks:
        raise RuntimeError(f"no frames decoded from {path}")
    if len(chunks) < count:
        chunks += [chunks[-1]] * (count - len(chunks))
    return [
        Bitmap(size[0], size[1],
               reduce_to_cells(chunk, PROBE_WIDTH, PROBE_HEIGHT,
                               window_for(chunk, (PROBE_WIDTH, PROBE_HEIGHT), fit, grid=size,
                                           threshold=crop_threshold, margin=margin),
                               size, pool, level=crop_threshold))
        for chunk in chunks[:count]
    ]


def sample(frames: list[Bitmap], count: int) -> list[Bitmap]:
    """Pick ``count`` frames spread evenly over ``frames`` (index order)."""
    if count > len(frames):
        raise ValueError(f"cannot sample {count} frames out of {len(frames)}; decode at least {count}")
    if count == len(frames):
        return list(frames)
    if count == 1:
        return [frames[0]]
    last = len(frames) - 1
    return [frames[round(i * last / (count - 1))] for i in range(count)]
