"""Canonical score model shared by import, editing, rendering and the player.

One musical timeline (integer ticks, TPQ per quarter note) drives the audio stems,
bar labels and loops. Pitches keep their spelling as names ("F#4").

Model shape:
  {"title", "tpq", "bars": [{"index","label","ticks","time","key","pickup"}],
   "tempo": [{"tick","bpm"}],
   "parts": {"S"|"A"|"T"|"B": None | {"label","clef","bars": [[{"p": ["G4"], "d": 480, "tie_next": False}]]}},
   "flags": [...]}
"""
from __future__ import annotations

import re
from fractions import Fraction

TPQ = 480
VOICE_PARTS = ("S", "A", "T", "B")
PART_NAMES = {"S": "Soprano", "A": "Alto", "T": "Tenor", "B": "Bass"}
STEPS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NAME_RX = re.compile(r"^([A-G])(##|#|bb|b)?(-?\d)$")
ACC = {None: 0, "#": 1, "##": 2, "b": -1, "bb": -2}


class ModelError(ValueError):
    pass


def name_to_midi(name: str) -> int:
    m = NAME_RX.match(name)
    if not m:
        raise ModelError(f"Not a pitch name: {name!r}")
    step, acc, octave = m.groups()
    return 12 * (int(octave) + 1) + STEPS[step] + ACC[acc]


def shift_name(name: str, octaves: int) -> str:
    if not octaves:
        return name
    m = NAME_RX.match(name)
    if not m:
        raise ModelError(f"Not a pitch name: {name!r}")
    step, acc, octave = m.groups()
    return f"{step}{acc or ''}{int(octave) + octaves}"


# ---- Note tokens used by the Voice Lead editor ---------------------------------
# "G4:1"  quarter note G4      "R:2"   half rest       "C4+E4:1" chord (divisi)
# "D5:2~" tied to next note    durations are in quarter notes: 0.5, 1.5, 2/3 ...

TOKEN_RX = re.compile(r"^(R|[A-G](?:##|#|bb|b)?-?\d(?:\+[A-G](?:##|#|bb|b)?-?\d)*):([0-9]+(?:\.[0-9]+)?(?:/[0-9]+)?)(~?)$")


def parse_bar_tokens(text: str, bar_ticks: int, low: int = 28, high: int = 96) -> list[dict]:
    tokens = (text or "").split()
    if not tokens:
        raise ModelError("A bar needs at least one note or rest (use R:4 for a whole-bar rest in 4/4)")
    if len(tokens) > 64:
        raise ModelError("Too many notes in one bar")
    notes = []
    for tok in tokens:
        m = TOKEN_RX.match(tok)
        if not m:
            raise ModelError(f"Cannot read {tok!r}. Use forms like G4:1, F#3:0.5, R:2, C4+E4:1, D5:2~")
        pitch_part, dur_txt, tie = m.groups()
        try:
            q = Fraction(dur_txt) if "/" in dur_txt else Fraction(dur_txt)
        except (ValueError, ZeroDivisionError) as exc:
            raise ModelError(f"Bad duration in {tok!r}") from exc
        ticks = q * TPQ
        if ticks <= 0 or ticks.denominator != 1:
            raise ModelError(f"Duration in {tok!r} is not on the timing grid")
        pitches = [] if pitch_part == "R" else pitch_part.split("+")
        for p in pitches:
            midi = name_to_midi(p)
            if not low <= midi <= high:
                raise ModelError(f"{p} is outside the playable range for a voice")
        if tie and not pitches:
            raise ModelError("A rest cannot be tied")
        notes.append({"p": pitches, "d": int(ticks), "tie_next": bool(tie)})
    total = sum(n["d"] for n in notes)
    if total != bar_ticks:
        raise ModelError(f"Bar adds up to {Fraction(total, TPQ)} quarters but must be {Fraction(bar_ticks, TPQ)}")
    return notes


def format_bar_tokens(bar: list[dict]) -> str:
    out = []
    for n in bar:
        q = Fraction(n["d"], TPQ)
        if q.denominator == 1:
            dur = str(q.numerator)
        elif q.denominator in (2, 4, 8, 16):
            dur = f"{float(q):g}"
        else:
            dur = f"{q.numerator}/{q.denominator}"
        out.append(f"{'+'.join(n['p']) if n['p'] else 'R'}:{dur}{'~' if n.get('tie_next') else ''}")
    return " ".join(out)


# ---- Timeline -----------------------------------------------------------------

def bar_start_ticks(model: dict) -> list[int]:
    starts, t = [], 0
    for b in model["bars"]:
        starts.append(t)
        t += b["ticks"]
    return starts


def total_ticks(model: dict) -> int:
    return sum(b["ticks"] for b in model["bars"])


