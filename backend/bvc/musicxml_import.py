"""MusicXML -> source inventory -> explicit S/A/T/B mapping -> canonical score model.

Key rule: a staff, a MusicXML part or a voice number is never assumed to be a
singer's part. The importer lists every (part, staff, voice) stream it finds,
*proposes* a mapping, and records flags for anything ambiguous. A human confirms.
"""
from __future__ import annotations

import re
from fractions import Fraction
from statistics import median

from . import config
from .model import TPQ, VOICE_PARTS, PART_NAMES, name_to_midi, shift_name
from .safe_upload import UploadError, parse_xml_safely

ALTER = {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}
TYPICAL_RANGE = {"S": (60, 84), "A": (53, 77), "T": (48, 69), "B": (40, 64)}  # C4-C6, F3-F5, C3-A4, E2-E4


def _text(el, path, default=None):
    found = el.find(path)
    return found.text.strip() if found is not None and found.text else default


def _flag(level, code, message, part=None, bar=None):
    return {"level": level, "code": code, "message": message, "part": part, "bar": bar}


def inspect(xml: bytes) -> dict:
    """Read a MusicXML document into an inventory of streams and global facts."""
    root = parse_xml_safely(xml)
    title = _text(root, "work/work-title") or _text(root, "movement-title") or "Untitled"
    names = {}
    for sp in root.iter("score-part"):
        names[sp.get("id")] = _text(sp, "part-name", sp.get("id"))

    flags: list[dict] = []
    parts_info = []
    streams: dict[str, dict] = {}
    bars: list[dict] | None = None
    tempo: dict[int, float] = {}
    note_count = 0

    for part in root.findall("part"):
        pid = part.get("id")
        divisions = None
        staves = 1
        clefs: dict[int, dict] = {}
        time_sig = "4/4"
        key = 0
        part_bars = []
        abs_tick = 0
        has_transpose = False
        for mi, measure in enumerate(part.findall("measure")):
            pos = Fraction(0)
            max_pos = Fraction(0)
            last_event_by_voice: dict[str, dict] = {}
            for el in measure:
                tag = el.tag
                if tag == "attributes":
                    d = _text(el, "divisions")
                    if d:
                        divisions = int(d)
                    s = _text(el, "staves")
                    if s:
                        staves = int(s)
                    beats, beat_type = _text(el, "time/beats"), _text(el, "time/beat-type")
                    if beats and beat_type:
                        time_sig = f"{beats}/{beat_type}"
                    f = _text(el, "key/fifths")
                    if f is not None:
                        key = int(f)
                    for c in el.findall("clef"):
                        clefs[int(c.get("number", "1"))] = {
                            "sign": _text(c, "sign"), "line": _text(c, "line"),
                            "octave_change": int(_text(c, "clef-octave-change", "0")),
                        }
                    if el.find("transpose") is not None:
                        has_transpose = True
                elif tag in ("backup", "forward"):
                    dur = _ticks(_text(el, "duration", "0"), divisions)
                    pos = pos - dur if tag == "backup" else pos + dur
                    if pos < 0:
                        raise UploadError(f"Part {pid} bar {mi + 1}: <backup> moves before the bar start")
                    max_pos = max(max_pos, pos)
                elif tag == "direction" or tag == "sound":
                    snd = el if tag == "sound" else el.find("sound")
                    if snd is not None:
                        if snd.get("tempo"):
                            tempo.setdefault(abs_tick + int(pos), float(snd.get("tempo")))
                        if any(snd.get(a) for a in ("dacapo", "dalsegno", "segno", "coda", "tocoda", "fine")):
                            flags.append(_flag("warn", "jumps", "Da capo / segno / coda marks are present. "
                                               "They are NOT expanded; audio follows the written order.", bar=mi))
                elif tag == "barline":
                    if el.find("repeat") is not None or el.find("ending") is not None:
                        flags.append(_flag("warn", "repeats", "Repeat signs or endings are present. They are NOT "
                                           "expanded; audio plays the bars once, in written order.", bar=mi))
                elif tag == "note":
                    if divisions is None:
                        raise UploadError(f"Part {pid}: notes appear before <divisions> is set")
                    if el.find("grace") is not None or el.find("cue") is not None:
                        flags.append(_flag("warn", "grace", "Grace or cue notes were skipped.", bar=mi))
                        continue
                    is_chord = el.find("chord") is not None
                    voice = _text(el, "voice", "1")
                    staff = int(_text(el, "staff", "1"))
                    dur = _ticks(_text(el, "duration", "0"), divisions)
                    pitch = None
                    if el.find("rest") is None:
                        p = el.find("pitch")
                        if p is None:
                            flags.append(_flag("error", "unpitched", "Unpitched note found; cannot render.", bar=mi))
                            continue
                        alter_txt = _text(p, "alter", "0")
                        alter = float(alter_txt)
                        if alter != int(alter) or int(alter) not in ALTER:
                            flags.append(_flag("error", "microtone", "Microtonal alteration is not supported.", bar=mi))
                            alter = 0
                        pitch = f"{_text(p, 'step')}{ALTER[int(alter)]}{_text(p, 'octave')}"
                    ties = {t.get("type") for t in el.findall("tie")}
                    key_ = f"{pid}/{staff}/{voice}"
                    st = streams.setdefault(key_, {
                        "key": key_, "part_id": pid, "part_name": names.get(pid, pid), "staff": staff,
                        "voice": voice, "events": [], "clef": clefs.get(staff, {"sign": "G", "line": "2", "octave_change": 0}),
                    })
                    if is_chord:
                        prev = last_event_by_voice.get(key_)
                        if prev is None:
                            raise UploadError(f"Part {pid} bar {mi + 1}: <chord/> without a preceding note")
                        if pitch:
                            prev["pitches"].append(pitch)
                        prev["tie_next"] = prev["tie_next"] or "start" in ties
                        continue
                    ev = {"bar": mi, "start": int(pos), "dur": int(dur), "pitches": [pitch] if pitch else [],
                          "tie_next": "start" in ties}
                    st["events"].append(ev)
                    last_event_by_voice[key_] = ev
                    note_count += 1
                    pos += dur
                    max_pos = max(max_pos, pos)
            beats, beat_type = (int(x) for x in time_sig.split("/"))
            expected = int(Fraction(beats * 4, beat_type) * TPQ)
            actual = int(max_pos)
            part_bars.append({
                "index": mi, "label": measure.get("number", str(mi + 1)), "ticks": actual or expected,
                "expected_ticks": expected, "time": time_sig, "key": key,
                "pickup": mi == 0 and 0 < actual < expected,
            })
            abs_tick += actual or expected
        parts_info.append({"id": pid, "name": names.get(pid, pid), "staves": staves,
                           "clefs": {str(k): v for k, v in clefs.items()}})
        if has_transpose:
            flags.append(_flag("warn", "transpose", f"Part '{names.get(pid, pid)}' has a <transpose> element; "
                               "written and sounding pitch may differ. Check before mapping.", part=None))
        if bars is None:
            bars = part_bars
        elif [b["ticks"] for b in bars] != [b["ticks"] for b in part_bars]:
            flags.append(_flag("error", "bar-mismatch", f"Part '{names.get(pid, pid)}' has a different bar "
                               "structure from the first part."))
            for a, b in zip(bars, part_bars):
                a["ticks"] = max(a["ticks"], b["ticks"])

    if not bars:
        raise UploadError("The score has no bars")
    if len(bars) > config.MAX_BARS or note_count > config.MAX_NOTES:
        raise UploadError("The score is larger than this pilot supports")
    for b in bars[1:]:
        if b["ticks"] != b["expected_ticks"]:
            flags.append(_flag("warn", "irregular-bar", f"Bar {b['label']} is shorter or longer than its time "
                               "signature.", bar=b["index"]))
    if not tempo:
        tempo[0] = 80.0
        flags.append(_flag("warn", "no-tempo", "No tempo marking found; 80 BPM is assumed. Confirm with the director."))
    tempo_map = [{"tick": t, "bpm": bpm} for t, bpm in sorted(tempo.items())]
    if tempo_map[0]["tick"] != 0:
        tempo_map.insert(0, {"tick": 0, "bpm": tempo_map[0]["bpm"]})
    if len(tempo_map) > 1:
        flags.append(_flag("warn", "tempo-change", "The score changes tempo. Check the rendered audio by ear."))

    stream_list = []
    for st in streams.values():
        pitched = [name_to_midi(p) for e in st["events"] for p in e["pitches"]]
        st["note_count"] = sum(1 for e in st["events"] if e["pitches"])
        st["chord_count"] = sum(1 for e in st["events"] if len(e["pitches"]) > 1)
        st["low"] = min(pitched) if pitched else None
        st["high"] = max(pitched) if pitched else None
        st["median"] = median(pitched) if pitched else None
        st["bars_with_notes"] = sorted({e["bar"] for e in st["events"] if e["pitches"]})
        stream_list.append(st)
    # Shared staves: more than one voice on the same (part, staff).
    by_staff: dict[tuple, list] = {}
    for st in stream_list:
        by_staff.setdefault((st["part_id"], st["staff"]), []).append(st["key"])
    for (pid, staff), keys in by_staff.items():
        if len(keys) > 1:
            flags.append(_flag("warn", "shared-staff", f"Part '{names.get(pid, pid)}' staff {staff} carries "
                               f"{len(keys)} voices ({', '.join(keys)}). Each must be mapped explicitly."))
    return {"title": title, "parts": parts_info, "streams": stream_list, "bars": bars, "tempo": tempo_map,
            "flags": _dedupe(flags)}


