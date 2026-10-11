import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bvc import auth, config, db  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
PASSWORD = "test-password-123"
USERS = [("director", "director", None), ("lead_s", "voice_lead", "S"), ("lead_t", "voice_lead", "T"),
         ("singer", "singer", "T")]


@pytest.fixture()
def env(tmp_path):
    config.set_data_dir(tmp_path)
    auth._failures.clear()
    db.init()
    users = {}
    for name, role, part in USERS:
        uid = auth.create_user(name, PASSWORD, role, part)
        users[name] = {"id": uid, "username": name, "role": role, "voice_part": part}
    return users


@pytest.fixture()
def client(env):
    from fastapi.testclient import TestClient
    from bvc.app import app
    return TestClient(app, headers={"x-bvc": "1"})


def login(client, username):
    client.cookies.clear()
    r = client.post("/api/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return client


def fixture_bytes(name="morning-light-test-piece.musicxml"):
    return (FIXTURES / name).read_bytes()


def import_song(client, name="morning-light-test-piece.musicxml"):
    login(client, "director")
    r = client.post("/api/songs", files={"score": (name, fixture_bytes(name), "application/xml")},
                    data={"rights_note": "Original test piece", "is_test_piece": "true"})
    assert r.status_code == 200, r.text
    return r.json()


def confirm_all(client, vid):
    login(client, "director")
    mapping = client.get(f"/api/versions/{vid}").json()["mapping"]
    entries = {vp: {k: m[k] for k in ("part_id", "staff", "voice", "octave_shift")} for vp, m in mapping.items()}
    r = client.post(f"/api/versions/{vid}/mapping", json={"entries": entries, "confirm": True})
    assert r.status_code == 200, r.text
    return r.json()["version_id"]


def approved_song(client):
    """Import, confirm, render, submit, approve. Returns (song_id, version_id)."""
    from bvc import worker
    res = import_song(client)
    vid = confirm_all(client, res["version_id"])
    worker.run_once()
    assert client.post(f"/api/versions/{vid}/submit").status_code == 200
    assert client.post(f"/api/versions/{vid}/approve", json={"note": "ok"}).status_code == 200
    return res["song_id"], vid


def dump(x):
    return json.dumps(x, indent=1)
