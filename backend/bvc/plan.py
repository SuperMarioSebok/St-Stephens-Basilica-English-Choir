"""Score in, practice plan out.

Reads the canonical score model (model.py) and, for one voice part, works out which bars are
hard and why, then lays the song out as short daily sessions up to a deadline. Everything is
computed from the notes with fixed rules, so the same score always gives the same plan and
every flagged bar states its reason. Nothing here guesses at notes or uses the audio.
"""
from __future__ import annotations

from datetime import date, timedelta

from .model import PART_NAMES, TPQ, VOICE_PARTS, name_to_midi, tick_to_seconds, bar_start_ticks

CHUNK_BARS = 8           # learning unit: about one phrase
HOT_SCORE = 2            # a bar at or above this is a "tricky bar"
MAX_SPOTS = 6
MAJOR_STEPS = (0, 2, 4, 5, 7, 9, 11)

REASONS = {
    "leap": "wide leap",
    "chromatic": "note outside the key",
    "fast": "fast notes",
    "tie": "held over the barline",
    "entry": "entry after a long rest",
    "high": "top of the part's range",
    "low": "bottom of the part's range",
    "divisi": "part divides",
}


def _key_pitch_classes(fifths) -> set[int]:
    try:
        tonic = (int(fifths) * 7) % 12
    except (TypeError, ValueError):
        return set(range(12))  # unknown key: never flag chromatic notes
    return {(tonic + s) % 12 for s in MAJOR_STEPS}


