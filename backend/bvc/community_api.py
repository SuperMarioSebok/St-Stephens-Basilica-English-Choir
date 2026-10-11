"""HTTP routes for recruiting, onboarding, events, the member survey and KPIs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from . import auth, community, config
from .workflow import WorkflowError

router = APIRouter()
COOKIE = "bvc_session"


def _user(request: Request):
    from .app import current_user
    return current_user(request)


def _optional_user(request: Request):
    u = auth.user_for_token(request.cookies.get(COOKIE))
    return dict(u) if u else None


def _client_key(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    fwd = request.headers.get("x-forwarded-for")
    if host in ("127.0.0.1", "::1") and fwd:  # behind Caddy on the same machine
        host = fwd.split(",")[-1].strip()
    return host


def _limit(request: Request, what: str):
    if community.rate_limited(f"{what}:{_client_key(request)}") or community.rate_limited(f"{what}:all", 200, 3600):
        raise WorkflowError("Too many requests just now. Please try again in a few minutes.")


def _count(request: Request, what: str):
    """Only successful submissions count towards the limit, so typing mistakes never lock someone out."""
    community.rate_record(f"{what}:{_client_key(request)}")
    community.rate_record(f"{what}:all")


# ---- Public (no login) ----------------------------------------------------------------------

@router.get("/api/public/page")
def public_page(request: Request):
    return community.public_page(_optional_user(request))


class EnquiryBody(BaseModel):
    first_name: str = Field("", max_length=200)
    contact: str = Field("", max_length=300)
    interests: list[str] = Field(default_factory=list, max_length=4)
    voice_type: str | None = Field(None, max_length=20)
    message: str = Field("", max_length=2000)
    consent: bool = False
    updates_opt_in: bool = False
    under_18: bool = False
    guardian_name: str | None = Field(None, max_length=200)
    guardian_contact: str | None = Field(None, max_length=300)
    guardian_consent: bool = False
    source: str | None = Field(None, max_length=30)
    website: str | None = Field(None, max_length=200)  # honeypot


@router.post("/api/public/enquiries", status_code=204)
def post_enquiry(body: EnquiryBody, request: Request):
    if community.get_settings()["published"] != "1":
        raise LookupError("This page is not published yet")
    _limit(request, "enquiry")
    community.submit_enquiry(body.model_dump())
    _count(request, "enquiry")
    return Response(status_code=204)


class ReservationBody(BaseModel):
    event_id: int
    first_name: str = Field("", max_length=200)
    contact: str = Field("", max_length=300)
    party_size: int = 1
    consent: bool = False
    updates_opt_in: bool = False
    source: str | None = Field(None, max_length=30)
    website: str | None = Field(None, max_length=200)


@router.post("/api/public/reservations")
def post_reservation(body: ReservationBody, request: Request):
    _limit(request, "reserve")
    result = community.reserve(body.model_dump())
    _count(request, "reserve")
    return result


class CancelBody(BaseModel):
    code: str = Field(max_length=100)


@router.post("/api/public/reservations/cancel", status_code=204)
def cancel_reservation(body: CancelBody, request: Request):
    _limit(request, "cancel")
    try:
        community.cancel_reservation(body.code)
    finally:
        _count(request, "cancel")  # wrong codes count too, to stop guessing
    return Response(status_code=204)


@router.get("/api/public/invites/{token}")
def check_invite(token: str, request: Request):
    _limit(request, "invite-check")
    try:
        return community.check_invite(token)
    except LookupError:
        _count(request, "invite-check")  # only failed lookups count, to stop guessing
        raise


class AcceptBody(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


@router.post("/api/public/invites/{token}/accept")
def accept_invite(token: str, body: AcceptBody, request: Request, response: Response):
    _limit(request, "invite-accept")
    session = community.accept_invite(token, body.username, body.password)
    _count(request, "invite-accept")
    response.set_cookie(COOKIE, session, httponly=True, samesite="strict", secure=config.COOKIE_SECURE,
                        max_age=config.SESSION_DAYS * 86400, path="/")
    return {"ok": True}


# ---- Staff ---------------------------------------------------------------------------------

@router.get("/api/site")
def get_site(user=Depends(_user)):
    community.require_role(user, "director", "welcome", "comms")
    return community.get_settings()


@router.put("/api/site")
def put_site(values: dict[str, str], user=Depends(_user)):
    return community.update_settings(user, values)


class EventBody(BaseModel):
    title: str = Field(max_length=200)
    starts_at: str = Field(max_length=40)
    venue: str = Field("", max_length=300)
    description: str = Field("", max_length=3000)
    is_public: bool = False
    rsvp_open: bool = False
    capacity: int | None = None
    actual_attendance: int | None = None
    donations_reported_huf: int | None = None


@router.get("/api/events")
def get_events(user=Depends(_user)):
    return community.list_events(user)


@router.post("/api/events")
def create_event(body: EventBody, user=Depends(_user)):
    return {"id": community.save_event(user, body.model_dump())}


@router.put("/api/events/{event_id}")
def update_event(event_id: int, body: EventBody, user=Depends(_user)):
    return {"id": community.save_event(user, body.model_dump(), event_id)}


@router.get("/api/events/{event_id}/reservations")
def event_reservations(event_id: int, user=Depends(_user)):
    return community.list_reservations(user, event_id)


@router.get("/api/enquiries")
def get_enquiries(user=Depends(_user)):
    return community.list_enquiries(user)


class EnquiryPatch(BaseModel):
    status: str | None = Field(None, max_length=30)
    notes: str | None = Field(None, max_length=3000)


@router.patch("/api/enquiries/{enquiry_id}")
def patch_enquiry(enquiry_id: str, body: EnquiryPatch, user=Depends(_user)):
    community.update_enquiry(user, enquiry_id, body.status, body.notes)
    return {"ok": True}


@router.delete("/api/enquiries/{enquiry_id}", status_code=204)
def remove_enquiry(enquiry_id: str, user=Depends(_user)):
    community.delete_enquiry(user, enquiry_id)
    return Response(status_code=204)


class InviteBody(BaseModel):
    display_name: str = Field(max_length=100)
    role: str = Field(max_length=20)
    voice_part: str | None = Field(None, max_length=1)
    enquiry_id: str | None = Field(None, max_length=40)


@router.post("/api/invites")
def post_invite(body: InviteBody, user=Depends(_user)):
    return community.create_invite(user, body.display_name, body.role, body.voice_part, body.enquiry_id)


@router.get("/api/invites")
def get_invites(user=Depends(_user)):
    return community.list_invites(user)


@router.post("/api/invites/{invite_id}/resend")
def resend_invite(invite_id: int, user=Depends(_user)):
    return community.resend_invite(user, invite_id)


class SurveyBody(BaseModel):
    title: str = Field(max_length=100)
    question: str | None = Field(None, max_length=400)


@router.post("/api/surveys")
def post_survey(body: SurveyBody, user=Depends(_user)):
    return {"id": community.create_survey(user, body.title, body.question)}


@router.post("/api/surveys/{survey_id}/close")
def post_close_survey(survey_id: int, user=Depends(_user)):
    community.close_survey(user, survey_id)
    return {"ok": True}


@router.get("/api/surveys/open")
def get_open_surveys(user=Depends(_user)):
    return community.open_surveys(user)


class AnswerBody(BaseModel):
    score: int
    comment: str = Field("", max_length=2000)


@router.post("/api/surveys/{survey_id}/answer", status_code=204)
def post_answer(survey_id: int, body: AnswerBody, user=Depends(_user)):
    community.answer_survey(user, survey_id, body.score, body.comment)
    return Response(status_code=204)


@router.get("/api/surveys/results")
def get_survey_results(user=Depends(_user)):
    return community.survey_results(user)


@router.get("/api/kpi")
def get_kpi(user=Depends(_user)):
    return community.kpi_summary(user)


@router.get("/api/kpi.csv")
def get_kpi_csv(user=Depends(_user)):
    return PlainTextResponse(community.kpi_csv(user), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="weekly-counts.csv"'})


class SnapshotBody(BaseModel):
    metric: str = Field(max_length=40)
    value: int
    week: str | None = Field(None, max_length=10)


@router.post("/api/kpi/snapshots")
def post_snapshot(body: SnapshotBody, user=Depends(_user)):
    community.save_snapshot(user, body.metric, body.value, body.week)
    return {"ok": True}
