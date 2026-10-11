"""Generate the ORIGINAL SATB test pieces used by Basilica Voice Coach.

"Morning Light" is a short original chorale written for this project's tests and
demo. It is NOT one of the choir's arrangements and must never be presented as one.
Rights: original test material, free to use within this project.

Three files are written from the same music:
  morning-light-test-piece.musicxml       4 parts, 1 staff and 1 voice each (clean case)
  morning-light-shared-staves.musicxml    2 parts (Women: S+A, Men: T+B), 2 voices per
                                          staff, divisi chord in the tenor's last bar
  morning-light-tenor-octave.musicxml     4 parts, tenor in plain treble clef written an
                                          octave above sounding pitch (octave ambiguity)

Run:  python fixtures/make_fixtures.py
"""
from pathlib import Path

TITLE = "Morning Light (Original Test Piece)"
CREATOR = "Original test piece written for Basilica Voice Coach. Not a choir arrangement."
RIGHTS = "Original test material created for this project. Free to use for testing."
DIV = 4  # divisions per quarter
TEMPO = 84

# Each bar is a list of (pitch or chord or None for rest, quarters, tie) tuples.
# Bar 0 is a one-beat pickup.
S = [
    [("D4", 1, None)],
    [("G4", 1, None), ("G4", 1, None), ("A4", 1, None), ("B4", 1, None)],
    [("C5", 1, None), ("B4", 1, None), ("A4", 2, None)],
    [("B4", 1, None), ("C5", 1, None), ("D5", 1, None), ("B4", 1, None)],
    [("A4", 2, None), ("G4", 2, None)],
    [("B4", 1, None), ("B4", 1, None), ("C5", 1, None), ("D5", 1, None)],
    [("E5", 2, None), ("D5", 2, "start")],
    [("D5", 1, "stop"), ("C5", 1, None), ("B4", 1, None), ("A4", 1, None)],
    [("G4", 4, None)],
]
A = [
    [("B3", 1, None)],
    [("D4", 1, None), ("D4", 1, None), ("E4", 1, None), ("D4", 1, None)],
    [("E4", 1, None), ("D4", 1, None), ("D4", 2, None)],
    [("D4", 1, None), ("E4", 1, None), ("F#4", 1, None), ("G4", 1, None)],
    [("E4", 1, None), ("F#4", 1, None), ("D4", 2, None)],
    [("G4", 1, None), ("G4", 1, None), ("E4", 1, None), ("F#4", 1, None)],
    [("G4", 2, None), ("F#4", 2, None)],
    [("G4", 1, None), ("E4", 1, None), ("D4", 1, None), ("C4", 1, None)],
    [("D4", 4, None)],
]
T = [
    [("G3", 1, None)],
    [("B3", 1, None), ("B3", 1, None), ("C4", 1, None), ("G3", 1, None)],
    [("G3", 1, None), ("G3", 1, None), ("F#3", 2, None)],
    [("G3", 1, None), ("G3", 1, None), ("A3", 1, None), ("D4", 1, None)],
    [("C4", 1, None), ("A3", 1, None), ("B3", 2, None)],
    [("D4", 1, None), ("E4", 1, None), ("E4", 1, None), ("D4", 1, None)],
    [("C4", 1, None), ("B3", 1, None), ("A3", 2, None)],
    [("B3", 1, None), ("C4", 1, None), ("D4", 1, None), ("E4", 1, None)],
    [("B3", 4, None)],
]
B = [
    [("G2", 1, None)],
    [("G2", 1, None), ("G3", 1, None), ("A2", 1, None), ("G2", 1, None)],
    [("C3", 1, None), ("G2", 1, None), ("D3", 2, None)],
    [("G2", 1, None), ("C3", 1, None), ("D3", 1, None), ("G3", 1, None)],
    [("A2", 1, None), ("D3", 1, None), ("G2", 2, None)],
    [("G2", 1, None), ("E3", 1, None), ("A2", 1, None), ("D3", 1, None)],
    [("C3", 2, None), ("D3", 2, None)],
    [("G2", 1, None), ("C3", 1, None), ("G2", 1, None), ("A2", 1, None)],
    [("G2", 4, None)],
]

TYPES = {4: "whole", 3: "half", 2: "half", 1.5: "quarter", 1: "quarter", 0.5: "eighth"}
DOTTED = {3, 1.5}


def shift(pitch: str, octaves: int) -> str:
    return pitch[:-1] + str(int(pitch[-1]) + octaves)


