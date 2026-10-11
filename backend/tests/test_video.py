"""Practice videos: bar labels follow the shared timeline; video and audio lengths match."""
import json
import shutil
import subprocess

import pytest

from bvc import config, db, worker
from bvc import musicxml_import as mxi
from bvc.model import timeline
from bvc.video import FONT, _safe_label, bar_windows, filter_script
from conftest import approved_song, fixture_bytes, login

needs_tools = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which(config.FLUIDSYNTH) is None, reason="ffmpeg or fluidsynth missing")


def model():
    inv = mxi.inspect(fixture_bytes())
    return mxi.build_model(inv, mxi.propose_mapping(inv))


def test_bar_windows_follow_timeline_at_each_tempo():
    m = model()
    tl = timeline(m)
    for pct in (100, 75):
        w = bar_windows(m, pct)
        assert len(w) == len(tl["bars"])
        assert w[0][0] == "0 (pickup)"
        assert w[2][1] == pytest.approx(tl["bars"][2]["start"] / (pct / 100), abs=0.001)
        assert w[-1][2] == pytest.approx(tl["end"] / (pct / 100), abs=0.001)
        assert all(a[2] == pytest.approx(b[1], abs=0.001) for a, b in zip(w, w[1:]))  # no gaps


def test_labels_from_scores_cannot_inject_filters(tmp_path):
    assert _safe_label("12a'[x];movie=evil") == "12axmovieevil"
    m = model()
    m["bars"][1]["label"] = "1':drawtext=x"
    script = filter_script(m, 100, tmp_path / "t.txt", tmp_path / "s.txt")
    assert "':drawtext=x" not in script


@needs_tools
def test_video_job_end_to_end(client):
    song_id, vid = approved_song(client)
    login(client, "singer")
    assert client.post(f"/api/versions/{vid}/videos").status_code == 403
    login(client, "director")
    assert client.post(f"/api/versions/{vid}/videos").status_code == 200
    assert client.post(f"/api/versions/{vid}/videos").status_code == 409  # already queued
    worker.run_once()
    detail = client.get(f"/api/versions/{vid}").json()
    assert detail["videos"]["status"] == "done", detail["videos"]
    videos = [a for a in detail["assets"] if a["kind"] == "video"]
    assert len(videos) == 2 * (4 * 2 + 1)  # two tempos x (4 parts x alone/louder + full choir)
    playlist = next(a for a in detail["assets"] if a["kind"] == "playlist")
    assert len(json.loads(client.get(f"/api/assets/{playlist['id']}").text)["videos"]) == 18
    with db.closing() as conn:
        row = conn.execute("SELECT rel_path, seconds FROM assets WHERE version_id = ? AND kind = 'video' AND "
                           "part = 'T-alone' AND tempo = 75", (vid,)).fetchone()
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(config.STORAGE_DIR / row["rel_path"])], capture_output=True, text=True).stdout
    assert float(out) == pytest.approx(row["seconds"], abs=0.15)
    login(client, "singer")  # approved version: singers can watch
    assert client.get(f"/api/assets/{videos[0]['id']}").status_code == 200


def test_font_present_for_videos():
    import os
    if shutil.which("ffmpeg"):
        assert os.path.exists(FONT)
