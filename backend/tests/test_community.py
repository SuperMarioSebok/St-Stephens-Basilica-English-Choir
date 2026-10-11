"""Recruiting page, enquiries, reservations, invites, member survey and KPIs."""
from datetime import date, datetime, timedelta, timezone

import pytest

from bvc import auth, community, db
from conftest import PASSWORD, login

FORM = {"first_name": "Anna", "contact": "anna@example.org", "interests": ["sing"], "voice_type": "alto",
        "consent": True, "source": "whatsapp"}


@pytest.fixture()
def staff(env):
    auth.create_user("welcome", PASSWORD, "welcome")
    auth.create_user("comms", PASSWORD, "comms")
    community._rate.clear()
    return env


def publish(client):
    login(client, "director")
    r = client.put("/api/site", json={"published": "1", "join_deadline": "2026-10-24",
                                      "rehearsals": "Thursdays 19:00, parish hall"})
    assert r.status_code == 200, r.text


def add_event(client, days=60, **extra):
    login(client, "director")
    starts = (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat()
    body = {"title": "Christmas Concert", "starts_at": starts, "venue": "St. Stephen's Basilica",
            "is_public": True, "rsvp_open": True, "capacity": 5, **extra}
    r = client.post("/api/events", json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ---- Public page ---------------------------------------------------------------------------

def test_page_hidden_until_published(client, staff):
    client.cookies.clear()
    assert client.get("/api/public/page").status_code == 404
    assert client.post("/api/public/enquiries", json=FORM).status_code == 404
    login(client, "welcome")
    assert client.get("/api/public/page").json()["preview"] is True  # staff can preview
    publish(client)
    client.cookies.clear()
    page = client.get("/api/public/page").json()
    assert page["settings"]["choir_name"] == "the English Choir of St. Stephen's Basilica"
    assert page["settings"]["join_deadline"] == "2026-10-24"


def test_only_director_edits_page(client, staff):
    for name in ("welcome", "comms", "singer", "lead_t"):
        login(client, name)
        assert client.put("/api/site", json={"headline": "x"}).status_code == 403
    login(client, "director")
    assert client.put("/api/site", json={"donation_url": "http://not-secure"}).status_code == 409
    assert client.put("/api/site", json={"unknown": "x"}).status_code == 409


# ---- Enquiries ---------------------------------------------------------------------------------

def test_enquiry_requires_consent_and_guardian_for_minors(client, staff):
    publish(client)
    client.cookies.clear()
    assert client.post("/api/public/enquiries", json={**FORM, "consent": False}).status_code == 409
    assert client.post("/api/public/enquiries", json={**FORM, "interests": []}).status_code == 409
    minor = {**FORM, "under_18": True}
    assert client.post("/api/public/enquiries", json=minor).status_code == 409
    assert client.post("/api/public/enquiries", json={**minor, "guardian_name": "Parent",
                                                      "guardian_contact": "p@example.org"}).status_code == 409
    ok = {**minor, "guardian_name": "Parent", "guardian_contact": "p@example.org", "guardian_consent": True}
    assert client.post("/api/public/enquiries", json=ok).status_code == 204
    assert client.post("/api/public/enquiries", json=FORM).status_code == 204
    login(client, "welcome")
    rows = client.get("/api/enquiries").json()
    assert len(rows) == 2 and {r["under_18"] for r in rows} == {0, 1}


def test_honeypot_and_rate_limit(client, staff):
    publish(client)
    client.cookies.clear()
    assert client.post("/api/public/enquiries", json={**FORM, "website": "spam"}).status_code == 204
    for _ in range(4):
        assert client.post("/api/public/enquiries", json=FORM).status_code == 204
    assert client.post("/api/public/enquiries", json=FORM).status_code == 409  # 6th within 10 minutes
    login(client, "director")
    assert len(client.get("/api/enquiries").json()) == 4  # honeypot entry was dropped silently


def test_tracker_is_staff_only(client, staff):
    for name in ("singer", "lead_t", "comms"):
        login(client, name)
        assert client.get("/api/enquiries").status_code == 403
    client.cookies.clear()
    assert client.get("/api/enquiries").status_code == 401


def test_status_flow_counts_and_retention(client, staff):
    publish(client)
    client.cookies.clear()
    client.post("/api/public/enquiries", json=FORM)
    client.post("/api/public/enquiries", json={**FORM, "interests": ["volunteer", "concert"]})
    login(client, "welcome")
    eid = next(r["id"] for r in client.get("/api/enquiries").json() if "sing" in r["interests"])
    for status in ("contacted", "first_rehearsal", "probation"):
        assert client.patch(f"/api/enquiries/{eid}", json={"status": status}).status_code == 200
    kpi = client.get("/api/kpi").json()
    this_week = kpi["weeks"][-1]
    assert (this_week["enquiries"], this_week["singers"], this_week["volunteers_supporters"]) == (2, 1, 1)
    assert (this_week["contacted"], this_week["first_rehearsal"], this_week["probation"]) == (1, 1, 1)
    csv_text = client.get("/api/kpi.csv").text
    assert "Anna" not in csv_text and "anna@example.org" not in csv_text and "week,enquiries" in csv_text
    # Entries untouched for more than 6 months disappear; the anonymous counts stay.
    old = (date.today() - timedelta(days=200)).isoformat()
    with db.closing() as conn:
        conn.execute("UPDATE enquiries SET status_changed_on = ?", (old,))
    assert client.get("/api/enquiries").json() == []
    assert client.get("/api/kpi").json()["totals"]["new"] == 2


# ---- Events and reservations ----------------------------------------------------------------------

def test_reservations_capacity_cancel_and_privacy(client, staff):
    eid = add_event(client)
    client.cookies.clear()
    body = {"event_id": eid, "first_name": "Tom", "contact": "+36 1 234", "party_size": 3, "consent": True,
            "source": "qr"}
    r = client.post("/api/public/reservations", json=body)
    assert r.status_code == 200
    code = r.json()["cancel_code"]
    assert client.post("/api/public/reservations", json={**body, "party_size": 3}).status_code == 409  # 3+3 > 5
    assert client.post("/api/public/reservations", json={**body, "consent": False}).status_code == 409
    page_event = client.get("/api/public/page")
    assert page_event.status_code == 404  # page itself still unpublished
    assert client.post("/api/public/reservations/cancel", json={"code": code}).status_code == 204
    assert client.post("/api/public/reservations/cancel", json={"code": code}).status_code == 404
    assert client.post("/api/public/reservations", json={**body, "party_size": 5}).status_code == 200
    login(client, "comms")
    assert client.get(f"/api/events/{eid}/reservations").status_code == 403  # names: welcome team only
    events = client.get("/api/events").json()
    assert events[0]["reserved"] == 5
    login(client, "welcome")
    assert len(client.get(f"/api/events/{eid}/reservations").json()) == 2


def test_closed_or_private_events_refuse_reservations(client, staff):
    eid = add_event(client, rsvp_open=False)
    pid = add_event(client, is_public=False)
    client.cookies.clear()
    for e in (eid, pid):
        r = client.post("/api/public/reservations", json={"event_id": e, "first_name": "A", "contact": "a",
                                                           "consent": True})
        assert r.status_code == 404


def test_old_reservations_deleted_total_kept(client, staff):
    eid = add_event(client)
    client.cookies.clear()
    client.post("/api/public/reservations", json={"event_id": eid, "first_name": "A", "contact": "a",
                                                  "party_size": 2, "consent": True})
    past = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat(timespec="minutes")
    with db.closing() as conn:
        conn.execute("UPDATE events SET starts_at = ?", (past,))
    community.purge_expired()
    with db.closing() as conn:
        assert conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 0
        assert conn.execute("SELECT reservations_final FROM events").fetchone()[0] == 2


def test_countdown_lists_only_public_upcoming(client, staff):
    add_event(client, days=30)
    add_event(client, days=10, is_public=False)
    add_event(client, days=-3)
    publish(client)
    client.cookies.clear()
    events = client.get("/api/public/page").json()["events"]
    assert len(events) == 1 and events[0]["places_left"] == 5


# ---- Invites ---------------------------------------------------------------------------------

def test_invite_flow_from_enquiry(client, staff):
    publish(client)
    client.cookies.clear()
    client.post("/api/public/enquiries", json=FORM)
    login(client, "director")
    eid = client.get("/api/enquiries").json()[0]["id"]
    inv = client.post("/api/invites", json={"display_name": "Anna", "role": "singer", "voice_part": "A",
                                            "enquiry_id": eid}).json()
    client.cookies.clear()
    assert client.get(f"/api/public/invites/{inv['token']}").json()["voice_part"] == "A"
    r = client.post(f"/api/public/invites/{inv['token']}/accept", json={"username": "anna", "password": "short"})
    assert r.status_code == 409
    r = client.post(f"/api/public/invites/{inv['token']}/accept",
                    json={"username": "anna", "password": "a-long-password"})
    assert r.status_code == 200
    me = client.get("/api/me").json()  # logged in straight away
    assert (me["role"], me["voice_part"]) == ("singer", "A")
    assert client.get(f"/api/public/invites/{inv['token']}").status_code == 404  # single use
    login(client, "director")
    assert client.get("/api/enquiries").json() == []  # enquiry removed once they joined
    assert client.get("/api/kpi").json()["weeks"][-1]["joined"] == 1
    assert client.get("/api/invites").json()[0]["state"] == "used"


def test_invite_rules(client, staff):
    for name in ("welcome", "comms", "lead_t", "singer"):
        login(client, name)
        assert client.post("/api/invites", json={"display_name": "X", "role": "director"}).status_code == 403
    login(client, "director")
    assert client.post("/api/invites", json={"display_name": "X", "role": "voice_lead"}).status_code == 409
    inv = client.post("/api/invites", json={"display_name": "Ben", "role": "singer", "voice_part": "B"}).json()
    new = client.post(f"/api/invites/{inv['id']}/resend").json()
    client.cookies.clear()
    assert client.get(f"/api/public/invites/{inv['token']}").status_code == 404  # replaced
    assert client.get(f"/api/public/invites/{new['token']}").status_code == 200
    with db.closing() as conn:
        conn.execute("UPDATE invites SET expires_at = '2000-01-01T00:00:00+00:00'")
    assert client.get(f"/api/public/invites/{new['token']}").status_code == 404  # expired
    with db.closing() as conn:
        stored = [r[0] for r in conn.execute("SELECT token_hash FROM invites")]
    assert new["token"] not in stored  # only hashes are stored


# ---- Member survey -----------------------------------------------------------------------------

def test_survey_is_anonymous_once_per_member_and_hidden_below_five(client, staff):
    login(client, "director")
    sid = client.post("/api/surveys", json={"title": "Baseline November"}).json()["id"]
    names = []
    for i in range(5):
        uname = f"member{i}"
        auth.create_user(uname, PASSWORD, "singer")
        names.append(uname)
    for i, uname in enumerate(names[:4]):
        login(client, uname)
        assert client.post(f"/api/surveys/{sid}/answer", json={"score": 10 - i, "comment": f"c{i}"}).status_code == 204
    login(client, names[0])
    assert client.post(f"/api/surveys/{sid}/answer", json={"score": 0}).status_code == 409  # only once
    assert client.get("/api/surveys/open").json()[0]["answered"] is True
    login(client, "director")
    res = client.get("/api/surveys/results").json()[0]
    assert res["responses"] == 4 and "nps" not in res
    login(client, names[4])
    client.post(f"/api/surveys/{sid}/answer", json={"score": 3})
    login(client, "director")
    res = client.get("/api/surveys/results").json()[0]
    # scores 10, 9, 8, 7, 3 -> promoters 2, detractors 1 -> NPS 20
    assert (res["nps"], res["promoters"], res["detractors"]) == (20, 2, 1)
    with db.closing() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(survey_answers)")}
    assert cols == {"id", "survey_id", "score", "comment"}
    login(client, "singer")
    assert client.get("/api/surveys/results").status_code == 403


# ---- KPI snapshots ---------------------------------------------------------------------------

def test_kpi_snapshots(client, staff):
    login(client, "comms")
    assert client.post("/api/kpi/snapshots", json={"metric": "followers_instagram", "value": 812}).status_code == 200
    assert client.post("/api/kpi/snapshots", json={"metric": "favourite_colour", "value": 1}).status_code == 409
    login(client, "singer")
    assert client.get("/api/kpi").status_code == 403
    login(client, "welcome")
    snaps = client.get("/api/kpi").json()["snapshots"]
    assert snaps[0]["metric"] == "followers_instagram" and snaps[0]["value"] == 812


def test_new_roles_see_only_approved_songs(client, staff):
    from conftest import import_song
    res = import_song(client)
    for name in ("welcome", "comms"):
        login(client, name)
        assert client.get("/api/songs").json() == []
        assert client.get(f"/api/versions/{res['version_id']}").status_code == 404
