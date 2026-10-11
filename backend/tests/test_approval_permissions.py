"""Approval gate and role/part permissions, exercised through the HTTP API."""
from bvc import worker
from conftest import approved_song, confirm_all, fixture_bytes, import_song, login


def singer_view(client, song_id, vid):
    login(client, "singer")
    songs = client.get("/api/songs").json()
    return songs, client.get(f"/api/versions/{vid}").status_code


def test_unapproved_song_invisible_to_singers(client):
    res = import_song(client)
    vid = confirm_all(client, res["version_id"])
    worker.run_once()
    songs, status = singer_view(client, res["song_id"], vid)
    assert songs == [] and status == 404
    login(client, "director")
    assert client.post(f"/api/versions/{vid}/submit").status_code == 200
    songs, status = singer_view(client, res["song_id"], vid)
    assert songs == [] and status == 404  # in review is still invisible


def test_approved_song_visible_with_assets(client):
    song_id, vid = approved_song(client)
    login(client, "singer")
    songs = client.get("/api/songs").json()
    assert [s["approved_version_id"] for s in songs] == [vid]
    detail = client.get(f"/api/versions/{vid}").json()
    assert "model" not in detail and "mapping" not in detail  # singers get the player data only
    stems = [a for a in detail["assets"] if a["kind"] == "stem"]
    assert len(stems) == 12  # 4 parts x 3 tempos
    r = client.get(f"/api/assets/{stems[0]['id']}")
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store"


def test_edit_creates_new_version_and_revokes_approval(client):
    song_id, vid = approved_song(client)
    login(client, "singer")
    old_asset = client.get(f"/api/versions/{vid}").json()["assets"][0]["id"]
    login(client, "lead_t")
    r = client.post(f"/api/versions/{vid}/parts/T/bars", json={"bars": {"1": "B3:1 B3:1 C4:1 A3:1"}})
    assert r.status_code == 200, r.text
    new_vid = r.json()["version_id"]
    assert new_vid != vid
    login(client, "singer")
    assert client.get("/api/songs").json() == []
    assert client.get(f"/api/versions/{vid}").status_code == 404
    assert client.get(f"/api/versions/{new_vid}").status_code == 404
    assert client.get(f"/api/assets/{old_asset}").status_code == 404
    # History records who changed what.
    login(client, "director")
    hist = client.get(f"/api/songs/{song_id}/history").json()["changes"]
    edit = next(c for c in hist if c["action"] == "edit-notes")
    assert edit["who"] == "lead_t" and edit["part"] == "T"
    assert edit["detail"]["bars"] == [{"bar": "1", "before": "B3:1 B3:1 C4:1 G3:1", "after": "B3:1 B3:1 C4:1 A3:1"}]
    statuses = {v["id"]: v["status"] for v in client.get(f"/api/songs/{song_id}/versions").json()}
    assert statuses[vid] == "revoked" and statuses[new_vid] == "draft"
    # Audio regenerates for the new version, then it can be approved again.
    assert client.get(f"/api/versions/{new_vid}").json()["render"]["status"] == "queued"
    worker.run_once()
    assert client.post(f"/api/versions/{new_vid}/submit").status_code == 200
    assert client.post(f"/api/versions/{new_vid}/approve", json={}).status_code == 200
    login(client, "singer")
    assert [s["approved_version_id"] for s in client.get("/api/songs").json()] == [new_vid]


def test_cannot_approve_stale_or_unready_versions(client):
    res = import_song(client)
    vid1 = res["version_id"]
    worker.run_once()
    r = client.post(f"/api/versions/{vid1}/submit")
    assert r.status_code == 409 and "mapping is not confirmed" in r.json()["detail"]
    vid2 = confirm_all(client, vid1)
    r = client.post(f"/api/versions/{vid2}/submit")
    assert r.status_code == 409 and "not rendered" in r.json()["detail"]
    worker.run_once()
    assert client.post(f"/api/versions/{vid2}/submit").status_code == 200
    login(client, "lead_t")
    vid3 = client.post(f"/api/versions/{vid2}/parts/T/label", json={"label": "Tenor 1"}).json()["version_id"]
    login(client, "director")
    assert client.post(f"/api/versions/{vid2}/approve", json={}).status_code == 409
    assert vid3 > vid2