def _ticks(duration_txt, divisions) -> Fraction:
    if divisions is None:
        raise UploadError("Duration found before <divisions> is set")
    t = Fraction(int(duration_txt) * TPQ, divisions)
    if t.denominator != 1:
        raise UploadError("Rhythm too fine for this pilot's timing grid")
    return t


def _dedupe(flags):
    seen, out = set(), []
    for f in flags:
        k = (f["code"], f["message"], f["part"])
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


NAME_RULES = [
    (re.compile(r"\b(soprano|sopr?\.?|s)\b", re.I), ["S"]),
    (re.compile(r"\b(alto|a)\b", re.I), ["A"]),
    (re.compile(r"\b(tenor|ten\.?|t)\b", re.I), ["T"]),
    (re.compile(r"\b(bass|bas\.?|b|baritone)\b", re.I), ["B"]),
    (re.compile(r"\b(women|ladies|sa|s\s*a|soprano\s*alto)\b", re.I), ["S", "A"]),
    (re.compile(r"\b(men|gentlemen|tb|t\s*b|tenor\s*bass)\b", re.I), ["T", "B"]),
]


def propose_mapping(inv: dict) -> dict:
    """Suggest a mapping from part names. Never marks anything as confirmed."""
    mapping = {vp: None for vp in VOICE_PARTS}
    streams = inv["streams"]
    for part in inv["parts"]:
        targets = None
        for rx, t in NAME_RULES:
            if rx.search(part["name"]):
                targets = t
        if not targets:
            continue
        pstreams = [s for s in streams if s["part_id"] == part["id"]]
        # Upper voice first: order by staff then by median pitch, highest first.
        pstreams.sort(key=lambda s: (s["staff"], -(s["median"] or 0)))
        for vp, st in zip(targets, pstreams):
            if mapping[vp] is None:
                mapping[vp] = {"part_id": st["part_id"], "staff": st["staff"], "voice": st["voice"],
                               "octave_shift": 0, "confirmed": False, "label": PART_NAMES[vp]}
    for vp in VOICE_PARTS:
        if mapping[vp] is None:
            mapping[vp] = {"part_id": None, "staff": None, "voice": None, "octave_shift": 0,
                           "confirmed": False, "label": PART_NAMES[vp]}
    return mapping


