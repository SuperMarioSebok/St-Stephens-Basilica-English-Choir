"""Rendered audio: synchronized stems, tempo variants that keep pitch."""
import io
import shutil
import wave
from pathlib import Path

import numpy as np
import pytest

from bvc import config, musicxml_import as mxi
from bvc.model import tick_to_seconds
from bvc.render import render_version
from conftest import fixture_bytes

pytestmark = pytest.mark.skipif(shutil.which(config.FLUIDSYNTH) is None or not Path(config.SOUNDFONT).exists(),
                                reason="FluidSynth or SoundFont not installed")


@pytest.fixture(scope="module")
def rendered():
    inv = mxi.inspect(fixture_bytes())
    model = mxi.build_model(inv, mxi.propose_mapping(inv))
    files = {}

    def write(name, data):
        files[name] = data
        return name
    assets = render_version(model, write)
    return model, assets, files


def samples(data: bytes) -> np.ndarray:
    with wave.open(io.BytesIO(data)) as w:
        assert w.getframerate() == config.SAMPLE_RATE and w.getnchannels() == 1
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768


def dominant_hz(x: np.ndarray, start: float, length=0.25, sr=config.SAMPLE_RATE) -> float:
    n = int(length * sr)
    i = int(start * sr)
    seg = x[i:i + n] * np.hanning(n)
    spec = np.abs(np.fft.rfft(seg, n=1 << 16))
    freqs = np.fft.rfftfreq(1 << 16, 1 / sr)
    band = (freqs > 70) & (freqs < 1200)
    return float(freqs[band][np.argmax(spec[band])])


def test_all_files_of_a_tempo_have_identical_length(rendered):
    _, assets, files = rendered
    for pct in config.TEMPO_VARIANTS:
        lengths = {len(samples(files[a["rel"]])) for a in assets if a["tempo"] == pct}
        assert len(lengths) == 1, (pct, lengths)


def test_tempo_variants_scale_duration(rendered):
    model, assets, files = rendered
    body = {a["tempo"]: len(samples(files[a["rel"]])) / config.SAMPLE_RATE - config.TAIL_SECONDS
            for a in assets if a["kind"] == "stem" and a["part"] == "T"}
    assert body[100] == pytest.approx(tick_to_seconds(model, 480 * 33), abs=0.01)
    assert body[75] == pytest.approx(body[100] / 0.75, abs=0.01)
    assert body[50] == pytest.approx(body[100] / 0.5, abs=0.01)


def test_slow_variants_keep_pitch(rendered):
    """Tenor bar 1 beat 1 is B3 (246.9 Hz) at every tempo: slowing never transposes."""
    model, assets, files = rendered
    stems = {a["tempo"]: samples(files[a["rel"]]) for a in assets if a["kind"] == "stem" and a["part"] == "T"}
    for pct, x in stems.items():
        t = tick_to_seconds(model, 480, pct / 100) + 0.05
        assert dominant_hz(x, t) == pytest.approx(246.94, rel=0.015), pct


def test_stems_are_synchronized_to_the_score_timeline():
    """Bar 1 is silenced in every part, so bar 2 beat 1 is a clean onset. Each stem's onset
    must land where the shared timeline says, within 15 ms, at every tempo."""
    import copy
    inv = mxi.inspect(fixture_bytes())
    model = mxi.build_model(inv, mxi.propose_mapping(inv))
    model = copy.deepcopy(model)
    for vp in "SATB":
        model["parts"][vp]["bars"][1] = [{"p": [], "d": 1920, "tie_next": False}]
    files = {}

    def write(name, data):
        files[name] = data
        return name
    for a in render_version(model, write):
        if a["kind"] != "stem":
            continue
        x = samples(files[a["rel"]])
        expected = tick_to_seconds(model, 480 + 1920, a["tempo"] / 100)
        hop = int(0.002 * config.SAMPLE_RATE)
        i0 = int((expected - 0.25) * config.SAMPLE_RATE)
        env = [np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(i0, i0 + config.SAMPLE_RATE, hop)]
        quiet = float(np.median(env[:20]))
        first = next(k for k, e in enumerate(env) if e > max(0.01, 8 * quiet))
        got = (i0 + first * hop) / config.SAMPLE_RATE
        assert got == pytest.approx(expected, abs=0.015), (a["part"], a["tempo"], got, expected)