def analyse_part(model: dict, vp: str) -> dict | None:
    """Per-bar difficulty for one part. Returns None when the part is not in the piece."""
    part = model["parts"].get(vp)
    if not part:
        return None
    pitches = [name_to_midi(p) for bar in part["bars"] for n in bar for p in n["p"]]
    if not pitches:
        return None
    low, high = min(pitches), max(pitches)
    wide = high - low >= 16  # range extremes only matter when the part spans well over an octave
    bars, prev_pitch, rest_ticks = [], None, 0
    for bar_def, bar in zip(model["bars"], part["bars"]):
        in_key = _key_pitch_classes(bar_def.get("key"))
        reasons: list[str] = []
        sounding = [n for n in bar if n["p"]]
        for n in bar:
            if not n["p"]:
                rest_ticks += n["d"]
                continue
            top = max(name_to_midi(p) for p in n["p"])
            if prev_pitch is not None and abs(top - prev_pitch) >= 8:  # a sixth or more; fourths and fifths are routine
                reasons.append("leap")
            if prev_pitch is not None and rest_ticks >= 2 * bar_def["ticks"]:
                reasons.append("entry")
            if any(name_to_midi(p) % 12 not in in_key for p in n["p"]):
                reasons.append("chromatic")
            if len(n["p"]) > 1:
                reasons.append("divisi")
            if wide and top >= high - 1:
                reasons.append("high")
            if wide and top <= low + 1:
                reasons.append("low")
            prev_pitch, rest_ticks = top, 0
        if any(n["d"] < TPQ // 2 for n in sounding):
            reasons.append("fast")
        if bar and bar[-1]["p"] and bar[-1].get("tie_next"):
            reasons.append("tie")
        kinds = list(dict.fromkeys(reasons))  # unique, in order found
        weight = {"leap": 2, "chromatic": 2, "entry": 2}
        label = "pickup" if bar_def.get("pickup") else str(bar_def["label"])
        bars.append({"index": bar_def["index"], "label": label, "sounding": bool(sounding),
                     "score": sum(weight.get(k, 1) for k in kinds), "reasons": kinds})
    return {"low": low, "high": high, "bars": bars}


def _hot_spots(bars: list[dict]) -> list[dict]:
    """Group neighbouring tricky bars (a gap of one bar is bridged) and keep the hardest."""
    spots, cur = [], None
    for i, b in enumerate(bars):
        if b["score"] >= HOT_SCORE:
            if cur and i - cur["to"] <= 2:
                cur["to"] = i
            else:
                cur = {"from": i, "to": i}
                spots.append(cur)
    out = []
    for s in spots:
        inside = bars[s["from"]:s["to"] + 1]
        kinds = list(dict.fromkeys(k for b in inside for k in b["reasons"] if b["score"] >= HOT_SCORE))
        total = sum(b["score"] for b in inside)
        out.append({"from_index": inside[0]["index"], "to_index": inside[-1]["index"],
                    "from_label": inside[0]["label"], "to_label": inside[-1]["label"], "score": total,
                    "reasons": [REASONS[k] for k in kinds], "tempo": 50 if total >= 6 else 75})
    out.sort(key=lambda s: -s["score"])
    return sorted(out[:MAX_SPOTS], key=lambda s: s["from_index"])


def _rating(bars: list[dict]) -> str:
    sounding = [b for b in bars if b["sounding"]]
    if not sounding:
        return "easy"
    share = sum(1 for b in sounding if b["score"] >= HOT_SCORE) / len(sounding)
    return "demanding" if share >= 0.35 else "moderate" if share >= 0.12 else "easy"


def _note_name(model: dict, vp: str, midi: int) -> str:
    for bar in model["parts"][vp]["bars"]:
        for n in bar:
            for p in n["p"]:
                if name_to_midi(p) == midi:
                    return p
    return str(midi)


def _chunks(model: dict, bars: list[dict]) -> list[dict]:
    """Split the bars where the part sings into phrases of about CHUNK_BARS bars."""
    starts = bar_start_ticks(model)
    ends = [s + b["ticks"] for s, b in zip(starts, model["bars"])]
    idx = [i for i, b in enumerate(bars) if b["sounding"]]
    if not idx:
        return []
    first, last = idx[0], idx[-1]
    count = last - first + 1
    n = max(1, round(count / CHUNK_BARS))
    size = -(-count // n)
    out = []
    for a in range(first, last + 1, size):
        b = min(a + size - 1, last)
        secs = tick_to_seconds(model, ends[b]) - tick_to_seconds(model, starts[a])
        out.append({"from_index": bars[a]["index"], "to_index": bars[b]["index"], "from_label": bars[a]["label"],
                    "to_label": bars[b]["label"], "seconds": secs, "_a": a, "_b": b})
    return out


def _step(kind: str, text: str, minutes: float, **link) -> dict:
    return {"kind": kind, "text": text, "minutes": max(1, round(minutes)), **link}


def build_plan(model: dict, vp: str, today: date, deadline: date, minutes_per_day: int = 15) -> dict:
    """Practice plan for one part. `deadline` is the day the song must be ready (e.g. the concert)."""
    if vp not in VOICE_PARTS:
        raise ValueError("Unknown part")
    analysis = analyse_part(model, vp)
    overview = []
    for other in VOICE_PARTS:
        a = analysis if other == vp else analyse_part(model, other)
        if a:
            overview.append({"part": other, "rating": _rating(a["bars"]),
                             "tricky_bars": sum(1 for b in a["bars"] if b["score"] >= HOT_SCORE),
                             "range": f"{_note_name(model, other, a['low'])}–{_note_name(model, other, a['high'])}"})
    if analysis is None:
        return {"part": vp, "in_piece": False, "overview": overview, "sessions": [], "hot_spots": []}

    bars = analysis["bars"]
    spots = _hot_spots(bars)
    chunks = _chunks(model, bars)
    song_min = tick_to_seconds(model, sum(b["ticks"] for b in model["bars"])) / 60
    budget = max(5, min(60, minutes_per_day))

    def spot_step(s: dict) -> dict:
        label = s["from_label"] if s["from_index"] == s["to_index"] else f"{s['from_label']}–{s['to_label']}"
        return _step("drill", f"Loop bar {label} at {s['tempo']}% until it is right three times in a row "
                              f"({', '.join(s['reasons'])}).", 3,
                     from_index=s["from_index"], to_index=s["to_index"], tempo=s["tempo"])

    sessions: list[dict] = []
    sessions.append({"title": "Listen and follow", "stage": 1, "steps": [
        _step("listen", "Listen to the whole song with your part louder. Follow the score.", song_min),
        _step("listen", "Listen again and hum your part quietly.", song_min)]})

    # Learn phrase by phrase; several phrases share a session while they fit the daily minutes.
    cur: list[dict] = []
    used = 0.0

    def flush():
        nonlocal cur, used
        if cur:
            sessions.append({"title": "Learn the notes", "stage": 2, "steps": cur})
        cur, used = [], 0.0

    for c in chunks:
        label = f"{c['from_label']}–{c['to_label']}"
        # 3 times at 75% speed, then 2 times at full speed
        slow, full = 3 * c["seconds"] / 0.75 / 60, 2 * c["seconds"] / 60
        steps = [_step("learn", f"Bars {label}: sing with your part alone at 75%, three times.", slow,
                       from_index=c["from_index"], to_index=c["to_index"], tempo=75),
                 _step("learn", f"Bars {label}: twice at full speed with your part louder.", full,
                       from_index=c["from_index"], to_index=c["to_index"], tempo=100)]
        steps += [spot_step(s) for s in spots if c["_a"] <= _pos(bars, s["from_index"]) <= c["_b"]]
        cost = sum(s["minutes"] for s in steps)
        if cur and used + cost > budget:
            flush()
        cur += steps
        used += cost
    flush()

    if spots:
        sessions.append({"title": "Tricky bars", "stage": 2, "steps": [spot_step(s) for s in spots]})
    sessions.append({"title": "Sing it through", "stage": 3, "steps": [
        _step("run", "Sing the whole song with your part louder.", song_min, tempo=100),
        _step("run", "Sing it again with the full choir mix. Note any bar that slips.", song_min, tempo=100)]})
    sessions.append({"title": "Ready check", "stage": 4, "steps": [
        _step("run", "Sing the whole song with the full choir mix, from memory where you can.", song_min, tempo=100),
        _step("record", "Record 60 seconds of your hardest passage and listen back.", 3)]})

    # One session a day from today; the last day before the deadline is the latest practice day.
    days_available = max(0, (deadline - today).days)
    per_day = 1 if days_available >= len(sessions) else -(-len(sessions) // max(1, days_available))
    for i, s in enumerate(sessions):
        s["day"] = (today + timedelta(days=min(i // per_day, max(0, days_available - 1)))).isoformat()
        s["minutes"] = sum(st["minutes"] for st in s["steps"])

    return {
        "part": vp, "part_name": PART_NAMES[vp], "in_piece": True, "title": model.get("title", ""),
        "summary": {"rating": _rating(bars), "bars": len(bars), "sounding_bars": sum(1 for b in bars if b["sounding"]),
                    "range": f"{_note_name(model, vp, analysis['low'])}–{_note_name(model, vp, analysis['high'])}",
                    "song_minutes": round(song_min, 1)},
        "hot_spots": spots, "overview": overview, "sessions": sessions,
        "schedule": {"start": today.isoformat(), "deadline": deadline.isoformat(), "days_available": days_available,
                     "sessions_per_day": per_day, "minutes_per_day": budget,
                     "tight": per_day > 1 or days_available == 0},
    }


def _pos(bars: list[dict], index: int) -> int:
    return next(i for i, b in enumerate(bars) if b["index"] == index)
