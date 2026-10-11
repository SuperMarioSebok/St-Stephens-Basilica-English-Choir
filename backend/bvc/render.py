"""Render practice audio from the canonical model.

Tempo variants are rendered from the SCORE at a different tempo, so pitch never
changes. All stems of one tempo variant are padded/trimmed to the same sample
count and start at sample 0 = tick 0, so the browser can start them together on
one AudioContext clock and they stay locked.
"""
from __future__ import annotations

import io
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from . import config
from .model import TPQ, VOICE_PARTS, part_events, tick_to_seconds, total_ticks


class RenderError(RuntimeError):
    pass


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def midi_bytes(model: dict, part: str, tempo_factor: float, program: int) -> bytes:
    """Type-0 Standard MIDI File for one voice part with the scaled tempo map."""
    events: list[tuple[int, int, bytes]] = []  # (tick, order, data); note-offs before note-ons at same tick
    for seg in model["tempo"]:
        usec = int(round(60_000_000 / (seg["bpm"] * tempo_factor)))
        events.append((seg["tick"], 0, b"\xff\x51\x03" + usec.to_bytes(3, "big")))
    events.append((0, 1, bytes([0xC0, program & 0x7F])))
    for start, end, midi in part_events(model, part):
        events.append((start, 3, bytes([0x90, midi, 84])))
        events.append((end, 2, bytes([0x80, midi, 0])))
    end_tick = total_ticks(model)
    events.append((end_tick, 9, b"\xff\x2f\x00"))
    events.sort(key=lambda e: (e[0], e[1]))
    track, last = bytearray(), 0
    for tick, _, data in events:
        track += _vlq(tick - last) + data
        last = tick
    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, TPQ)
    return header + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def _run_fluidsynth(mid: Path, out: Path) -> None:
    cmd = [config.FLUIDSYNTH, "-ni", "-q", "-R", "0", "-C", "0", "-g", "0.8",
           "-r", str(config.SAMPLE_RATE), "-T", "wav", "-F", str(out), config.SOUNDFONT, str(mid)]
    try:
        # List arguments, no shell: file names never pass through a shell parser.
        res = subprocess.run(cmd, capture_output=True, timeout=config.SUBPROCESS_TIMEOUT, check=False)
    except FileNotFoundError as exc:
        raise RenderError("FluidSynth is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise RenderError("FluidSynth timed out") from exc
    if res.returncode != 0 or not out.exists():
        raise RenderError(f"FluidSynth failed: {res.stderr.decode(errors='replace')[:300]}")


def _read_wav_mono(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        ch, sw, frames = w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(frames)
    if sw != 2:
        raise RenderError("Unexpected sample width from FluidSynth")
    data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data


def wav_bytes(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(config.SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def _fit(samples: np.ndarray, n: int) -> np.ndarray:
    if len(samples) >= n:
        return samples[:n]
    return np.concatenate([samples, np.zeros(n - len(samples), dtype=np.float32)])


def _normalise(x: np.ndarray, peak: float = 0.89) -> np.ndarray:
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    return x if m < 1e-6 else x * (peak / m)


def render_version(model: dict, write) -> list[dict]:
    """Render every stem and mix. `write(name, bytes)` stores a file and returns its relative path.

    Returns asset descriptors: {kind, part, tempo, rel, seconds}.
    """
    if not Path(config.SOUNDFONT).exists():
        raise RenderError(f"SoundFont not found at {config.SOUNDFONT}")
    end_seconds = tick_to_seconds(model, total_ticks(model))
    if end_seconds / (min(config.TEMPO_VARIANTS) / 100) > config.MAX_SCORE_SECONDS:
        raise RenderError("Score is too long to render in this pilot")
    parts = [vp for vp in VOICE_PARTS if model["parts"].get(vp)]
    if not parts:
        raise RenderError("No voice parts are mapped")
    assets = []
    with tempfile.TemporaryDirectory(prefix="bvc-render-") as tmp:
        tmpd = Path(tmp)
        for pct in config.TEMPO_VARIANTS:
            factor = pct / 100
            seconds = end_seconds / factor + config.TAIL_SECONDS
            n = int(round(seconds * config.SAMPLE_RATE))
            stems = {}
            for vp in parts:
                mid, out = tmpd / f"{vp}{pct}.mid", tmpd / f"{vp}{pct}.wav"
                mid.write_bytes(midi_bytes(model, vp, factor, config.GM_PROGRAM))
                _run_fluidsynth(mid, out)
                stems[vp] = _fit(_read_wav_mono(out), n)
            # One gain for all stems keeps their relative balance true to the score.
            peak = max(float(np.max(np.abs(s))) for s in stems.values()) or 1.0
            gain = 0.89 / peak
            for vp in parts:
                rel = write(f"stem-{vp}-{pct}.wav", wav_bytes(stems[vp] * gain))
                assets.append({"kind": "stem", "part": vp, "tempo": pct, "rel": rel, "seconds": n / config.SAMPLE_RATE})
            full = sum(stems.values())
            assets.append({"kind": "mix", "part": "full", "tempo": pct, "seconds": n / config.SAMPLE_RATE,
                           "rel": write(f"mix-full-{pct}.wav", wav_bytes(_normalise(full)))})
            for vp in parts:
                prominent = stems[vp] + config.PROMINENT_OTHERS_GAIN * sum(s for k, s in stems.items() if k != vp)
                assets.append({"kind": "mix", "part": f"{vp}-prominent", "tempo": pct,
                               "seconds": n / config.SAMPLE_RATE,
                               "rel": write(f"mix-{vp}-prominent-{pct}.wav", wav_bytes(_normalise(prominent)))})
    return assets
