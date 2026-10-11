"""Background render worker. Runs as its own process, separate from web requests.

    python -m bvc.worker          # poll forever
    python -m bvc.worker --once   # process queued jobs and exit

Jobs are bounded: score size limits, a subprocess timeout per FluidSynth call,
and at most JOB_MAX_ATTEMPTS attempts before a job is marked failed with a reason.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
import traceback

from . import config, db
from .model import to_musicxml
from .render import RenderError, render_version
from .workflow import _add_asset, latest_version_id, now_iso, song_dir


def _claim(conn):
    stale = time.time() - config.JOB_STALE_SECONDS
    conn.execute("BEGIN IMMEDIATE")
    try:
        # A job left 'running' by a crashed worker goes back to the queue.
        conn.execute("UPDATE jobs SET status = 'queued' WHERE status = 'running' AND started_at < ?", (stale,))
        job = conn.execute("SELECT * FROM jobs WHERE status = 'queued' ORDER BY id LIMIT 1").fetchone()
        if job is None:
            conn.execute("COMMIT")
            return None
        if job["attempts"] >= job["max_attempts"]:
            conn.execute("UPDATE jobs SET status = 'failed', finished_at = ?, error = COALESCE(error, '') || "
                         "' (attempt limit reached)' WHERE id = ?", (now_iso(), job["id"]))
            conn.execute("COMMIT")
            return _claim(conn)
        conn.execute("UPDATE jobs SET status = 'running', attempts = attempts + 1, started_at = ? WHERE id = ?",
                     (time.time(), job["id"]))
        conn.execute("COMMIT")
        return job
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def process_job(job) -> None:
    if job["kind"] == "video":
        return process_video_job(job)
    with db.closing() as conn:
        v = conn.execute("SELECT * FROM versions WHERE id = ?", (job["version_id"],)).fetchone()
        if v["id"] != latest_version_id(conn, v["song_id"]) and v["status"] != "approved":
            conn.execute("UPDATE jobs SET status = 'failed', error = 'Skipped: a newer version exists', "
                         "finished_at = ? WHERE id = ?", (now_iso(), job["id"]))
            return
    model = json.loads(v["model_json"])
    out_dir = song_dir(v["song_id"]) / f"v{v['id']}"
    if out_dir.exists():
        shutil.rmtree(out_dir)  # a retry starts clean
    out_dir.mkdir(parents=True)

    def write(name: str, data: bytes) -> str:
        (out_dir / name).write_bytes(data)
        return str((out_dir / name).relative_to(config.STORAGE_DIR))

    try:
        produced = render_version(model, write)
        score_rel = write("score.musicxml", to_musicxml(model))
    except Exception as exc:  # noqa: BLE001 - every failure becomes a visible job error
        msg = str(exc) if isinstance(exc, RenderError) else f"{type(exc).__name__}: {exc}"
        with db.closing() as conn:
            final = job["attempts"] + 1 >= job["max_attempts"]
            conn.execute("UPDATE jobs SET status = ?, error = ?, finished_at = ? WHERE id = ?",
                         ("failed" if final else "queued", msg[:500], now_iso() if final else None, job["id"]))
        if not isinstance(exc, RenderError):
            traceback.print_exc()
        return
    with db.transaction() as conn:
        conn.execute("DELETE FROM assets WHERE version_id = ?", (v["id"],))
        for a in produced:
            _add_asset(conn, v["id"], a["kind"], a["part"], a["tempo"], a["rel"], "audio/wav", a["seconds"])
        _add_asset(conn, v["id"], "score", None, None, score_rel, "application/vnd.recordare.musicxml+xml")
        conn.execute("UPDATE jobs SET status = 'done', error = NULL, finished_at = ? WHERE id = ?",
                     (now_iso(), job["id"]))
    prune_old_assets(v["song_id"])


def process_video_job(job) -> None:
    """Make the private practice videos for one version from its already-rendered audio."""
    from .video import VideoError, render_videos
    with db.closing() as conn:
        v = conn.execute("SELECT * FROM versions WHERE id = ?", (job["version_id"],)).fetchone()
        rows = conn.execute("SELECT kind, part, tempo, rel_path, seconds FROM assets WHERE version_id = ? AND kind IN "
                            "('stem', 'mix')", (v["id"],)).fetchall()
    audio = {(r["kind"], r["part"], r["tempo"]): (config.STORAGE_DIR / r["rel_path"], r["seconds"]) for r in rows}
    out_dir = song_dir(v["song_id"]) / f"v{v['id']}" / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)

    def write_path(name: str):
        path = out_dir / name
        return path, str(path.relative_to(config.STORAGE_DIR))

    try:
        produced = render_videos(json.loads(v["model_json"]), audio, write_path)
    except Exception as exc:  # noqa: BLE001 - every failure becomes a visible job error
        msg = str(exc) if isinstance(exc, VideoError) else f"{type(exc).__name__}: {exc}"
        with db.closing() as conn:
            final = job["attempts"] + 1 >= job["max_attempts"]
            conn.execute("UPDATE jobs SET status = ?, error = ?, finished_at = ? WHERE id = ?",
                         ("failed" if final else "queued", msg[:500], now_iso() if final else None, job["id"]))
        if not isinstance(exc, VideoError):
            traceback.print_exc()
        return
    with db.transaction() as conn:
        conn.execute("DELETE FROM assets WHERE version_id = ? AND kind IN ('video', 'playlist')", (v["id"],))
        for a in produced:
            _add_asset(conn, v["id"], a["kind"], a["part"], a["tempo"], a["rel"], a["mime"], a["seconds"])
        conn.execute("UPDATE jobs SET status = 'done', error = NULL, finished_at = ? WHERE id = ?",
                     (now_iso(), job["id"]))


def prune_old_assets(song_id: int) -> None:
    """Delete generated audio of versions nobody can use any more. History rows stay."""
    with db.transaction() as conn:
        keep = {r[0] for r in conn.execute(
            "SELECT id FROM versions WHERE song_id = ? AND (status IN ('approved', 'in_review') OR id = "
            "(SELECT MAX(id) FROM versions WHERE song_id = ?))", (song_id, song_id))}
        old = conn.execute("SELECT a.id, a.rel_path, a.version_id FROM assets a JOIN versions v ON v.id = a.version_id "
                           "WHERE v.song_id = ? AND a.kind IN ('stem', 'mix', 'score', 'video', 'playlist')", (song_id,)).fetchall()
        for a in old:
            if a["version_id"] not in keep:
                (config.STORAGE_DIR / a["rel_path"]).unlink(missing_ok=True)
                conn.execute("DELETE FROM assets WHERE id = ?", (a["id"],))


def run_once() -> int:
    done = 0
    with db.closing() as conn:
        while True:
            job = _claim(conn)
            if job is None:
                return done
            process_job(dict(job))  # job["attempts"] is the count before this attempt
            done += 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--data-dir")
    args = ap.parse_args()
    if args.data_dir:
        config.set_data_dir(args.data_dir)
    db.init()
    if args.once:
        from .community import purge_expired
        purge_expired()
        print(f"processed {run_once()} job(s)")
        return
    print("render worker started; Ctrl+C to stop")
    last_purge = 0.0
    while True:
        if time.time() - last_purge > 3600:
            # Retention rules run hourly even if nobody opens the app.
            from .community import purge_expired
            purge_expired()
            last_purge = time.time()
        if run_once() == 0:
            time.sleep(2)


if __name__ == "__main__":
    main()
