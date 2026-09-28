"""Playback and export: the grid as terminal animation, GIF or MP4."""

import io
import subprocess
import sys
import time
from pathlib import Path

from .calendar import LEVEL_COLORS, WEEKDAYS, WEEKS, Grid, level_for
from .frames import Bitmap
from .printer import Printer
from .render import SHADE_CHARS, palette_image, render_png

UPPER_HALF = "▀"


def _sgr(color: str, *, background: bool) -> str:
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    return f"\x1b[{48 if background else 38};2;{r};{g};{b}m"


class Player:
    """Plays frames through the GitHub grid: half blocks in colour, shades as text.

    Seven grid rows fit into four terminal rows by drawing two cells per row:
    the upper cell is the foreground of a half block, the lower one its
    background.
    """

    def __init__(
        self,
        frames: list[Bitmap],
        *,
        fps: float = 15.0,
        zoom: int = 1,
        color: bool = True,
        printer: Printer | None = None,
    ) -> None:
        if not frames:
            raise ValueError("no frames to play")
        if fps <= 0:
            raise ValueError("fps must be positive")
        if zoom < 1:
            raise ValueError("zoom must be >= 1")
        self.frames = frames
        self.fps = fps
        self.zoom = zoom
        self.color = color
        self.printer = printer or Printer(fill_outside=True)
        self._codes: dict[str, str] = {}

    def grids(self, frame: Bitmap) -> list[Grid]:
        """One frame pressed onto throwaway years, ignoring year boundaries."""
        printer = Printer(
            start_year=self.printer.start_year,
            fit=self.printer.fit,
            shade=self.printer.shade,
            threshold=self.printer.threshold,
            invert=self.printer.invert,
            fill_outside=True,
            level=self.printer.level,
        )
        return printer._press(frame, printer.start_year)

    def _paint(self, color: str, background: bool) -> str:
        code = self._codes.get(color)
        if code is None:
            code = _sgr(color, background=background)
            self._codes[color] = code
        return code

    def render(self, frame: Bitmap) -> str:
        rows = [(grid, row) for grid in self.grids(frame) for row in range(WEEKDAYS)]
        if not self.color:
            return "\n".join(
                "".join(SHADE_CHARS[level_for(grid.get(col, row))] * self.zoom for col in range(WEEKS))
                for grid, row in rows
            )
        lines = []
        for start in range(0, len(rows), 2):
            parts = []
            for col in range(WEEKS):
                top = rows[start][0].get(col, rows[start][1])
                bottom = rows[start + 1][0].get(col, rows[start + 1][1]) if start + 1 < len(rows) else 0
                parts.append(
                    self._paint(LEVEL_COLORS[level_for(top)], False)
                    + self._paint(LEVEL_COLORS[level_for(bottom)], True)
                    + UPPER_HALF * self.zoom
                )
            parts.append("\x1b[0m")
            lines.append("".join(parts))
        return "\n".join(lines)

    def run(self, stream=None, *, loop: bool = True, once: bool = False) -> None:
        stream = stream or sys.stdout
        tty = hasattr(stream, "isatty") and stream.isatty()
        if tty:
            stream.write("\x1b[2J")
        start = time.monotonic()
        while True:
            for frame in self.frames:
                stream.write("\x1b[H" if tty else "")
                stream.write(self.render(frame) + "\n" + ("" if tty else "\n"))
            stream.flush()
            if once or not loop:
                return
            time.sleep(max(0.0, len(self.frames) / self.fps - (time.monotonic() - start)))
            start = time.monotonic()

    def write_gif(self, path: str | Path, scale: int = 1) -> int:
        from PIL import Image

        palette = palette_image()
        frames = [
            render_png(self.grids(frame), scale=scale).quantize(palette=palette, dither=Image.Dither.NONE)
            for frame in self.frames
        ]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(
            path,
            save_all=True,
            append_images=frames[1:],
            duration=int(1000 / self.fps),
            loop=0,
            disposal=2,
            optimize=False,
        )
        return len(frames)


    def write_video(self, path: str | Path, scale: int = 1, crf: int = 18,
                    fps: float | None = None, audio: str | Path | None = None) -> int:
        """Encode the same frames as an H.264/MP4, one movie frame each."""
        return write_video(
            (render_png(self.grids(frame), scale=scale) for frame in self.frames),
            path, fps=self.fps if fps is None else fps, crf=crf, audio=audio,
        )


def write_video(images, path: str | Path, *, fps: float = 12.0, crf: int = 18,
                audio: str | Path | None = None, bitrate: str = "160k") -> int:
    """Pipe PIL images into ffmpeg and write an H.264 file.

    MP4 needs even dimensions for yuv420p, so the frame is padded by at most
    one pixel rather than refusing the odd heights the band layout produces.
    An ``audio`` file (which may be a video) is looped and mixed in; the
    streams are mapped explicitly so a video input cannot displace the frames.
    """
    if fps <= 0:
        raise ValueError("fps must be positive")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", f"{fps:g}",
               "-i", "-"]
    if audio is not None:
        command += ["-stream_loop", "-1", "-i", str(audio)]
    command += ["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2:0:0:color=white",
                "-map", "0:v", "-c:v", "libx264", "-preset", "medium",
                "-crf", str(crf), "-pix_fmt", "yuv420p"]
    if audio is not None:
        command += ["-map", "1:a:0", "-c:a", "aac", "-b:a", bitrate, "-shortest"]
    command += ["-movflags", "+faststart", str(path)]
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    written = 0
    buffer = io.BytesIO()
    try:
        for image in images:
            buffer.seek(0)
            buffer.truncate()
            image.save(buffer, format="PNG")
            proc.stdin.write(buffer.getvalue())
            written += 1
    except BrokenPipeError:
        pass
    finally:
        proc.stdin.close()
    errors = proc.stderr.read().decode(errors="replace").strip()
    proc.stderr.close()
    if proc.wait():
        raise RuntimeError(f"ffmpeg failed: {errors or 'unknown error'}")
    if not written:
        raise RuntimeError("no frames to encode")
    return written
