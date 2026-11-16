"""Concert dashboard: seeded data, personal progress, RSVP and knowledge-base search."""
from datetime import date

from bvc import choir, db
from conftest import login


def test_seed_is_idempotent_and_dashboard_lists_concert_data(client, monkeypatch):
    monkeypatch.setattr(choir, "today", lambda: date(2026, 11, 16))
    assert choir.seed_concert() == {"songs": 12, "rehearsals": 7, "notices": 1}
    assert choir.seed_concert() == {"songs": 0, "rehearsals": 0, "notices": 0}
    d = login(client, "singer").get("/api/dashboard").json()
    assert [s["title"] for s in d["songs"]][:2] == ["Baba tunaleta vipaji", "Unmerited Grace"]
    assert len(d["songs"]) == 12 and all(s["stage"] == 0 for s in d["songs"])
    assert "Thursday rehearsals" in d["notices"][0]["text"]
    assert [r["day"] for r in d["rehearsals"] if r["kind"] == "weekend"] == [
        "2026-11-22", "2026-11-28", "2026-11-29", "2026-12-05"]
    assert d["concert"]["days_left"] == 20


def test_past_rehearsals_are_hidden(client, monkeypatch):
    choir.seed_concert()
    monkeypatch.setattr(choir, "today", lambda: date(2026, 11, 30))
    d = login(client, "singer").get("/api/dashboard").json()
    assert [r["day"] for r in d["rehearsals"]] == ["2026-12-03", "2026-12-05"]


def test_progress_is_personal_and_builds_a_streak(client, monkeypatch):
    choir.seed_concert()
    login(client, "singer")
    sid = client.get("/api/dashboard").json()["songs"][0]["id"]
    monkeypatch.setattr(choir, "today", lambda: date(2026, 11, 16))
    assert client.post("/api/practice", json={"repertoire_id": sid, "stage": 1}).json()["streak"] == 1
    monkeypatch.setattr(choir, "today", lambda: date(2026, 11, 17))
    assert client.get("/api/dashboard").json()["streak"] == 1  # yesterday still counts
    assert client.post("/api/practice", json={"repertoire_id": sid, "stage": 2}).json() == {"stage": 2, "streak": 2}
    monkeypatch.setattr(choir, "today", lambda: date(2026, 11, 20))
    assert client.get("/api/dashboard").json()["streak"] == 0  # two missed days break it
    assert client.post("/api/practice", json={"repertoire_id": sid, "stage": 5}).status_code == 422
    assert client.post("/api/practice", json={"repertoire_id": 999, "stage": 1}).status_code == 404
    other = login(client, "lead_t").get("/api/dashboard").json()
    assert other["songs"][0]["stage"] == 0 and other["streak"] == 0


def test_rsvp_roundtrip_and_login_required(client, monkeypatch):
    monkeypatch.setattr(choir, "today", lambda: date(2026, 11, 16))
    choir.seed_concert()
    client.cookies.clear()
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/kb/search?q=dress").status_code == 401
    login(client, "singer")
    rid = client.get("/api/dashboard").json()["rehearsals"][0]["id"]
    assert client.post(f"/api/rehearsals/{rid}/rsvp", json={"rsvp": "maybe"}).status_code == 422
    assert client.post(f"/api/rehearsals/{rid}/rsvp", json={"rsvp": "no"}).status_code == 200
    assert client.post(f"/api/rehearsals/{rid}/rsvp", json={"rsvp": "yes"}).status_code == 200
    assert client.get("/api/dashboard").json()["rehearsals"][0]["my_rsvp"] == "yes"
    with db.closing() as conn:
        assert conn.execute("SELECT COUNT(*) FROM attendance").fetchone()[0] == 1


def test_kb_search_finds_sections_and_resync_replaces(client):
    text = "# Choir Guide\n\nIntro line.\n\n## Dress code\n\nBlack and white with a red scarf for concerts.\n\n" \
           "## Rehearsals\n\nSaturday 5 pm and Sunday 2 pm.\n"
    assert choir.kb_upsert("gdoc:abc", "Choir Guide", "https://example.org/doc", text) == 3
    login(client, "singer")
    hits = client.get("/api/kb/search", params={"q": "red scarf dress code?"}).json()
    assert hits[0]["heading"] == "Dress code" and "[[scarf]]" in hits[0]["snippet"]
    assert hits[0]["url"] == "https://example.org/doc"
    # FTS syntax in user input is treated as plain words, not as a query
    assert client.get("/api/kb/search", params={"q": 'scarf" OR NEAR( * AND'}).status_code == 200
    assert client.get("/api/kb/search", params={"q": "???"}).json() == []
    choir.kb_upsert("gdoc:abc", "Choir Guide", None, "## Dress code\n\nAll black.\n")
    assert client.get("/api/kb/search", params={"q": "scarf"}).json() == []
    with db.closing() as conn:
        assert conn.execute("SELECT COUNT(*) FROM kb_docs").fetchone()[0] == 1
