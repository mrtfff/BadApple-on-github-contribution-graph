"""A small chiptune loop, synthesised so the export has a soundtrack.

The point is that the exported MP4 looks like a video someone made, with music
under it.  This is a generated placeholder, not the Bad Apple!! theme: pass
``--music path/to/song.wav`` to use a real track instead.
"""

from __future__ import annotations

import array
import wave
import tempfile
from contextlib import contextmanager
from pathlib import Path

SAMPLE_RATE = 22050

_PROGRESSION = ((9, 0, 4), (5, 0, 4), (0, 0, 4), (7, 0, 4))
_STEPS = 16
_PATTERN = (0, 2, 3, 2, 1, 3, 2, 3, 0, 2, 3, 2, 1, 3, 2, 3)
_BASS_STEPS = (0, 6, 10, 14)


def _square(phase: float, duty: float = 0.5) -> float:
    return 1.0 if (phase % 1.0) < duty else -1.0


def _note(root: int, degree: int) -> float:
    return 440.0 * 2 ** ((root - 9 + degree - 69) / 12)


def synth_loop(path: str | Path, seconds: float, *, bpm: float = 132.0) -> Path:
    """Write ``seconds`` of a two-voice chiptune loop to a mono WAV file.

    The loop is Am - F - C - G, sixteen sixteenth notes per bar.  The lead
    arpeggiates the chord tones (root, third, fifth, octave) and the bass
    doubles the root on every fourth sixteenth.
    """
    if seconds <= 0:
        raise ValueError("seconds must be positive")
    if bpm <= 0:
        raise ValueError("bpm must be positive")
    step = 60.0 / bpm / 4
    total = int(seconds * SAMPLE_RATE)
    lead = array.array("h", bytes(total * 2))
    bass = array.array("h", bytes(total * 2))
    bar = _STEPS * 4 * step

    for bar_index in range(int(seconds / bar) + 1):
        root, _, _ = _PROGRESSION[bar_index % len(_PROGRESSION)]
        for index in range(_STEPS):
            start = int((bar_index * bar + index * step) * SAMPLE_RATE)
            if start >= total:
                break
            length = int(step * SAMPLE_RATE)
            degree = _PATTERN[index]
            _add(lead, start, length, _note(root + 12, degree), 0.22, duty=0.5)
            if index in _BASS_STEPS:
                _add(bass, start, length, _note(root, 0), 0.30, duty=0.25)

    mixed = array.array("h", bytes(total * 2))
    for index in range(total):
        sample = (lead[index] + bass[index]) / 32767.0
        mixed[index] = int(max(-1.0, min(1.0, sample * 0.8)) * 32000)
    return _write(path, mixed)


def _add(track: array.array, start: int, length: int, frequency: float,
         amplitude: float, *, duty: float) -> None:
    """Add one note with a short attack and a gentle decay, so it does not click."""
    attack = max(1, int(0.004 * SAMPLE_RATE))
    phase = 0.0
    step = frequency / SAMPLE_RATE
    for offset in range(min(length, len(track) - start)):
        envelope = min(1.0, offset / attack) * (1.0 - 0.25 * offset / length)
        value = _square(phase, duty) * amplitude * envelope
        track[start + offset] = max(-32000, min(32000, track[start + offset] + int(value * 32000)))
        phase += step


def _write(path: str | Path, samples: array.array) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(samples.tobytes())
    return path


@contextmanager
def resolve_music(choice: str, seconds: float, source: str | Path | None = None):
    """Resolve a music choice to a media file.

    ``none``     - no audio track
    ``source``   - the audio of the film itself, so the export is the real song,
                   in sync by construction (needs ``source``)
    ``generated``- a two-voice chiptune loop in a temporary file, removed again
    anything else is taken as a path to an audio or video file
    """
    if choice == "none":
        yield None
        return
    if choice == "source":
        if source is None:
            raise ValueError("'source' needs the video to take the audio from")
        path = Path(source)
        if not has_audio(path):
            raise ValueError(f"{path} has no audio stream; use --music none or generated")
        yield path
        return
    if choice != "generated":
        path = Path(choice)
        if not path.exists():
            raise FileNotFoundError(path)
        yield path
        return
    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    handle.close()
    path = Path(handle.name)
    try:
        synth_loop(path, seconds)
        yield path
    finally:
        path.unlink(missing_ok=True)


def has_audio(path: str | Path) -> bool:
    """Whether a media file carries an audio stream at all."""
    import subprocess

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=codec_type", "-of", "csv=p=0", str(path)],
        check=False, capture_output=True, text=True,
    )
    return "audio" in probe.stdout
