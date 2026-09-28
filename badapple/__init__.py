"""Print a video onto GitHub's contribution graph.

    python3 -m badapple print bad_apple.mp4 -o bad_apple.svg
    python3 -m badapple play  bad_apple.mp4
    python3 -m badapple compare bad_apple.mp4 -o compare.mp4
"""

from .calendar import CELLS, EMPTY, LEVEL_COLORS, MAX_COUNT, WEEKS, WEEKDAYS, Cell, Grid, Year, level_for
from .frames import (
    FITS, POOLS, Bitmap, duration, read_bitmaps, reduce_to_cells, sample, window_for,
)
from .player import Player, write_video
from .render import render_png, render_svg, render_text, write_output
from .printer import Printer

__all__ = [
    "CELLS", "EMPTY", "LEVEL_COLORS", "MAX_COUNT", "WEEKS", "WEEKDAYS", "Cell", "Grid", "Year",
    "level_for", "FITS", "POOLS", "Bitmap", "duration", "read_bitmaps",
    "reduce_to_cells", "sample", "window_for",
    "Player", "Printer", "render_png", "render_svg", "render_text", "write_output", "write_video",
]
