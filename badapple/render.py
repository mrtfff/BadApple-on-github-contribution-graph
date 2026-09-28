"""Rendering: reproduce GitHub's contribution graph as SVG, PNG or text."""

from __future__ import annotations

from pathlib import Path

from .calendar import LEVEL_COLORS, WEEKDAYS, WEEKS, Grid, level_for

CELL = 10
GAP = 3
PITCH = CELL + GAP
LEFT = 30
TOP = 15
BAND_W = WEEKS * PITCH - GAP
BAND_H = WEEKDAYS * PITCH - GAP
BAND_STEP = BAND_H + 24
FOOTER = 18
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
UI_COLORS = ("#ffffff", "#444444", "#666666")
TEXT_LABEL = {1: "Mon", 3: "Wed", 5: "Fri"}
SHADE_CHARS = " ░▒▓█"


def palette_image():
    """P-mode swatch image holding every colour the renderers emit."""
    from PIL import Image

    swatch = Image.new("P", (1, 1))
    entries = list(LEVEL_COLORS) + list(UI_COLORS)
    flat: list[int] = []
    for color in entries:
        flat += [int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)]
    swatch.putpalette(flat + [0, 0, 0] * (256 - len(entries)))
    return swatch


def band_height(grids: list[Grid]) -> int:
    return TOP + max(len(grids), 1) * BAND_STEP - (BAND_STEP - BAND_H) + FOOTER


def band_size(grids: list[Grid]) -> tuple[int, int]:
    return LEFT + BAND_W, band_height(grids)


def _defs() -> str:
    return "".join(
        f'<rect id="c{i}" width="{CELL}" height="{CELL}" rx="2"/>' for i in range(5)
    )


def band_svg(grid: Grid, offset_y: int = 0) -> str:
    """One calendar year, positioned at ``offset_y`` from the top of the page.

    Every day gets its own rounded square, exactly like GitHub's own export -
    empty days included, which is what gives the graph its lattice.
    """
    top = TOP + offset_y
    cells = "\n".join(
        f'<use href="#c{cell.level}" xlink:href="#c{cell.level}" '
        f'x="{cell.col * PITCH}" y="{cell.row * PITCH}" fill="{cell.color}"/>'
        for cell in grid.cells()
    )
    labels = "".join(
        f'<text x="{col * PITCH - 2}" y="-5" fill="#444" font-size="9" '
        f'font-family="{FONT}">{month}</text>'
        for month, col in grid.geometry.label_x().items()
    )
    weekdays = "".join(
        f'<text x="-6" y="{row * PITCH + 9}" fill="#444" font-size="9" '
        f'font-family="{FONT}" text-anchor="end">{name}</text>'
        for row, name in TEXT_LABEL.items()
    )
    caption = (
        f'<text x="0" y="{top - 5}" fill="#666" font-size="10" '
        f'font-family="{FONT}">{grid.year}</text>'
    )
    return "\n".join([
        labels,
        weekdays,
        caption,
        f'<g transform="translate({LEFT},{top})">\n{cells}\n</g>',
    ])


def render_svg(grids: list[Grid]) -> str:
    width, height = band_size(grids)
    bands = [band_svg(grid, i * BAND_STEP) for i, grid in enumerate(grids)]
    total = sum(grid.total() for grid in grids)
    footer = (
        f'<text x="{LEFT}" y="{height - 5}" fill="#444" font-size="10" '
        f'font-family="{FONT}">{total} contributions</text>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        f'<rect width="{width}" height="{height}" fill="#ffffff" rx="4"/>\n'
        f"<defs>{_defs()}</defs>\n"
        + "\n".join(bands)
        + f"\n{footer}\n</svg>\n"
    )


def _rgb(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def font(size: int):
    from PIL import ImageFont

    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def render_png(grids: list[Grid], scale: int = 2):
    """Render the stack to a Pillow image (RGB)."""
    from PIL import Image, ImageDraw

    width, height = band_size(grids)
    image = Image.new("RGB", (width * scale, height * scale), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    label = font(9 * scale)
    for index, grid in enumerate(grids):
        top = TOP + index * BAND_STEP
        ox, oy = LEFT * scale, top * scale
        for cell in grid.cells():
            x = ox + cell.col * PITCH * scale
            y = oy + cell.row * PITCH * scale
            draw.rounded_rectangle(
                [x, y, x + CELL * scale - 1, y + CELL * scale - 1],
                radius=2 * scale, fill=_rgb(cell.color),
            )
        for month, col in grid.geometry.label_x().items():
            draw.text((ox + col * PITCH * scale - 2 * scale, top * scale - 13 * scale),
                      month, font=label, fill=(68, 68, 68))
        for row, name in TEXT_LABEL.items():
            width_px = label.getlength(name)
            draw.text((ox - 6 * scale - width_px, top * scale + (row * PITCH + 1) * scale),
                      name, font=label, fill=(68, 68, 68))
        draw.text((0, top * scale - 13 * scale), str(grid.year), font=label, fill=(102, 102, 102))
    total = sum(grid.total() for grid in grids)
    draw.text((LEFT * scale, (height - 14) * scale), f"{total} contributions",
              font=label, fill=(68, 68, 68))
    return image


def render_text(grids: list[Grid]) -> str:
    """Monochrome dump: ' ' for empty, shade blocks for the four green levels."""
    lines: list[str] = []
    for grid in grids:
        lines.append(f"{grid.year}  {grid.total()} contributions")
        for row in range(WEEKDAYS):
            lines.append(
                "".join(SHADE_CHARS[level_for(grid.get(col, row))] for col in range(WEEKS))
            )
        lines.append("")
    return "\n".join(lines)


def write(out: Path, data: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(data, encoding="utf-8")


def write_output(grids: list[Grid], out: str | Path | None, *, scale: int = 2) -> str:
    """Write a poster, picking the format from the suffix: .svg, .png or text.

    ``out=None`` returns the text instead of writing, so the caller decides
    where it goes.  Returns what a caller should report.
    """
    text = render_text(grids) + "\n"
    if out is None:
        return text
    path = Path(out)
    if path.suffix.lower() == ".svg":
        write(path, render_svg(grids))
    elif path.suffix.lower() == ".png":
        path.parent.mkdir(parents=True, exist_ok=True)
        render_png(grids, scale=scale).save(path)
    else:
        write(path, text)
    return f"wrote {path}"
