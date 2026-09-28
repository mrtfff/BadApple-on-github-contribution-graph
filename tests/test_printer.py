"""Printer tests.

Column 0 of the 2026 band belongs to December 2025, so ink that should land
inside the year starts at column 1, which is Sunday 4 January 2026.
"""

from datetime import date

import pytest

from badapple.calendar import MAX_COUNT
from badapple.printer import Printer
from conftest import art, grey


def test_ink_lands_on_the_cell_it_was_drawn_in():
    frame = art(".#..", "....", "...#")
    grid = Printer(start_year=2026).print_frame(frame)
    assert grid.get(1, 0) == MAX_COUNT
    assert grid.get(2, 0) == 0
    assert grid.get(3, 2) == MAX_COUNT
    assert grid.total() == 2 * MAX_COUNT


def test_level_picks_the_contribution_bucket():
    assert Printer(start_year=2026, level=1).print_frame(art(".#")).get(1, 0) == 1
    assert Printer(start_year=2026, level=3).print_frame(art(".#")).get(1, 0) == 20


def test_threshold_decides_what_counts_as_ink():
    frame = grey(2, 1, 100)
    loose = Printer(start_year=2026, threshold=0.5, fill_outside=True)
    tight = Printer(start_year=2026, threshold=0.3, fill_outside=True)
    assert loose.print_frame(frame).get(0, 0) == 0
    assert tight.print_frame(frame).get(0, 0) == MAX_COUNT


def test_shade_quantises_partial_coverage():
    grid = Printer(start_year=2026, shade=True, threshold=0.1, fill_outside=True)
    assert 10 <= grid.print_frame(grey(2, 1, 100)).get(0, 0) < 20


def test_invert_flips_which_pixels_are_ink():
    grid = Printer(start_year=2026, invert=True, threshold=0.5, fill_outside=True)
    assert grid.print_frame(grey(2, 1, 100)).get(0, 0) == MAX_COUNT
    assert grid.print_frame(grey(2, 1, 100)).get(1, 0) == MAX_COUNT


def test_crop_centres_a_narrow_frame_in_the_band():
    grid = Printer(start_year=2026, fit="crop").print_frame(art("...#", "...."))
    assert grid.get(27, 2) == MAX_COUNT
    assert grid.get(3, 0) == 0
    assert grid.get(0, 0) == 0
    assert grid.get(52, 0) == 0


def test_squash_places_a_frame_at_the_origin():
    assert Printer(start_year=2026).print_frame(art(".#")).get(1, 0) == MAX_COUNT


def test_days_of_neighbouring_years_stay_empty():
    grid = Printer(start_year=2026).print_frame(grey(53, 7, 255))

    assert grid.get(0, 0) == 0
    assert grid.get_day(date(2026, 1, 4)) == MAX_COUNT
    assert grid.total() == 365 * MAX_COUNT


def test_fill_option_prints_the_whole_week():
    grid = Printer(start_year=2026, fill_outside=True).print_frame(grey(53, 7, 255))
    assert grid.get(0, 0) == MAX_COUNT
    assert grid.total() == 371 * MAX_COUNT


def test_film_is_printed_oldest_year_first():
    printer = Printer(start_year=2026).print_film([art(".#"), art("."), art(".##")], years=3)
    assert [g.year for g in printer.grids] == [2024, 2025, 2026]
    assert [g.year for g in printer.bands()] == [2024, 2025, 2026]
    assert [g.total() for g in printer.grids] == [MAX_COUNT, 0, 2 * MAX_COUNT]


def test_a_tall_frame_reads_top_down():
    """Ink in the frame's first seven rows must land in the band drawn first."""
    rows = ["." + "#" * 52] + ["." * 53] * 20
    printer = Printer(start_year=2026, fill_outside=True)
    printer._press(art(*rows), 2020)
    ordered = printer.bands()
    assert [g.year for g in ordered] == [2020, 2021, 2022]
    assert ordered[0].get(1, 0) == MAX_COUNT      # the top strip, drawn highest
    assert ordered[1].get(1, 0) == 0
    assert ordered[2].get(1, 0) == 0


def test_film_spreads_over_all_given_frames():
    frames = [art("." + "#" * i) for i in range(1, 11)]
    lit = [sum(1 for c in g.cells() if c.count)
           for g in Printer(start_year=2026).print_film(frames, years=3).grids]
    assert lit[0] == 1
    assert 4 <= lit[1] <= 6
    assert lit[2] == 10


def test_single_frames_also_stack_backwards():
    printer = Printer(start_year=2026)
    printer.print_frame(art(".#"))
    printer.print_frame(art(".#"))
    assert [g.year for g in printer.grids] == [2026, 2025]


def test_more_years_than_frames_is_an_error():
    with pytest.raises(ValueError):
        Printer(start_year=2026).print_film([art(".#")], years=2)


def test_empty_film_is_an_error():
    with pytest.raises(ValueError):
        Printer(start_year=2026).print_film([])


def test_stats_count_ink_not_contributions():
    stats = Printer(start_year=2026).print_film([art(".#."), art("...")], years=2).stats()
    assert stats.years == 2
    assert stats.lit_cells == 1
    assert stats.ink_ratio == pytest.approx(1 / 742)


def tall(height_rows=21):
    """A frame with a single inked cell in the first row of each strip."""
    rows = []
    for strip in range(height_rows // 7):
        rows.append("." + "#" + "." * 51)
        rows.extend(["." * 53] * 6)
    return art(*rows)


def test_a_tall_frame_is_printed_across_several_bands():
    printer = Printer(start_year=2026, fill_outside=True)
    printer._press(tall(), 2020)
    assert [g.year for g in printer.grids] == [2020, 2021, 2022]
    assert [g.get(1, 0) for g in printer.grids] == [MAX_COUNT] * 3
    assert printer.grids[0].get(1, 1) == 0


def test_the_top_row_of_a_frame_lands_in_the_newest_band():
    printer = Printer(start_year=2026, fill_outside=True)
    top = printer._press(tall(), 2000)[-1]
    assert top.year == 2002
    assert top.get(1, 0) == MAX_COUNT


def test_print_frame_returns_the_newest_band_of_a_tall_frame():
    printer = Printer(start_year=2026, fill_outside=True)
    assert printer.print_frame(tall()).year == 2026
    assert len(printer.grids) == 3


def test_film_bands_do_not_overlap():
    printer = Printer(start_year=2026, fill_outside=True).print_film([tall(), tall()], years=2)
    assert [g.year for g in printer.grids] == [2021, 2022, 2023, 2024, 2025, 2026]
    assert printer.bands()[0].year == 2021
    assert printer.bands()[-1].year == 2026


def test_a_short_frame_is_padded_into_one_band():
    printer = Printer(start_year=2026, fill_outside=True)
    grid = printer.print_frame(art("." * 53, "#" * 53, "." * 53))
    assert len(printer.grids) == 1
    assert grid.get(10, 1) == MAX_COUNT
    assert grid.get(10, 0) == 0 and grid.get(10, 6) == 0


def test_invalid_options_are_rejected():
    with pytest.raises(ValueError):
        Printer(fit="stretch")
    with pytest.raises(ValueError):
        Printer(threshold=1.5)
    with pytest.raises(ValueError):
        Printer(level=9)
