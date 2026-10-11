"""Feedback must stay unlinked to users."""
import re

from bvc import config, db
from conftest import approved_song, login


def test_feedback_table_has_no_identity_or_time_columns(env):
    with db.closing() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(feedback)")}
    assert cols == {"id", "song_id", "bar_label", "comment", "week"}


def test_feedback_stored_without_user_and_listed_without_times(client):
    song_id, vid = approved_song(client)
    login(client, "singer")
    r = client.post("/api/feedback", json={"song_id": song_id, "bar_label": "5", "comment": "Bar 5 tenor sounds odd"})
    assert r.status_code == 204
    assert "set-cookie" not in {k.lower() for k in r.headers}
    with db.closing() as conn:
        row = dict(conn.execute("SELECT * FROM feedback").fetchone())
        users = [dict(u) for u in conn.execute("SELECT id, username FROM users")]
    for u in users:
        assert str(u["id"]) != row["id"] and u["username"] not in str(row.values())
    assert re.fullmatch(r"\d{4}-W\d{2}", row["week"])
    login(client, "director")
    listed = client.get("/api/feedback").json()
    assert listed == [{"song": "Morning Light (Original Test Piece)", "bar_label": "5",
                       "comment": "Bar 5 tenor sounds odd", "week": row["week"]}]


def test_feedback_only_for_approved_songs_and_bounded(client):
    song_id, _ = approved_song(client)
    login(client, "singer")
    assert client.post("/api/feedback", json={"song_id": 999, "comment": "x"}).status_code == 404
    assert client.post("/api/feedback", json={"song_id": song_id, "comment": ""}).status_code == 409
    long = "x" * (config.FEEDBACK_MAX_CHARS + 1)
    assert client.post("/api/feedback", json={"song_id": song_id, "comment": long}).status_code == 422


def test_feedback_route_does_not_pass_user_to_storage():
    import inspect
    from bvc import workflow
    assert list(inspect.signature(workflow.add_feedback).parameters) == ["song_id", "bar_label", "comment"]


def test_voice_leads_cannot_read_feedback(client):
    login(client, "lead_t")
    assert client.get("/api/feedback").status_code == 403
