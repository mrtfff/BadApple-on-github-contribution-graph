"""The two halves of a comparison must be the same frames.

``read_original`` (left) and ``read_bitmaps`` (right) are separate decoders; if
they pick different moments the picture beside the film is a lie, which is the
one thing this project must not do.
"""

import pytest

from badapple import read_bitmaps
from badapple.compare import read_original
from badapple.frames import frame_indices
from conftest import requires_ffmpeg


def bar_column(image) -> float:
    """Where the bar sits in the image, as a fraction of the width."""
    width, height = image.size
    pixels = image.convert("L").tobytes()
    columns = [x for x in range(width)
               if sum(pixels[y * width + x] for y in range(height)) > height * 32]
    assert columns, "no bar in the frame"
    return (min(columns) + max(columns)) / 2 / width


@requires_ffmpeg
def test_both_halves_sample_the_same_moments(indexed_clip):
    images = read_original(indexed_clip, count=4, height=48)
    frames = read_bitmaps(indexed_clip, count=4, size=(53, 7), fit="squash", pool="max")
    assert len(images) == len(frames) == 4
    for image, frame in zip(images, frames):
        from_left = bar_column(image) * 53
        from_right = [x for x in range(53) if frame.at(x, 3) > 127]
        assert from_right, "no ink in the printed frame"
        assert abs(from_left - sum(from_right) / len(from_right)) < 1.5


@requires_ffmpeg
def test_both_halves_agree_after_an_offset(indexed_clip):
    images = read_original(indexed_clip, count=3, height=48, start=1.0)
    frames = read_bitmaps(indexed_clip, count=3, size=(53, 7), start=1.0, fit="squash",
                          pool="max")
    for image, frame in zip(images, frames):
        from_left = bar_column(image) * 53
        from_right = [x for x in range(53) if frame.at(x, 3) > 127]
        assert from_right
        assert abs(from_left - sum(from_right) / len(from_right)) < 1.5


@requires_ffmpeg
def test_frame_indices_match_the_decoders(indexed_clip):
    first, step = frame_indices(indexed_clip, count=4)
    assert (first, step) == (0, 2)          # 8 frames at 2 fps, four samples -> every other
