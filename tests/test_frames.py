import pytest

from badapple.frames import (
    Bitmap, frame_rate, read_bitmaps, reduce_to_cells, sample, window_for,
)
from conftest import requires_ffmpeg


def solid(width, height, value):
    return Bitmap(width, height, bytes([value]) * (width * height))


def test_squash_keeps_the_whole_frame():
    assert window_for(bytes(240 * 180), (240, 180), "squash") == (0, 0, 240, 180)


def test_crop_takes_the_largest_strip_of_the_grid_aspect():
    """240 wide against a 53x7 grid wants 240 / 7.57 = 32 rows, centred.

    A taller grid keeps more of the frame (240 / (53/21) = 95 rows), and a
    frame taller than the grid aspect is limited by its width instead.
    """
    assert window_for(bytes(240 * 180), (240, 180), "crop") == (0, 74, 240, 32)
    assert window_for(bytes(240 * 180), (240, 180), "crop", grid=(53, 21)) == (0, 42, 240, 95)
    assert window_for(bytes(100 * 400), (100, 400), "crop", grid=(53, 21)) == (0, 180, 100, 40)


def test_unknown_fit_is_rejected():
    with pytest.raises(ValueError):
        window_for(bytes(4), (2, 2), "squashy")


def test_subject_window_follows_the_ink():
    frame = bytearray(240 * 180)
    for y in range(60, 120):
        for x in range(100, 140):
            frame[y * 240 + x] = 255
    x, y, w, h = window_for(bytes(frame), (240, 180), "subject", threshold=0.35, margin=0.08)
    assert 100 <= x + w // 2 <= 140
    assert 60 <= y + h // 2 <= 120
    assert w == h


def test_subject_window_falls_back_when_the_frame_is_empty():
    assert window_for(bytes(240 * 180), (240, 180), "subject") == (0, 0, 240, 180)


def test_subject_window_stays_inside_the_frame():
    frame = bytearray(240 * 180)
    for y in range(0, 180):
        for x in range(0, 60):
            frame[y * 240 + x] = 255
    x, y, w, h = window_for(bytes(frame), (240, 180), "subject")
    assert 0 <= x and x + w <= 240
    assert 0 <= y and y + h <= 180


def test_max_pool_lights_a_cell_that_area_would_grey_out():
    frame = bytearray(8 * 8)
    for y in range(2):
        for x in range(8):
            frame[y * 8 + x] = 255
    box = (0, 0, 8, 8)
    pooled = reduce_to_cells(bytes(frame), 8, 8, box, (2, 2), "max")
    averaged = reduce_to_cells(bytes(frame), 8, 8, box, (2, 2), "area")
    assert pooled == bytes([255, 255, 0, 0])
    assert averaged[0] == 127 and averaged[2] == 0


def test_coverage_pool_reports_the_ink_share_of_a_cell():
    frame = bytearray(8 * 8)
    for y in range(2):
        for x in range(8):
            frame[y * 8 + x] = 255
    box = (0, 0, 8, 8)
    covered = reduce_to_cells(bytes(frame), 8, 8, box, (2, 2), "coverage")
    assert covered == bytes([127, 127, 0, 0])
    dim = reduce_to_cells(bytes([128] * 64), 8, 8, box, (2, 2), "coverage", level=0.9)
    assert dim == bytes(4)

def test_reduce_to_cells_rejects_an_unknown_pool():
    with pytest.raises(ValueError):
        reduce_to_cells(bytes(4), 2, 2, (0, 0, 2, 2), (2, 2), "median")


def test_coverage_is_ink_fraction():
    frame = Bitmap(2, 1, bytes([255, 0]))
    assert frame.coverage(0, 0) == pytest.approx(1.0)
    assert frame.coverage(1, 0) == 0.0
    assert frame.coverage(0, 0, invert=True) == 0.0
    assert frame.coverage(1, 0, invert=True) == pytest.approx(1.0)


def test_bitmap_validates_its_buffer():
    with pytest.raises(ValueError):
        Bitmap(4, 4, b"\x00" * 15)


def test_lookups_outside_the_bitmap_are_refused():
    with pytest.raises(IndexError):
        Bitmap(2, 1, bytes(2)).at(2, 0)
    with pytest.raises(IndexError):
        Bitmap(2, 1, bytes(2)).at(0, 1)


def test_sample_spreads_over_the_film():
    frames = [solid(1, 1, i) for i in range(10)]
    assert [f.at(0, 0) for f in sample(frames, 3)] == [0, 4, 9]


def test_sample_of_a_single_frame():
    assert [f.at(0, 0) for f in sample([solid(1, 1, 7)], 1)] == [7]


def test_sample_cannot_invent_frames():
    with pytest.raises(ValueError):
        sample([solid(1, 1, 0)] * 2, 5)


@requires_ffmpeg
def test_read_bitmaps_samples_across_the_whole_clip(clip):
    frames = read_bitmaps(clip, count=5, size=(53, 7), fit="subject")
    assert len(frames) == 5
    assert all(f.size == (53, 7) for f in frames)


    assert frames[0].at(0, 0) == 255
    assert frames[0].at(52, 6) == 0


@requires_ffmpeg
def test_frames_can_span_several_bands(clip):
    frames = read_bitmaps(clip, count=2, size=(53, 21), bands=3, fit="subject")
    assert all(f.size == (53, 21) for f in frames)
    assert max(frames[0].pixels) == 255


@requires_ffmpeg
def test_squash_keeps_the_frame_off_the_edges(clip):
    frames = read_bitmaps(clip, count=1, size=(53, 7), fit="squash")
    assert frames[0].at(0, 0) == 255
    assert frames[0].at(52, 0) == 0


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_bitmaps(tmp_path / "nope.mp4", count=1, size=(53, 7))


@requires_ffmpeg
def test_start_offset_changes_where_the_frames_come_from(moving):
    whole = read_bitmaps(moving, count=2, size=(53, 7))
    later = read_bitmaps(moving, count=2, size=(53, 7), start=0.5)
    assert len(later) == 2
    assert later[0].pixels != whole[0].pixels


@requires_ffmpeg
def test_start_outside_the_film_is_refused(clip):
    with pytest.raises(ValueError):
        read_bitmaps(clip, count=1, size=(53, 7), start=99.0)
    with pytest.raises(ValueError):
        read_bitmaps(clip, count=1, size=(53, 7), start=-1.0)


@requires_ffmpeg
def test_frame_rate_is_read_from_the_file(clip):
    assert frame_rate(clip) == pytest.approx(5.0, abs=0.01)


@requires_ffmpeg
def test_the_first_sample_is_the_frame_at_the_offset(moving):
    """count must not move where the samples land."""
    one = read_bitmaps(moving, count=1, size=(53, 7), start=0.5)
    many = read_bitmaps(moving, count=4, size=(53, 7), start=0.5)
    assert one[0].pixels == many[0].pixels