def note_xml(pitches, quarters, tie, voice, staff=None, stem=None):
    out = []
    plist = pitches if isinstance(pitches, list) else [pitches]
    for i, p in enumerate(plist):
        x = ["<note>"]
        if i > 0:
            x.append("<chord/>")
        if p is None:
            x.append("<rest/>")
        else:
            step, rest = p[0], p[1:]
            alter = ""
            if rest.startswith("#"):
                alter, rest = "<alter>1</alter>", rest[1:]
            elif rest.startswith("b"):
                alter, rest = "<alter>-1</alter>", rest[1:]
            x.append(f"<pitch><step>{step}</step>{alter}<octave>{rest}</octave></pitch>")
        x.append(f"<duration>{int(quarters * DIV)}</duration>")
        if tie and p is not None:
            x.append(f'<tie type="{tie}"/>')
        x.append(f"<voice>{voice}</voice><type>{TYPES[quarters]}</type>")
        if quarters in DOTTED:
            x.append("<dot/>")
        if stem:
            x.append(f"<stem>{stem}</stem>")
        if staff:
            x.append(f"<staff>{staff}</staff>")
        if tie and p is not None:
            x.append(f'<notations><tied type="{tie}"/></notations>')
        x.append("</note>")
        out.append("".join(x))
    return "".join(out)


def clef_xml(kind, number=None):
    n = f' number="{number}"' if number else ""
    if kind == "treble":
        return f"<clef{n}><sign>G</sign><line>2</line></clef>"
    if kind == "treble8vb":
        return f"<clef{n}><sign>G</sign><line>2</line><clef-octave-change>-1</clef-octave-change></clef>"
    return f"<clef{n}><sign>F</sign><line>4</line></clef>"


def measure_open(i):
    implicit = ' implicit="yes"' if i == 0 else ""
    return f'<measure number="{i}"{implicit}>'


def attributes(clefs, staves=1):
    st = f"<staves>{staves}</staves>" if staves > 1 else ""
    return (f"<attributes><divisions>{DIV}</divisions><key><fifths>1</fifths></key>"
            f"<time><beats>4</beats><beat-type>4</beat-type></time>{st}{''.join(clefs)}</attributes>")


TEMPO_XML = (f'<direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit>'
             f"<per-minute>{TEMPO}</per-minute></metronome></direction-type><sound tempo=\"{TEMPO}\"/></direction>")


def header(part_list):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<score-partwise version="3.1">'
            f"<work><work-title>{TITLE}</work-title></work>"
            f'<identification><creator type="composer">{CREATOR}</creator><rights>{RIGHTS}</rights></identification>'
            f"<part-list>{part_list}</part-list>")


def single_part(pid, name, bars, clef, with_tempo=False, octave_up=False):
    out = [f'<part id="{pid}">']
    for i, bar in enumerate(bars):
        out.append(measure_open(i))
        if i == 0:
            out.append(attributes([clef_xml(clef)]))
            if with_tempo:
                out.append(TEMPO_XML)
        for p, q, tie in bar:
            if octave_up and p:
                p = shift(p, 1)
            out.append(note_xml(p, q, tie, 1))
        out.append("</measure>")
    out.append("</part>")
    return "".join(out)


def shared_part(pid, upper, lower, clef, with_tempo=False, divisi_last=None):
    out = [f'<part id="{pid}">']
    for i, (ub, lb) in enumerate(zip(upper, lower)):
        out.append(measure_open(i))
        if i == 0:
            out.append(attributes([clef_xml(clef)]))
            if with_tempo:
                out.append(TEMPO_XML)
        length = sum(q for _, q, _ in ub)
        for p, q, tie in ub:
            if divisi_last and i == len(upper) - 1:
                p = divisi_last
            out.append(note_xml(p, q, tie, 1, stem="up"))
        out.append(f"<backup><duration>{int(length * DIV)}</duration></backup>")
        for p, q, tie in lb:
            out.append(note_xml(p, q, tie, 2, stem="down"))
        out.append("</measure>")
    out.append("</part>")
    return "".join(out)


def score_part(pid, name):
    return f'<score-part id="{pid}"><part-name>{name}</part-name></score-part>'


def satb(tenor_octave_up=False):
    pl = "".join(score_part(p, n) for p, n in [("P1", "Soprano"), ("P2", "Alto"), ("P3", "Tenor"), ("P4", "Bass")])
    tenor_clef = "treble" if tenor_octave_up else "treble8vb"
    body = (single_part("P1", "Soprano", S, "treble", with_tempo=True)
            + single_part("P2", "Alto", A, "treble")
            + single_part("P3", "Tenor", T, tenor_clef, octave_up=tenor_octave_up)
            + single_part("P4", "Bass", B, "bass"))
    return header(pl) + body + "</score-partwise>\n"


def shared():
    pl = score_part("P1", "Women") + score_part("P2", "Men")
    body = (shared_part("P1", S, A, "treble", with_tempo=True)
            + shared_part("P2", T, B, "bass", divisi_last=["B3", "D4"]))
    return header(pl) + body + "</score-partwise>\n"


if __name__ == "__main__":
    here = Path(__file__).parent
    for bars in (S, A, T, B):
        assert [sum(q for _, q, _ in b) for b in bars] == [1] + [4] * 8
    (here / "morning-light-test-piece.musicxml").write_text(satb())
    (here / "morning-light-shared-staves.musicxml").write_text(shared())
    (here / "morning-light-tenor-octave.musicxml").write_text(satb(tenor_octave_up=True))
    print("fixtures written")
