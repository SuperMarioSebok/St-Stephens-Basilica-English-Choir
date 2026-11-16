"""Score in, practice plan out."""
from datetime import date

from bvc import choir, musicxml_import as mxi, plan
from bvc.model import TPQ
from conftest import fixture_bytes, import_song, login


def fixture_model():
    inv = mxi.inspect(fixture_bytes())
    return mxi.build_model(inv, mxi.propose_mapping(inv))


def tiny_model(tenor_bars, key=0):
    bars = [{"index": i, "label": str(i + 1), "ticks": 4 * TPQ, "time": "4/4", "key": key, "pickup": False}
            for i in range(len(tenor_bars))]
    return {"title": "Tiny", "tpq": TPQ, "bars": bars, "tempo": [{"tick": 0, "bpm": 120}], "flags": [],
            "parts": {"S": None, "A": None, "B": None, "T": {"label": "Tenor", "clef": "treble8vb", "bars": tenor_bars}}}


def n(p, q=1, tie=False):
    return {"p": [p] if p else [], "d": int(q * TPQ), "tie_next": tie}


def test_each_flagged_bar_states_its_reason():
    m = tiny_model([
        [n("C4"), n("D4"), n("E4"), n("F4")],            # stepwise: nothing
        [n("A4"), n("C4"), n("D4"), n("E4")],            # falling sixth
        [n("F#4", 2), n("G4", 2)],                       # F# is outside C major
        [n(None, 4)], [n(None, 4)],                      # two bars rest
        [n("E4", 4)],                                    # entry after the rest
        [n("E4", 0.25), n("F4", 0.25), n("G4", 0.5), n("G4", 3, tie=True)],  # fast notes, tie over the barline
        [n("G4", 4)],
    ])
    bars = plan.analyse_part(m, "T")["bars"]
    assert [b["reasons"] for b in bars[:6]] == [[], ["leap"], ["chromatic"], [], [], ["entry"]]
    assert set(bars[6]["reasons"]) == {"fast", "tie"}
    assert [b["sounding"] for b in bars[3:5]] == [False, False]


def test_plan_covers_every_sung_bar_and_fits_the_deadline():
    p = plan.build_plan(fixture_model(), "T", date(2026, 11, 16), date(2026, 12, 6), 15)
    assert p["in_piece"] and p["summary"]["rating"] in ("easy", "moderate", "demanding")
    assert [s["stage"] for s in p["sessions"]] == sorted(s["stage"] for s in p["sessions"])
    assert p["sessions"][0]["title"] == "Listen and follow" and p["sessions"][-1]["title"] == "Ready check"
    learn = [st for s in p["sessions"] for st in s["steps"] if st["kind"] == "learn" and st["tempo"] == 75]
    covered = [i for st in learn for i in range(st["from_index"], st["to_index"] + 1)]
    sung = [b["index"] for b in plan.analyse_part(fixture_model(), "T")["bars"] if b["sounding"]]
    assert covered == list(range(min(sung), max(sung) + 1))          # no gap, no overlap
    assert all("2026-11-16" <= s["day"] < "2026-12-06" for s in p["sessions"])
    assert not p["schedule"]["tight"]
    assert {o["part"] for o in p["overview"]} == {"S", "A", "T", "B"}
    assert p == plan.build_plan(fixture_model(), "T", date(2026, 11, 16), date(2026, 12, 6), 15)  # deterministic


def test_short_deadline_doubles_up_and_says_so():
    p = plan.build_plan(fixture_model(), "S", date(2026, 12, 4), date(2026, 12, 6), 15)
    assert p["schedule"]["tight"] and p["schedule"]["sessions_per_day"] > 1
    assert {s["day"] for s in p["sessions"]} <= {"2026-12-04", "2026-12-05"}
    late = plan.build_plan(fixture_model(), "S", date(2026, 12, 6), date(2026, 12, 6), 15)
    assert late["schedule"]["tight"] and {s["day"] for s in late["sessions"]} == {"2026-12-06"}


def test_part_missing_from_the_piece():
    p = plan.build_plan(tiny_model([[n("C4", 4)]]), "S", date(2026, 11, 16), date(2026, 12, 6))
    assert p["in_piece"] is False and p["sessions"] == [] and [o["part"] for o in p["overview"]] == ["T"]


def test_endpoint_respects_the_approval_gate(client, monkeypatch):
    monkeypatch.setattr(choir, "today", lambda: date(2026, 11, 16))
    vid = import_song(client)["version_id"]              # a draft, no audio rendered
    r = client.get(f"/api/versions/{vid}/plan", params={"part": "A"})
    assert r.status_code == 200 and r.json()["part"] == "A" and r.json()["schedule"]["days_available"] == 20
    assert client.get(f"/api/versions/{vid}/plan", params={"part": "X"}).status_code == 400
    login(client, "singer")
    assert client.get(f"/api/versions/{vid}/plan").status_code == 404   # singers cannot see drafts
    assert client.get("/api/versions/999/plan").status_code == 404
