"""GitHub contribution graph model: palette, 53x7 year grids, date geometry.

A GitHub contribution year is 53 columns (weeks, Sunday-first) by 7 rows
(weekdays).  Each cell holds a contribution *count*; the count is quantised
into one of five colour levels.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator

WEEKS = 53
WEEKDAYS = 7
CELLS = WEEKS * WEEKDAYS

LEVEL_COLORS = ("#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39")
EMPTY = LEVEL_COLORS[0]

MAX_COUNT = 40


def level_for(count: int) -> int:
    """GitHub's contribution buckets: 0, 1-9, 10-19, 20-39, 40+."""
    if count <= 0:
        return 0
    if count < 10:
        return 1
    if count < 20:
        return 2
    if count < 40:
        return 3
    return 4


def count_for_level(level: int) -> int:
    """Smallest count that lands in ``level`` (inverse of :func:`level_for`)."""
    return {0: 0, 1: 1, 2: 10, 3: 20, 4: MAX_COUNT}[level]



@dataclass(frozen=True)
class Cell:
    date: date
    col: int
    row: int
    count: int
    in_year: bool

    @property
    def level(self) -> int:
        return level_for(self.count)

    @property
    def color(self) -> str:
        return LEVEL_COLORS[self.level]


class Year:
    """Date geometry of one contribution year: 53 Sunday-first weeks.

    The band starts on the Sunday on or before 1 January, so the first and
    last weeks always spill a few days into the neighbouring years.
    """

    def __init__(self, year: int) -> None:
        if not 1 <= year <= 9999:
            raise ValueError(f"year out of range: {year}")
        self.year = year
        first = date(year, 1, 1)
        self.start = first - timedelta(days=(first.weekday() + 1) % 7)

    def date_at(self, col: int, row: int) -> date:
        if not (0 <= col < WEEKS and 0 <= row < WEEKDAYS):
            raise IndexError(f"cell ({col},{row}) outside the grid")
        return self.start + timedelta(days=col * WEEKDAYS + row)

    def position(self, day: date) -> tuple[int, int]:
        offset = (day - self.start).days
        if not 0 <= offset < CELLS:
            raise ValueError(f"{day.isoformat()} is outside {self.year}")
        return divmod(offset, WEEKDAYS)

    def cells(self) -> Iterator[Cell]:
        """Every cell of the band, in reading order, with its count."""
        for col in range(WEEKS):
            for row in range(WEEKDAYS):
                day = self.date_at(col, row)
                yield Cell(day, col, row, 0, day.year == self.year)

    def label_x(self) -> dict[str, int]:
        """Month label -> column, for the month-change ticks above the band."""
        labels: dict[str, int] = {}
        for col in range(WEEKS):
            day = self.date_at(col, 0)
            if day.year == self.year and (col == 0 or day.month != self.date_at(col - 1, 0).month):
                labels[day.strftime("%b")] = col
        return labels


class Grid:
    """A single year of the contribution graph."""

    def __init__(self, year: int, *, fill_outside: bool = False) -> None:
        self.geometry = Year(year)
        self.fill_outside = fill_outside
        self._counts = bytearray(CELLS)

    @property
    def year(self) -> int:
        return self.geometry.year

    def set(self, col: int, row: int, count: int) -> None:
        day = self.geometry.date_at(col, row)
        if day.year != self.year and not self.fill_outside:
            return
        self._counts[col * WEEKDAYS + row] = min(count, 255)

    def set_day(self, day: date, count: int) -> None:
        self.set(*self.geometry.position(day), count)

    def get(self, col: int, row: int) -> int:
        return self._counts[col * WEEKDAYS + row]

    def get_day(self, day: date) -> int:
        return self.get(*self.geometry.position(day))

    def total(self) -> int:
        return sum(self._counts)

    def cells(self) -> Iterator[Cell]:
        for col in range(WEEKS):
            for row in range(WEEKDAYS):
                index = col * WEEKDAYS + row
                day = self.geometry.date_at(col, row)
                yield Cell(day, col, row, self._counts[index], day.year == self.year)
