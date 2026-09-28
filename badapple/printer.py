"""The printer: presses greyscale frames into GitHub contribution years.

Each 53x7 calendar band is a page and a frame is the ink.  A frame of 7 rows
fills one band; the usual frame is 7 * bands rows and fills that many
consecutive bands, its top row in the newest of them, so the picture reads
top-down.  Consecutive frames therefore stack into consecutive years, oldest
first, and the whole film becomes a tall column of calendar years.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .calendar import MAX_COUNT, WEEKDAYS, WEEKS, Grid, count_for_level
from .frames import FITS, Bitmap, sample


@dataclass(frozen=True)
class PrintStats:
    years: int
    lit_cells: int
    total_cells: int

    @property
    def ink_ratio(self) -> float:
        return self.lit_cells / self.total_cells if self.total_cells else 0.0


class Printer:
    """Prints a film into a stack of contribution years.

    Parameters
    ----------
    start_year:
        Year of the newest band.  Printing ``n`` frames yields the years
        ``start_year - n + 1 .. start_year``, oldest frame first.
    fit:
        Where a frame sits inside the band: ``squash`` pins it to the top-left
        corner, ``crop`` centres it.  Frames are not rescaled here - use
        :func:`badapple.frames.read_bitmaps` to decode a video at cell size.
    shade:
        Quantise partial cell coverage into the four green levels instead of
        treating every cell above the threshold as solid ink.
    threshold:
        Coverage at which a cell starts counting as ink, 0..1.
    fill_outside:
        Paint the days of the first/last week that belong to the neighbouring
        year as well (a full rectangle; GitHub leaves them empty).
    """

    def __init__(
        self,
        *,
        start_year: int | None = None,
        fit: str = "squash",
        shade: bool = False,
        threshold: float = 0.5,
        invert: bool = False,
        fill_outside: bool = False,
        level: int = 4,
    ) -> None:
        if fit not in FITS:
            raise ValueError(f"fit must be one of {FITS}")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be in 0..1")
        if not 0 <= level <= 4:
            raise ValueError("level must be 0..4")
        self.start_year = start_year or date.today().year
        self.fit = fit
        self.shade = shade
        self.threshold = threshold
        self.invert = invert
        self.fill_outside = fill_outside
        self.level = level
        self.grids: list[Grid] = []

    def _origin(self, frame: Bitmap) -> tuple[int, int]:
        """Top-left cell of a frame inside the band grid."""
        strips = max(1, frame.height // WEEKDAYS)
        rows = frame.height if strips > 1 else WEEKDAYS
        if self.fit != "crop":
            return 0, 0
        return (
            max(0, (WEEKS - frame.width) // 2),
            max(0, (rows - frame.height) // 2),
        )

    def _count(self, frame: Bitmap, x: int, y: int) -> int:
        coverage = frame.coverage(x, y, invert=self.invert)
        if coverage < self.threshold:
            return 0
        if not self.shade:
            return count_for_level(self.level)
        return max(1, min(MAX_COUNT, round(coverage * MAX_COUNT)))

    def _press(self, frame: Bitmap, year: int) -> list[Grid]:
        """Press a frame into consecutive year bands, one per seven rows.

        A frame shorter than a whole number of bands is padded with empty rows.
        """
        strips = max(1, -(-frame.height // WEEKDAYS))
        x0, y0 = self._origin(frame)
        pressed = []
        for strip in range(strips):
            grid = Grid(year + strip, fill_outside=self.fill_outside)
            base = 0 if strips == 1 else strip * WEEKDAYS
            rows = min(WEEKDAYS, max(0, frame.height - base))
            for x in range(frame.width):
                for y in range(rows):
                    grid.set(x0 + x, y0 + y, self._count(frame, x, base + y))
            pressed.append(grid)
        self.grids.extend(pressed)
        return pressed

    def print_frame(self, frame: Bitmap) -> Grid:
        """Press a single frame; returns its newest band, which is ``start_year``."""
        strips = max(1, -(-frame.height // WEEKDAYS))
        year = self.start_year - len(self.grids) - strips + 1
        return self._press(frame, year)[-1]

    def print_film(self, frames: list[Bitmap], years: int | None = None) -> "Printer":
        """Print ``years`` frames sampled evenly across ``frames``.

        A frame taller than seven rows is printed across several consecutive
        year bands, its top row in the newest of them, so the picture reads
        top-down on the poster.
        """
        if not frames:
            raise ValueError("no frames to print")
        if years is None:
            years = len(frames)
        if years < 1:
            raise ValueError("years must be >= 1")
        picked = sample(frames, years)
        per_frame = max(max(1, -(-f.height // WEEKDAYS)) for f in picked)
        first = self.start_year - len(picked) * per_frame + 1
        for offset, frame in enumerate(picked):
            self._press(frame, first + offset * per_frame)
        return self

    def bands(self) -> list[Grid]:
        """Printed years, newest first (the order a profile reads top down)."""
        return list(reversed(self.grids))

    def stats(self) -> PrintStats:
        grids = self.grids
        cells = [cell for grid in grids for cell in grid.cells()]
        return PrintStats(
            years=len(grids),
            lit_cells=sum(1 for cell in cells if cell.count),
            total_cells=len(cells),
        )
