import pytest

from badapple.calendar import LEVEL_COLORS, WEEKS
from badapple.frames import Bitmap
from badapple.printer import Printer
from badapple.render import (
    BAND_W, LEFT, PITCH, SHADE_CHARS, band_size, palette_image, render_png, render_svg,
    render_text,
)
from conftest import art


def lit_grid(**kwargs):
    return Printer(start_year=2026, fill_outside=True, **kwargs).print_frame(art("#..", "..#"))


def test_band_size_follows_the_cell_metrics():
    assert (LEFT + BAND_W, 121) == band_size([lit_grid()])
    assert band_size([lit_grid(), lit_grid()])[1] == 121 + 112


def test_svg_draws_every_day_as_its_own_square():
    svg = render_svg([lit_grid()])
    assert svg.count("<use ") == 371
    assert 'href="#c4" xlink:href="#c4" x="0" y="0" fill="#216e39"' in svg
    assert 'href="#c0" x="676" y="78" fill="#ebedf0"' in svg


def test_svg_has_the_month_and_weekday_labels():
    svg = render_svg([lit_grid()])
    for month in ("Jan", "Jul", "Dec"):
        assert f">{month}</text>" in svg
    for name in ("Mon", "Wed", "Fri"):
        assert f">{name}</text>" in svg
    assert ">2026</text>" in svg


def test_svg_offsets_every_band_downwards():
    printer = Printer(start_year=2026, fill_outside=True)
    printer.print_frame(art("#..", "..#"))
    printer.print_frame(art("...", "..."))
    svg = render_svg(printer.bands())
    assert svg.count('transform="translate(30,15)"') == 1
    assert svg.count('transform="translate(30,127)"') == 1
    assert ">2026</text>" in svg and ">2025</text>" in svg


def test_svg_is_well_formed_xml():
    from xml.etree import ElementTree

    assert ElementTree.fromstring(render_svg([lit_grid()])).tag.endswith("svg")


def test_png_uses_the_github_palette():
    grid = lit_grid()
    image = render_png([grid], scale=2)
    assert image.size == (band_size([grid])[0] * 2, band_size([grid])[1] * 2)
    lit = image.getpixel((LEFT * 2 + 5, 15 * 2 + 5))
    assert lit == (33, 110, 57)
    empty = image.getpixel((LEFT * 2 + 52 * PITCH * 2 + 5, 15 * 2 + 6 * PITCH * 2 + 5))
    assert empty == (235, 237, 240)


def test_text_dump_is_one_line_per_grid_row():
    text = render_text([lit_grid()])
    rows = text.splitlines()
    assert rows[0] == "2026  80 contributions"
    body = [r for r in rows[1:] if r]
    assert len(body) == 7
    assert all(len(r) == WEEKS for r in body)
    assert body[0][0] == SHADE_CHARS[4]
    assert body[0][1] == SHADE_CHARS[0]


def test_palette_image_lists_every_colour_the_renderers_use():
    flat = list(palette_image().getpalette())
    for index, color in enumerate(LEVEL_COLORS):
        assert flat[index * 3:index * 3 + 3] == [
            int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        ]


def test_bands_grow_taller_per_year():
    one = render_png([lit_grid()], scale=1)
    two = render_png([lit_grid(), lit_grid()], scale=1)
    assert two.size[1] == one.size[1] + 112
    assert two.size[0] == one.size[0]


def test_player_renders_four_terminal_rows():
    from badapple.player import Player

    frame = Bitmap(53, 7, bytes([255] * 371))
    player = Player([frame], color=True)
    rendered = player.render(frame)
    assert len(rendered.splitlines()) == 4
    assert rendered.count("▀") == 53 * 4
    assert "\x1b[38;2;33;110;57m" in rendered


def test_player_text_mode_renders_seven_rows():
    from badapple.player import Player

    frame = Bitmap(53, 7, bytes([255] * 371))
    player = Player([frame], color=False)
    lines = player.render(frame).splitlines()
    assert len(lines) == 7
    assert all(set(line) == {SHADE_CHARS[4]} for line in lines)


def test_player_text_mode_follows_the_palette():
    from badapple.player import Player

    half = Bitmap(53, 7, bytes([0] * 53 + [255] * (53 * 6)))
    lines = Player([half], color=False).render(half).splitlines()
    assert lines[0] == " " * 53
    assert lines[1] == SHADE_CHARS[4] * 53
