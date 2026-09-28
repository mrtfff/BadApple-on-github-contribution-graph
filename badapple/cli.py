"""Command line: ``python3 -m badapple print|play|compare VIDEO``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .calendar import WEEKS, WEEKDAYS
from .check import SAMPLE_FILM, missing_binaries
from .compare import build_frames
from .frames import FITS, POOLS, duration, read_bitmaps
from .player import Player, write_video
from .printer import Printer
from .render import write_output
from .sound import resolve_music

DEFAULT_FRAMES = 53
DEFAULT_BANDS = 3


def _ink_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--fit", choices=FITS, default="subject",
                        help="subject: crop to the ink (default); crop: band-aspect window; "
                             "squash: the whole frame")
    parser.add_argument("--pool", choices=POOLS, default="coverage",
                        help="coverage: share of the cell that is ink (default); "
                             "max: any ink lights it; area: average grey")
    parser.add_argument("--bands", type=int, default=DEFAULT_BANDS,
                        help=f"year bands each frame is printed across (default: {DEFAULT_BANDS})")
    parser.add_argument("--shade", action="store_true",
                        help="quantise partial cell coverage into the four green levels")
    parser.add_argument("--invert", action="store_true", help="treat dark pixels as ink")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="ink coverage needed per cell (0..1)")
    parser.add_argument("--crop-threshold", type=float, default=0.35,
                        help="coverage that counts as the subject when cropping (0..1)")
    parser.add_argument("--margin", type=float, default=0.15,
                        help="breathing room around the cropped subject (0..1)")
    parser.add_argument("--level", type=int, default=4, choices=(0, 1, 2, 3, 4),
                        help="green level used for solid ink (4 = darkest)")


def _printer(args: argparse.Namespace, **overrides) -> Printer:
    return Printer(
        start_year=args.start_year,
        fit=args.fit,
        shade=args.shade,
        threshold=args.threshold,
        invert=args.invert,
        level=args.level,
        fill_outside=overrides.get("fill_outside", False),
    )


def _read(args: argparse.Namespace, count: int):
    return read_bitmaps(
        args.video,
        count=count,
        size=(WEEKS, WEEKDAYS * args.bands),
        bands=args.bands,
        fit=args.fit,
        pool=args.pool,
        crop_threshold=args.crop_threshold,
        margin=args.margin,
        start=getattr(args, "at", 0.0),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="badapple",
        description="Print a video onto GitHub's contribution graph.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    printer_cmd = sub.add_parser("print", help="print the film into a stack of contribution years")
    printer_cmd.add_argument("video", type=Path)
    printer_cmd.add_argument("-o", "--out", type=Path,
                             help="output file: .svg, .png or .txt (default: stdout as text)")
    printer_cmd.add_argument("--frames", type=int, default=DEFAULT_FRAMES,
                             help=f"frames sampled from the film (default: {DEFAULT_FRAMES})")
    printer_cmd.add_argument("--at", type=float, default=0.0,
                             help="start sampling this many seconds into the film")
    printer_cmd.add_argument("--start-year", type=int, default=None,
                             help="year of the newest band (default: this year)")
    printer_cmd.add_argument("--fill", action="store_true",
                             help="also print the days that belong to the neighbouring years")
    printer_cmd.add_argument("--scale", type=int, default=2, help="PNG pixel scale (default: 2)")
    printer_cmd.add_argument("--stats", action="store_true", help="print ink statistics to stderr")
    _ink_options(printer_cmd)

    play_cmd = sub.add_parser(
        "play", help="animate the film in the terminal, optionally saving a GIF or MP4")
    play_cmd.add_argument("video", type=Path)
    play_cmd.add_argument("--fps", type=float, default=15.0)
    play_cmd.add_argument("--frames", type=int, default=None, help="sampled frames (default: fps x duration)")
    play_cmd.add_argument("--zoom", type=int, default=1, help="repeat every cell N times")
    play_cmd.add_argument("--no-color", action="store_true", help="shade blocks instead of 24-bit colour")
    play_cmd.add_argument("--once", action="store_true", help="play a single pass and exit")
    play_cmd.add_argument("--gif", type=Path, help="also save an animated GIF")
    play_cmd.add_argument("--mp4", type=Path, help="also save an H.264/MP4")
    play_cmd.add_argument("--mp4-scale", type=int, default=1)
    play_cmd.add_argument("--crf", type=int, default=18, help="MP4 quality, lower is better")
    play_cmd.add_argument("--gif-scale", type=int, default=1)
    play_cmd.add_argument("--start-year", type=int, default=None,
                          help="year the frames are placed in (default: this year)")
    _ink_options(play_cmd)

    compare_cmd = sub.add_parser(
        "compare", help="write one MP4 with the film and the graph side by side")
    compare_cmd.add_argument("video", type=Path)
    compare_cmd.add_argument("-o", "--out", type=Path, required=True)
    compare_cmd.add_argument("--frames", type=int, default=DEFAULT_FRAMES,
                             help=f"frames sampled from the film (default: {DEFAULT_FRAMES})")
    compare_cmd.add_argument("--fps", type=float, default=12.0)
    compare_cmd.add_argument("--music", default="source",
                             help="source: the film's own audio (default), generated: a "
                                  "chiptune loop, none: silent, or a path to a file")
    compare_cmd.add_argument("--crf", type=int, default=18, help="video quality, lower is better")
    compare_cmd.add_argument("--no-labels", action="store_true")
    compare_cmd.add_argument("--start-year", type=int, default=None)
    _ink_options(compare_cmd)
    return parser


def _run_print(args: argparse.Namespace) -> int:
    frames = _read(args, args.frames)
    printer = _printer(args, fill_outside=args.fill)
    grids = printer.print_film(frames, years=args.frames).bands()
    if args.stats:
        stats = printer.stats()
        print(f"{args.frames} frames over {stats.years} bands, {stats.lit_cells} lit cells of "
              f"{stats.total_cells} ({stats.ink_ratio:.1%} ink)", file=sys.stderr)
    message = write_output(grids, args.out, scale=args.scale)
    if args.out is None:
        sys.stdout.write(message)
    else:
        print(message, file=sys.stderr)
    return 0


def _run_play(args: argparse.Namespace) -> int:
    count = args.frames or max(1, round(args.fps * duration(args.video)))
    player = Player(
        _read(args, count),
        fps=args.fps,
        zoom=args.zoom,
        color=not args.no_color and sys.stdout.isatty(),
        printer=_printer(args, fill_outside=True),
    )
    if args.gif:
        print(f"wrote {player.write_gif(args.gif, scale=args.gif_scale)} frames to {args.gif}",
              file=sys.stderr)
    if args.mp4:
        print(f"wrote {player.write_video(args.mp4, scale=args.mp4_scale, crf=args.crf)} "
              f"frames to {args.mp4}", file=sys.stderr)
    player.run(loop=True, once=args.once)
    return 0


def _run_compare(args: argparse.Namespace) -> int:
    with resolve_music(args.music, duration(args.video), source=args.video) as music:
        player = Player(_read(args, args.frames), fps=args.fps,
                        printer=_printer(args, fill_outside=True))
        written = write_video(
            build_frames(args.video, player, labels=not args.no_labels),
            args.out, fps=args.fps, crf=args.crf, audio=music,
        )
    label = {"generated": "üretilen döngü", "source": "filmin kendi sesi",
             "none": "sessiz"}.get(args.music) or Path(music).name
    print(f"wrote {written} frames to {args.out} with {label}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    eksik = missing_binaries()
    if eksik:
        print(f"error: not found on PATH: {', '.join(eksik)}; install ffmpeg and retry",
              file=sys.stderr)
        return 3
    if not args.video.exists():
        print(f"error: no such file: {args.video}", file=sys.stderr)
        print(f"       any video works; for the demo film:\n"
              f"       curl -L -o {args.video} {SAMPLE_FILM}", file=sys.stderr)
        return 2
    try:
        if args.command == "print":
            return _run_print(args)
        if args.command == "play":
            return _run_play(args)
        return _run_compare(args)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