def extract_part(inv: dict, vp: str, m: dict) -> tuple[list | None, list[dict], dict | None]:
    """Return (bars, flags, clef) for one voice part using an explicit mapping entry."""
    flags = []
    if not m or not m.get("part_id"):
        flags.append(_flag("error" if not (m or {}).get("confirmed") else "info", "unmapped",
                           f"{PART_NAMES[vp]} is not mapped to anything in the score.", part=vp))
        return None, flags, None
    sel = [s for s in inv["streams"] if s["part_id"] == m["part_id"]
           and (m.get("staff") is None or s["staff"] == int(m["staff"]))
           and (m.get("voice") is None or s["voice"] == str(m["voice"]))]
    if len(sel) != 1:
        flags.append(_flag("error", "ambiguous-mapping", f"{PART_NAMES[vp]} mapping selects {len(sel)} streams; "
                           "choose one staff and voice.", part=vp))
        return None, flags, None
    st = sel[0]
    shift = int(m.get("octave_shift") or 0)
    bars_out = []
    for b in inv["bars"]:
        evs = sorted((e for e in st["events"] if e["bar"] == b["index"]), key=lambda e: e["start"])
        out, pos = [], 0
        for e in evs:
            if e["start"] < pos:
                flags.append(_flag("error", "overlap", f"Overlapping notes in {PART_NAMES[vp]} bar {b['label']}.",
                                   part=vp, bar=b["index"]))
                continue
            if e["start"] > pos:
                out.append({"p": [], "d": e["start"] - pos, "tie_next": False})
            out.append({"p": [shift_name(p, shift) for p in e["pitches"]], "d": e["dur"], "tie_next": e["tie_next"]})
            pos = e["start"] + e["dur"]
            if len(e["pitches"]) > 1:
                flags.append(_flag("warn", "divisi", f"{PART_NAMES[vp]} has a chord (divisi?) in bar {b['label']}. "
                                   "All notes are played; confirm who sings what.", part=vp, bar=b["index"]))
        if pos > b["ticks"]:
            flags.append(_flag("error", "overflow", f"{PART_NAMES[vp]} bar {b['label']} is longer than the bar.",
                               part=vp, bar=b["index"]))
        elif pos < b["ticks"]:
            out.append({"p": [], "d": b["ticks"] - pos, "tie_next": False})
        if not any(n["p"] for n in out):
            # Silent in this bar while other voices on the same staff sing: possible unison written once.
            neighbours = [s for s in inv["streams"] if s["part_id"] == st["part_id"] and s["staff"] == st["staff"]
                          and s["key"] != st["key"] and b["index"] in s["bars_with_notes"]]
            if neighbours:
                flags.append(_flag("warn", "possible-unison", f"{PART_NAMES[vp]} has no notes in bar {b['label']} "
                                   "but shares a staff with another voice that does. Unison written once?",
                                   part=vp, bar=b["index"]))
        bars_out.append(out)
    clef = st["clef"]
    clef_name = "bass" if clef.get("sign") == "F" else ("treble8vb" if clef.get("octave_change") == -1 else "treble")
    pitched = [name_to_midi(p) for bar in bars_out for n in bar for p in n["p"]]
    if pitched:
        lo, hi = TYPICAL_RANGE[vp]
        med = median(pitched)
        if vp == "T" and clef_name == "treble" and shift == 0 and med >= 62:
            flags.append(_flag("warn", "tenor-octave", "Tenor is in plain treble clef and sits high: it may be "
                               "written an octave above sounding pitch. Set octave shift to -1 if so.", part=vp))
        elif med < lo - 6 or med > hi + 6:
            flags.append(_flag("warn", "range", f"{PART_NAMES[vp]} sits outside its usual range "
                               "(median far from typical). Check octave and mapping.", part=vp))
    if vp == "T" and clef_name == "treble":
        clef_name = "treble8vb" if shift == -1 else "treble"
    return bars_out, flags, {"name": clef_name}