def test_voice_lead_cannot_touch_another_part(client):
    res = import_song(client)
    vid = confirm_all(client, res["version_id"])
    login(client, "lead_t")
    assert client.post(f"/api/versions/{vid}/parts/S/bars", json={"bars": {"1": "G4:4"}}).status_code == 403
    assert client.post(f"/api/versions/{vid}/parts/S/label", json={"label": "x"}).status_code == 403
    assert client.post(f"/api/versions/{vid}/mapping",
                       json={"entries": {"S": {"part_id": "P2", "staff": 1, "voice": "1"}}}).status_code == 403
    assert client.post(f"/api/versions/{vid}/mapping", json={"entries": {
        "T": {"part_id": "P3", "staff": 1, "voice": "1"}, "S": {"part_id": "P2", "staff": 1, "voice": "1"}}}
    ).status_code == 403
    r = client.post(f"/api/versions/{vid}/parts/S/reupload",
                    files={"score": ("a.musicxml", fixture_bytes(), "application/xml")})
    assert r.status_code == 403
    assert client.post(f"/api/versions/{vid}/approve", json={}).status_code == 403
    # Own part works.
    assert client.post(f"/api/versions/{vid}/parts/T/bars", json={"bars": {"8": "B3:2 G3:2"}}).status_code == 200


def test_reupload_replaces_only_own_part(client):
    res = import_song(client)
    vid = confirm_all(client, res["version_id"])
    # The corrected file changes the soprano (G4 -> A4) AND the tenor (G3 -> A3).
    head, tenor_and_rest = fixture_bytes().split(b'<part id="P3">')
    tenor, rest = tenor_and_rest.split(b"</part>", 1)
    corrected = (head.replace(b"<step>G</step><octave>4</octave>", b"<step>A</step><octave>4</octave>")
                 + b'<part id="P3">' + tenor.replace(b"<step>G</step><octave>3</octave>",
                                                    b"<step>A</step><octave>3</octave>") + b"</part>" + rest)
    login(client, "lead_t")
    before = client.get(f"/api/versions/{vid}").json()["bar_tokens"]
    r = client.post(f"/api/versions/{vid}/parts/T/reupload",
                    files={"score": ("fixed.musicxml", corrected, "application/xml")})
    assert r.status_code == 200, r.text
    after = client.get(f"/api/versions/{r.json()['version_id']}").json()["bar_tokens"]
    assert after["S"] == before["S"]  # soprano changes in the file were ignored
    assert after["T"] != before["T"] and "G3" not in " ".join(after["T"])


def test_singer_and_anonymous_are_blocked(client):
    res = import_song(client)
    vid = res["version_id"]
    login(client, "singer")
    for method, url, body in [
        ("post", f"/api/versions/{vid}/parts/T/bars", {"bars": {"1": "G3:4"}}),
        ("post", f"/api/versions/{vid}/notes", {"text": "x"}),
        ("post", f"/api/versions/{vid}/submit", None),
        ("post", f"/api/versions/{vid}/approve", {}),
        ("get", f"/api/songs/{res['song_id']}/history", None),
        ("get", f"/api/songs/{res['song_id']}/versions", None),
        ("get", "/api/feedback", None),
    ]:
        r = getattr(client, method)(url, json=body) if body is not None else getattr(client, method)(url)
        assert r.status_code == 403, (url, r.status_code)
    client.cookies.clear()
    assert client.get("/api/songs").status_code == 401
    assert client.get(f"/api/versions/{vid}").status_code == 401


def test_draft_assets_not_reachable_by_singer_even_with_id(client):
    res = import_song(client)
    vid = confirm_all(client, res["version_id"])
    worker.run_once()
    login(client, "director")
    asset = client.get(f"/api/versions/{vid}").json()["assets"][0]["id"]
    assert client.get(f"/api/assets/{asset}").status_code == 200
    login(client, "singer")
    assert client.get(f"/api/assets/{asset}").status_code == 404


def test_state_change_requires_custom_header(client):
    from fastapi.testclient import TestClient
    from bvc.app import app
    bare = TestClient(app)
    r = bare.post("/api/login", json={"username": "director", "password": "x"})
    assert r.status_code == 403


def test_login_lockout(client):
    client.cookies.clear()
    for _ in range(8):
        client.post("/api/login", json={"username": "singer", "password": "wrong-password"})
    r = client.post("/api/login", json={"username": "singer", "password": "test-password-123"})
    assert r.status_code == 401
