"""HTTP API. Every route checks the session and role; files are only served here."""
from __future__ import annotations

import json
import mimetypes
import random
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth, config, db, workflow
from . import musicxml_import as mxi
from .model import ModelError, VOICE_PARTS, format_bar_tokens, timeline
from .safe_upload import UploadError

COOKIE = "bvc_session"
mimetypes.add_type("application/manifest+json", ".webmanifest")


@asynccontextmanager
async def lifespan(_app):
    db.init()
    yield


app = FastAPI(title="Basilica Voice Coach", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    # Cross-site form posts are blocked: state-changing API calls need a custom header,
    # which browsers do not send cross-origin without a CORS preflight (not enabled).
    if request.url.path.startswith("/api/") and request.method not in ("GET", "HEAD") \
            and request.headers.get("x-bvc") != "1":
        return JSONResponse({"detail": "Missing request header"}, status_code=403)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
        "object-src 'self' blob:; frame-src 'self' blob:; frame-ancestors 'self'; base-uri 'none'; form-action 'self'")
    resp.headers["Permissions-Policy"] = "microphone=(), camera=(), geolocation=(), interest-cohort=()"
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "private, no-store"
    return resp


@app.exception_handler(UploadError)
@app.exception_handler(ModelError)
async def _bad_request(_req, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(workflow.WorkflowError)
async def _conflict(_req, exc):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(workflow.Forbidden)
async def _forbidden(_req, exc):
    return JSONResponse({"detail": str(exc)}, status_code=403)


@app.exception_handler(LookupError)
async def _not_found(_req, exc):
    return JSONResponse({"detail": str(exc) or "Not found"}, status_code=404)


def current_user(request: Request):
    user = auth.user_for_token(request.cookies.get(COOKIE))
    if user is None:
        raise HTTPException(401, "Please log in")
    return dict(user)


def role(*roles):
    def dep(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Your role cannot do this")
        return user
    return dep


STAFF = role("director", "voice_lead")
DIRECTOR = role("director")


async def read_upload(f: UploadFile, limit: int) -> tuple[str, bytes]:
    data = await f.read(limit + 1)
    if len(data) > limit:
        raise UploadError(f"File is larger than {limit // (1024 * 1024)} MB")
    return f.filename or "", data


# ---- Session ---------------------------------------------------------------------------

class LoginBody(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


@app.post("/api/login")
def login(body: LoginBody, response: Response):
    token = auth.login(body.username.strip(), body.password)
    if token is None:
        raise HTTPException(401, "Wrong username or password, or too many attempts. Try again later.")
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=config.COOKIE_SECURE,
                        max_age=config.SESSION_DAYS * 86400, path="/")
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    auth.logout(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return {k: user[k] for k in ("username", "display_name", "role", "voice_part")}


# ---- Songs and versions -------------------------------------------------------------------

@app.get("/api/songs")
def list_songs(user=Depends(current_user)):
    out = []
    with db.closing() as conn:
        for s in conn.execute("SELECT * FROM songs ORDER BY title"):
            approved = workflow.approved_version(conn, s["id"])
            item = {"id": s["id"], "title": s["title"], "kind": s["kind"], "is_test_piece": bool(s["is_test_piece"]),
                    "approved_version_id": approved["id"] if approved else None}
            if user["role"] not in ("director", "voice_lead"):
                if approved is None:
                    continue
            else:
                latest = workflow.get_version(conn, workflow.latest_version_id(conn, s["id"]))
                item.update(latest_version_id=latest["id"], latest_number=latest["number"],
                            latest_status=latest["status"], render=workflow.render_state(conn, latest["id"]),
                            rights_note=s["rights_note"])
            out.append(item)
    return out


@app.get("/api/songs/{song_id}/versions")
def song_versions(song_id: int, user=Depends(STAFF)):
    with db.closing() as conn:
        rows = conn.execute("SELECT v.id, v.number, v.status, v.created_at, v.change_summary, u.display_name AS author "
                            "FROM versions v JOIN users u ON u.id = v.created_by WHERE v.song_id = ? ORDER BY v.id DESC",
                            (song_id,)).fetchall()
    if not rows:
        raise LookupError("Song not found")
    return [dict(r) for r in rows]


@app.get("/api/songs/{song_id}/history")
def song_history(song_id: int, user=Depends(STAFF)):
    with db.closing() as conn:
        changes = conn.execute(
            "SELECT c.at, c.action, c.part, c.detail_json, u.display_name AS who, v.number AS version "
            "FROM changes c JOIN users u ON u.id = c.user_id JOIN versions v ON v.id = c.version_id "
            "WHERE v.song_id = ? ORDER BY c.id DESC", (song_id,)).fetchall()
        notes = conn.execute(
            "SELECT n.at, n.part, n.bar_index, n.text, u.display_name AS who, v.number AS version "
            "FROM review_notes n JOIN users u ON u.id = n.user_id JOIN versions v ON v.id = n.version_id "
            "WHERE v.song_id = ? ORDER BY n.id DESC", (song_id,)).fetchall()
    return {"changes": [{**dict(c), "detail": json.loads(c["detail_json"])} for c in changes],
            "notes": [dict(n) for n in notes]}


@app.get("/api/versions/{vid}")
def version_detail(vid: int, user=Depends(current_user)):
    with db.closing() as conn:
        v = workflow.get_version(conn, vid)
        if not workflow.can_view_version(user, v):
            raise LookupError("Version not found")  # singers cannot even learn that a draft exists
        assets = conn.execute("SELECT id, kind, part, tempo, mime, seconds FROM assets WHERE version_id = ?",
                              (vid,)).fetchall()
        out = {"id": v["id"], "song_id": v["song_id"], "title": v["song_title"], "kind": v["song_kind"],
               "number": v["number"], "status": v["status"], "assets": [dict(a) for a in assets],
               "tempos": list(config.TEMPO_VARIANTS)}
        if v["song_kind"] == "score":
            model = json.loads(v["model_json"])
            out["timeline"] = timeline(model)
            out["parts"] = {vp: (p["label"] if p else None) for vp, p in model["parts"].items()}
            out["cursor_verified"] = False  # see docs/LIMITATIONS.md
        else:
            out["manual"] = json.loads(v["manual_json"] or "{}")
        if user["role"] in ("director", "voice_lead"):
            out.update(created_at=v["created_at"], change_summary=v["change_summary"],
                       review_decision_note=v["review_decision_note"],
                       latest=v["id"] == workflow.latest_version_id(conn, v["song_id"]),
                       render=workflow.render_state(conn, vid),
                       videos=workflow.video_state(conn, vid),
                       readiness=workflow.readiness(conn, v))
            if v["song_kind"] == "score":
                out["model"] = model
                out["mapping"] = {k: {kk: vv for kk, vv in (m or {}).items() if kk != "source_file"}
                                  for k, m in json.loads(v["mapping_json"]).items()}
                out["bar_tokens"] = {vp: [format_bar_tokens(b) for b in p["bars"]] if p else None
                                     for vp, p in model["parts"].items()}
                out["inventory"] = mxi.public_inventory(workflow._inventory_for(v, None))
    return out


@app.post("/api/songs")
async def upload_song(score: UploadFile = File(...), rights_note: str = Form(...), title: str = Form(""),
                      is_test_piece: bool = Form(False), user=Depends(DIRECTOR)):
    name, data = await read_upload(score, config.MAX_SCORE_UPLOAD)
    return workflow.create_score_song(user, name, data, rights_note, is_test_piece, title.strip() or None)


@app.post("/api/songs/manual")
async def upload_manual(title: str = Form(...), rights_note: str = Form(...), note: str = Form(""),
                        audio: UploadFile = File(...), pdf: UploadFile | None = File(None), user=Depends(DIRECTOR)):
    aname, adata = await read_upload(audio, config.MAX_AUDIO_UPLOAD)
    pdata = None
    if pdf is not None and pdf.filename:
        _, pdata = await read_upload(pdf, config.MAX_PDF_UPLOAD)
    return workflow.create_manual_song(user, title, rights_note, aname, adata, pdata, note)


class BarsBody(BaseModel):
    bars: dict[str, str] = Field(max_length=600)
    summary: str = Field("", max_length=300)


@app.post("/api/versions/{vid}/parts/{part}/bars")
def edit_bars(vid: int, part: str, body: BarsBody, user=Depends(STAFF)):
    return {"version_id": workflow.edit_bars(user, vid, part, body.bars, body.summary)}


class MappingEntry(BaseModel):
    part_id: str | None = Field(None, max_length=64)
    staff: int | None = None
    voice: str | None = Field(None, max_length=8)
    octave_shift: int = 0
    none: bool = False


class MappingBody(BaseModel):
    entries: dict[str, MappingEntry]
    confirm: bool = True


@app.post("/api/versions/{vid}/mapping")
def set_mapping(vid: int, body: MappingBody, user=Depends(STAFF)):
    entries = {k: e.model_dump() for k, e in body.entries.items()}
    return {"version_id": workflow.set_mappings(user, vid, entries, body.confirm)}


class LabelBody(BaseModel):
    label: str = Field(max_length=40)


@app.post("/api/versions/{vid}/parts/{part}/label")
def set_label(vid: int, part: str, body: LabelBody, user=Depends(STAFF)):
    return {"version_id": workflow.set_label(user, vid, part, body.label)}


@app.post("/api/versions/{vid}/parts/{part}/reupload")
async def reupload(vid: int, part: str, score: UploadFile = File(...), part_id: str = Form(""),
                   staff: str = Form(""), voice: str = Form(""), octave_shift: int = Form(0), user=Depends(STAFF)):
    workflow.require_part(user, part)  # refuse before reading another part's file
    name, data = await read_upload(score, config.MAX_SCORE_UPLOAD)
    sel = {"part_id": part_id, "staff": staff or None, "voice": voice or None, "octave_shift": octave_shift} \
        if part_id else None
    return {"version_id": workflow.reupload_part(user, vid, part, name, data, sel)}


class NoteBody(BaseModel):
    part: str | None = None
    bar_index: int | None = None
    text: str = Field(max_length=2000)


@app.post("/api/versions/{vid}/notes")
def add_note(vid: int, body: NoteBody, user=Depends(STAFF)):
    workflow.add_review_note(user, vid, body.part, body.bar_index, body.text)
    return {"ok": True}


@app.post("/api/versions/{vid}/submit")
def submit(vid: int, user=Depends(STAFF)):
    workflow.submit(user, vid)
    return {"ok": True}


class DecisionBody(BaseModel):
    note: str = Field("", max_length=1000)


@app.post("/api/versions/{vid}/approve")
def approve(vid: int, body: DecisionBody, user=Depends(DIRECTOR)):
    workflow.decide(user, vid, True, body.note)
    return {"ok": True}


@app.post("/api/versions/{vid}/reject")
def reject(vid: int, body: DecisionBody, user=Depends(DIRECTOR)):
    workflow.decide(user, vid, False, body.note)
    return {"ok": True}


@app.post("/api/versions/{vid}/videos")
def make_videos(vid: int, user=Depends(DIRECTOR)):
    workflow.request_videos(user, vid)
    return {"ok": True}


@app.post("/api/versions/{vid}/rerender")
def rerender(vid: int, user=Depends(DIRECTOR)):
    workflow.retry_render(user, vid)
    return {"ok": True}


# ---- Files -----------------------------------------------------------------------------

@app.get("/api/assets/{asset_id}")
def get_asset(asset_id: str, user=Depends(current_user)):
    with db.closing() as conn:
        a = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if a is None:
            raise LookupError("File not found")
        v = workflow.get_version(conn, a["version_id"])
        if not workflow.can_view_version(user, v):
            raise LookupError("File not found")
    path = (config.STORAGE_DIR / a["rel_path"]).resolve()
    if config.STORAGE_DIR.resolve() not in path.parents or not path.is_file():
        raise LookupError("File not found")
    return FileResponse(path, media_type=a["mime"], headers={
        "Cache-Control": "private, no-store", "Content-Disposition": "inline"})


# ---- Anonymous feedback -----------------------------------------------------------------------

class FeedbackBody(BaseModel):
    song_id: int
    bar_label: str | None = Field(None, max_length=12)
    comment: str = Field(max_length=config.FEEDBACK_MAX_CHARS)


@app.post("/api/feedback", status_code=204)
def post_feedback(body: FeedbackBody, user=Depends(current_user)):
    # Login keeps the app private, but the user is NOT passed on or stored.
    del user
    workflow.add_feedback(body.song_id, body.bar_label, body.comment)
    return Response(status_code=204)


@app.get("/api/feedback")
def list_feedback(user=Depends(DIRECTOR)):
    with db.closing() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT s.title AS song, f.bar_label, f.comment, f.week FROM feedback f JOIN songs s ON s.id = f.song_id")]
    # Order within a week is shuffled so the list does not reveal submission order.
    random.shuffle(rows)
    rows.sort(key=lambda r: r["week"], reverse=True)
    return rows


from .community_api import router as community_router  # noqa: E402

app.include_router(community_router)


# ---- Frontend (built files) -----------------------------------------------------------------

if Path(config.FRONTEND_DIST).is_dir():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="frontend")