def build_model(inv: dict, mapping: dict) -> dict:
    parts, flags = {}, list(inv["flags"])
    used = {}
    for vp in VOICE_PARTS:
        m = mapping.get(vp) or {}
        if m.get("part_id") and m.get("staff") is not None and m.get("voice") is not None:
            sig = (m["part_id"], int(m["staff"]), str(m["voice"]))
            if sig in used:
                flags.append(_flag("warn", "shared-source", f"{PART_NAMES[vp]} and {PART_NAMES[used[sig]]} are "
                                   "mapped to the same source voice (unison?). Confirm.", part=vp))
            used[sig] = vp
        bars, f, clef = extract_part(inv, vp, m)
        flags += f
        parts[vp] = None if bars is None else {"label": m.get("label") or PART_NAMES[vp], "clef": clef["name"],
                                                "bars": bars}
    mapped_keys = {(m["part_id"], int(m["staff"]), str(m["voice"])) for m in mapping.values()
                   if m and m.get("part_id") and m.get("staff") is not None and m.get("voice") is not None}
    for st in inv["streams"]:
        if (st["part_id"], st["staff"], st["voice"]) not in mapped_keys and st["note_count"]:
            flags.append(_flag("info", "unused-stream", f"Source {st['part_name']} staff {st['staff']} voice "
                               f"{st['voice']} is not mapped to any singer part (accompaniment?)."))
    return {
        "title": inv["title"], "tpq": TPQ,
        "bars": [{k: b[k] for k in ("index", "label", "ticks", "time", "key", "pickup")} for b in inv["bars"]],
        "tempo": inv["tempo"], "parts": parts, "flags": _dedupe(flags),
    }


def public_inventory(inv: dict) -> dict:
    """Inventory without per-note events, for the mapping UI."""
    return {
        "title": inv["title"], "parts": inv["parts"], "flags": inv["flags"],
        "streams": [{k: s[k] for k in ("key", "part_id", "part_name", "staff", "voice", "note_count",
                                       "chord_count", "low", "high", "clef")} for s in inv["streams"]],
    }
