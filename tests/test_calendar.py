from datetime import date

import pytest

from badapple.calendar import CELLS, EMPTY, Grid, LEVEL_COLORS, Year, level_for


@pytest.mark.parametrize("count,level", [
    (-1, 0), (0, 0), (1, 1), (9, 1), (10, 2), (19, 2), (20, 3), (39, 3), (40, 4), (400, 4),
])
def test_level_buckets(count, level):
    assert level_for(count) == level


def test_palette_is_githubs():
    assert LEVEL_COLORS == ("#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39")


def test_year_starts_on_the_sunday_before_january_first():
    year = Year(2026)
    assert year.start == date(2025, 12, 28)
    assert year.start.weekday() == 6
    assert Year(2027).start == date(2026, 12, 27)


def test_position_round_trips():
    year = Year(2026)
    for col, row in ((0, 0), (13, 4), (52, 6)):
        assert year.position(year.date_at(col, row)) == (col, row)


def test_cells_cover_the_whole_band_but_only_the_year_is_inside_it():
    year = Year(2026)
    cells = list(year.cells())
    assert len(cells) == CELLS == 371
    assert sum(1 for c in cells if c.in_year) == 365
    assert sum(1 for c in cells if not c.in_year) == 6


def test_leap_year_has_an_extra_day():
    assert sum(1 for c in Year(2024).cells() if c.in_year) == 366


def test_grid_drops_days_belonging_to_other_years():
    grid = Grid(2026)
    grid.set(0, 0, 40)
    grid.set_day(date(2026, 1, 4), 7)
    assert grid.get(0, 0) == 0
    assert grid.get_day(date(2026, 1, 4)) == 7
    assert grid.total() == 7


def test_fill_outside_keeps_the_whole_week():
    grid = Grid(2026, fill_outside=True)
    grid.set(0, 0, 40)
    assert grid.get(0, 0) == 40


def test_empty_cell_colour_is_the_empty_palette_entry():
    grid = Grid(2026)
    cells = {c.date: c for c in grid.cells()}
    assert cells[date(2026, 1, 4)].color == EMPTY


def test_month_labels_name_every_month_once():
    labels = Year(2026).label_x()
    assert len(labels) == 12
    assert labels["Jan"] == 1

    for month, col in labels.items():
        day = Year(2026).date_at(col, 0)
        assert day.strftime("%b") == month
        assert 1 <= day.day <= 7