def tick_to_seconds(model: dict, tick: int, tempo_factor: float = 1.0) -> float:
    """Seconds at a tick. tempo_factor 0.75 means 75% speed (longer)."""
    secs, prev_tick, bpm = 0.0, 0, model["tempo"][0]["bpm"]
    for seg in model["tempo"][1:]:
        if seg["tick"] >= tick:
            break
        secs += (seg["tick"] - prev_tick) / TPQ * 60.0 / bpm
        prev_tick, bpm = seg["tick"], seg["bpm"]
    secs += (tick - prev_tick) / TPQ * 60.0 / bpm
    return secs / tempo_factor


def timeline(model: dict) -> dict:
    """Bar start times at 100% tempo. Other tempo variants divide by the factor exactly."""
    starts = bar_start_ticks(model)
    return {
        "bars": [{"index": b["index"], "label": b["label"], "pickup": bool(b.get("pickup")),
                  "start": round(tick_to_seconds(model, s), 6)}
                 for b, s in zip(model["bars"], starts)],
        "end": round(tick_to_seconds(model, total_ticks(model)), 6),
    }


def part_events(model: dict, vp: str) -> list[tuple[int, int, int]]:
    """(start_tick, end_tick, midi) per sounding note, with ties merged."""
    part = model["parts"].get(vp)
    if not part:
        return []
    events, open_ties = [], {}
    t = 0
    for bar_def, bar in zip(model["bars"], part["bars"]):
        for n in bar:
            nxt_open = {}
            for p in n["p"]:
                midi = name_to_midi(p)
                start = open_ties.pop(midi, t)
                if n.get("tie_next"):
                    nxt_open[midi] = start
                else:
                    events.append((start, t + n["d"], midi))
            for midi, start in open_ties.items():  # tie to a different pitch: end it
                events.append((start, t, midi))
            open_ties = nxt_open
            t += n["d"]
    for midi, start in open_ties.items():
        events.append((start, t, midi))
    return sorted(events)


def validate_model(model: dict) -> None:
    for vp in VOICE_PARTS:
        part = model["parts"].get(vp)
        if not part:
            continue
        if len(part["bars"]) != len(model["bars"]):
            raise ModelError(f"{PART_NAMES[vp]} has a different number of bars")
        for b, bar in zip(model["bars"], part["bars"]):
            if sum(n["d"] for n in bar) != b["ticks"]:
                raise ModelError(f"{PART_NAMES[vp]} bar {b['label']} does not add up")


def blocking_flags(model: dict) -> list[dict]:
    return [f for f in model.get("flags", []) if f["level"] == "error"]


# ---- Export for score display (music21) ---------------------------------------

def to_musicxml(model: dict) -> bytes:
    """Write the canonical model as MusicXML for the score view, via music21."""
    from music21 import chord, clef, key, meter, metadata, note, stream, tempo, tie

    score = stream.Score()
    score.metadata = metadata.Metadata()
    score.metadata.title = model["title"]
    clefs = {"treble": clef.TrebleClef, "treble8vb": clef.Treble8vbClef, "bass": clef.BassClef}
    for vp in VOICE_PARTS:
        part = model["parts"].get(vp)
        if not part:
            continue
        p = stream.Part()
        p.partName = part["label"]
        p.id = vp
        prev_time, prev_key, carry_tie = None, None, False
        for bi, (b, bar) in enumerate(zip(model["bars"], part["bars"])):
            m = stream.Measure(number=int(b["label"]) if str(b["label"]).isdigit() else bi)
            if bi == 0:
                m.insert(0, clefs[part["clef"]]())
                if vp == VOICE_PARTS[0] or not any(model["parts"].get(x) for x in VOICE_PARTS[:VOICE_PARTS.index(vp)]):
                    m.insert(0, tempo.MetronomeMark(number=model["tempo"][0]["bpm"]))
            if b["time"] != prev_time:
                m.insert(0, meter.TimeSignature(b["time"]))
                prev_time = b["time"]
            if b["key"] != prev_key:
                m.insert(0, key.KeySignature(b["key"]))
                prev_key = b["key"]
            for n in bar:
                ql = n["d"] / TPQ
                if not n["p"]:
                    el = note.Rest(quarterLength=ql)
                elif len(n["p"]) == 1:
                    el = note.Note(n["p"][0].replace("b", "-") if len(n["p"][0]) > 2 else n["p"][0], quarterLength=ql)
                else:
                    el = chord.Chord([x.replace("b", "-") if len(x) > 2 else x for x in n["p"]], quarterLength=ql)
                if n["p"]:
                    if carry_tie and n.get("tie_next"):
                        el.tie = tie.Tie("continue")
                    elif carry_tie:
                        el.tie = tie.Tie("stop")
                    elif n.get("tie_next"):
                        el.tie = tie.Tie("start")
                carry_tie = bool(n["p"]) and n.get("tie_next", False)
                m.append(el)
            if b.get("pickup"):
                m.paddingLeft = (model["bars"][1]["ticks"] - b["ticks"]) / TPQ if len(model["bars"]) > 1 else 0
            p.append(m)
        score.insert(0, p)
    from music21.musicxml.m21ToXml import GeneralObjectExporter
    return GeneralObjectExporter(score).parse()
