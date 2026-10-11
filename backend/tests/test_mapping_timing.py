"""Part mapping and musical timing."""
import pytest

from bvc import musicxml_import as mxi
from bvc.model import (ModelError, format_bar_tokens, parse_bar_tokens, part_events, tick_to_seconds, timeline,
                       to_musicxml)
from conftest import fixture_bytes


def load(name):
    inv = mxi.inspect(fixture_bytes(name))
    return inv, mxi.propose_mapping(inv)


def codes(model, part=None):
    return {(f["code"], f["part"], f["bar"]) for f in model["flags"] if part is None or f["part"] == part}


def test_clean_score_proposes_one_stream_per_part_but_never_confirms():
    inv, mapping = load("morning-light-test-piece.musicxml")
    assert {vp: (m["part_id"], m["staff"], m["voice"]) for vp, m in mapping.items()} == {
        "S": ("P1", 1, "1"), "A": ("P2", 1, "1"), "T": ("P3", 1, "1"), "B": ("P4", 1, "1")}
    assert not any(m["confirmed"] for m in mapping.values())
    model = mxi.build_model(inv, mapping)
    assert [f for f in model["flags"] if f["level"] in ("warn", "error")] == []
    assert model["parts"]["T"]["clef"] == "treble8vb"


def test_shared_staves_are_flagged_and_divisi_is_reported_not_resolved():
    inv, mapping = load("morning-light-shared-staves.musicxml")
    assert (mapping["S"]["part_id"], mapping["S"]["voice"]) == ("P1", "1")
    assert (mapping["A"]["part_id"], mapping["A"]["voice"]) == ("P1", "2")
    model = mxi.build_model(inv, mapping)
    found = codes(model)
    assert sum(1 for f in model["flags"] if f["code"] == "shared-staff") == 2
    assert ("divisi", "T", 8) in found
    # Both notes of the chord are kept for the reviewer to decide; nothing is dropped.
    assert model["parts"]["T"]["bars"][8][0]["p"] == ["B3", "D4"]


def test_shared_staff_music_equals_separate_staff_music_except_divisi():
    clean = mxi.build_model(*load("morning-light-test-piece.musicxml"))
    shared = mxi.build_model(*load("morning-light-shared-staves.musicxml"))
    for vp in "SAB":
        assert shared["parts"][vp]["bars"] == clean["parts"][vp]["bars"]
    assert shared["parts"]["T"]["bars"][:8] == clean["parts"]["T"]["bars"][:8]


def test_mapping_a_whole_part_with_two_voices_is_an_error_not_a_guess():
    inv, mapping = load("morning-light-shared-staves.musicxml")
    mapping["S"] = {**mapping["S"], "voice": None}
    model = mxi.build_model(inv, mapping)
    assert ("ambiguous-mapping", "S", None) in codes(model)
    assert model["parts"]["S"] is None


def test_tenor_octave_is_flagged_and_fixed_by_explicit_shift():
    inv, mapping = load("morning-light-tenor-octave.musicxml")
    model = mxi.build_model(inv, mapping)
    assert ("tenor-octave", "T", None) in codes(model)
    mapping["T"]["octave_shift"] = -1
    fixed = mxi.build_model(inv, mapping)
    assert ("tenor-octave", "T", None) not in codes(fixed)
    clean = mxi.build_model(*load("morning-light-test-piece.musicxml"))
    assert fixed["parts"]["T"]["bars"] == clean["parts"]["T"]["bars"]


def test_pickup_bar_and_timeline():
    model = mxi.build_model(*load("morning-light-test-piece.musicxml"))
    assert model["bars"][0]["pickup"] is True and model["bars"][0]["ticks"] == 480
    assert [b["label"] for b in model["bars"]] == [str(i) for i in range(9)]
    tl = timeline(model)
    beat = 60 / 84
    assert tl["bars"][1]["start"] == pytest.approx(beat, abs=1e-6)
    assert tl["bars"][2]["start"] == pytest.approx(5 * beat, abs=1e-6)
    assert tl["end"] == pytest.approx(33 * beat, abs=1e-6)
    # Tempo variants are exact divisions of one timeline.
    assert tick_to_seconds(model, 480 * 33, 0.5) == pytest.approx(2 * 33 * beat)


def test_tempo_change_mid_piece():
    model = mxi.build_model(*load("morning-light-test-piece.musicxml"))
    model["tempo"] = [{"tick": 0, "bpm": 60}, {"tick": 480 * 5, "bpm": 120}]
    assert tick_to_seconds(model, 480 * 5) == pytest.approx(5.0)
    assert tick_to_seconds(model, 480 * 9) == pytest.approx(7.0)


def test_ties_are_merged_into_one_sounding_note():
    model = mxi.build_model(*load("morning-light-test-piece.musicxml"))
    d5 = [e for e in part_events(model, "S") if e[2] == 74 and e[0] >= 480 * 21]
    assert d5[0] == (480 * 23, 480 * 26, 74)  # half note bar 6 + quarter bar 7, one event


def test_note_counts_match_music21():
    from music21 import converter
    model = mxi.build_model(*load("morning-light-test-piece.musicxml"))
    m21 = converter.parse(fixture_bytes("morning-light-test-piece.musicxml").decode())
    for vp, part in zip("SATB", m21.parts):
        ours = sum(1 for bar in model["parts"][vp]["bars"] for n in bar if n["p"])
        assert ours == len(part.recurse().notes)


def test_display_musicxml_round_trips_all_parts():
    model = mxi.build_model(*load("morning-light-test-piece.musicxml"))
    inv2 = mxi.inspect(to_musicxml(model))
    again = mxi.build_model(inv2, mxi.propose_mapping(inv2))
    for vp in "SATB":
        assert again["parts"][vp]["bars"] == model["parts"][vp]["bars"], vp


def test_bar_tokens_parse_and_validate():
    assert parse_bar_tokens("G4:1 R:1 C4+E4:1.5 D5:0.5~", 1920) == [
        {"p": ["G4"], "d": 480, "tie_next": False}, {"p": [], "d": 480, "tie_next": False},
        {"p": ["C4", "E4"], "d": 720, "tie_next": False}, {"p": ["D5"], "d": 240, "tie_next": True}]
    assert format_bar_tokens(parse_bar_tokens("F#3:2 Bb3:2", 1920)) == "F#3:2 Bb3:2"
    for bad in ["G4:1", "H4:4", "G4:4 x", "R:4~", "C9:4", "G4:0"]:
        with pytest.raises(ModelError):
            parse_bar_tokens(bad, 1920)
