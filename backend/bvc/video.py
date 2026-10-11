"""Private practice videos (Playlist Factory, first slice).

Each video is a simple title card with the song, part and mode, plus the current bar number,
driven by the same timeline as the audio. The audio track is the already-rendered stem or mix,
so sound and labels come from one source of truth. No moving notation cursor yet.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from . import config
from .model import PART_NAMES, timeline

FFMPEG = "ffmpeg"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
VIDEO_TEMPOS = (100, 75)
MODES = (("alone", "{part} alone"), ("louder", "{part} louder"), ("full", "Full choir"))


class VideoError(RuntimeError):
    pass


def _safe_label(text: str) -> str:
    """Bar labels come from uploaded scores: keep them to characters that are inert in a filter graph."""
    return re.sub(r"[^A-Za-z0-9 ()]", "", str(text))[:16] or "?"


def bar_windows(model: dict, tempo_pct: int) -> list[tuple[str, float, float]]:
    """(label, start, end) in seconds for each bar at this tempo, from the shared timeline."""
    tl = timeline(model)
    factor = tempo_pct / 100
    bars = tl["bars"]
    out = []
    for i, b in enumerate(bars):
        start = b["start"] / factor
        end = (bars[i + 1]["start"] if i + 1 < len(bars) else tl["end"]) / factor
        label = f"{_safe_label(b['label'])}{' (pickup)' if b.get('pickup') else ''}"
        out.append((label, round(start, 3), round(end, 3)))
    return out


def filter_script(model: dict, tempo_pct: int, title_file: Path, subtitle_file: Path) -> str:
    """ffmpeg filter graph: background card, static title lines from files, one bar label per bar window."""
    parts = [
        f"[0:v]drawtext=fontfile={FONT_BOLD}:textfile='{title_file}':fontcolor=white:fontsize=54:"
        "x=(w-text_w)/2:y=150",
        f"drawtext=fontfile={FONT}:textfile='{subtitle_file}':fontcolor=0xF2D27A:fontsize=40:x=(w-text_w)/2:y=240",
    ]
    for label, start, end in bar_windows(model, tempo_pct):
        parts.append(f"drawtext=fontfile={FONT_BOLD}:text='Bar {label}':fontcolor=white:fontsize=110:"
                     f"x=(w-text_w)/2:y=380:enable='between(t,{start},{end})'")
    parts.append(f"drawtext=fontfile={FONT}:expansion=none:text='{int(tempo_pct)}% speed':fontcolor=0xBFC8DA:"
                 "fontsize=30:x=(w-text_w)/2:y=h-90")
    return ",".join(parts) + "[v]"


def make_video(model: dict, audio_path: Path, out_path: Path, title: str, subtitle: str, tempo_pct: int,
               seconds: float) -> None:
    if not Path(FONT).exists():
        raise VideoError("DejaVu fonts are not installed (apt-get install fonts-dejavu-core)")
    with tempfile.TemporaryDirectory(prefix="bvc-video-") as tmp:
        tmpd = Path(tmp)
        (tmpd / "title.txt").write_text(title[:60])
        (tmpd / "subtitle.txt").write_text(subtitle[:60])
        script = tmpd / "graph.txt"
        script.write_text(filter_script(model, tempo_pct, tmpd / "title.txt", tmpd / "subtitle.txt"))
        cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
               "-f", "lavfi", "-i", f"color=c=0x1F2A44:s=1280x720:r=10:d={seconds:.3f}",
               "-i", str(audio_path),
               "-filter_complex_script", str(script), "-map", "[v]", "-map", "1:a",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-shortest", str(out_path)]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=config.SUBPROCESS_TIMEOUT, check=False)
        except FileNotFoundError as exc:
            raise VideoError("FFmpeg is not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise VideoError("FFmpeg timed out") from exc
        if res.returncode != 0 or not out_path.exists():
            raise VideoError(f"FFmpeg failed: {res.stderr.decode(errors='replace')[:300]}")


def render_videos(model: dict, audio: dict, write_path) -> list[dict]:
    """audio: {(kind, part, tempo): (Path, seconds)} from the version's rendered assets.
    write_path(name) -> (absolute Path, relative path). Returns asset descriptors plus a playlist entry."""
    produced, playlist = [], []
    parts = [vp for vp in ("S", "A", "T", "B") if model["parts"].get(vp)]
    for pct in VIDEO_TEMPOS:
        jobs = []
        for vp in parts:
            label = model["parts"][vp]["label"] or PART_NAMES[vp]
            jobs.append((f"{vp}-alone", ("stem", vp, pct), f"{label} alone"))
            jobs.append((f"{vp}-louder", ("mix", f"{vp}-prominent", pct), f"{label} louder"))
        jobs.append(("full", ("mix", "full", pct), "Full choir"))
        for name, key, subtitle in jobs:
            if key not in audio:
                raise VideoError(f"Missing rendered audio for {name} at {pct}%")
            src, seconds = audio[key]
            abs_path, rel = write_path(f"video-{name}-{pct}.mp4")
            make_video(model, src, abs_path, model["title"], subtitle, pct, seconds)
            produced.append({"kind": "video", "part": name, "tempo": pct, "rel": rel, "seconds": seconds,
                             "mime": "video/mp4"})
            playlist.append({"title": f"{model['title']}: {subtitle} ({pct}%)", "file": Path(rel).name})
    abs_path, rel = write_path("playlist.json")
    abs_path.write_text(json.dumps({"title": model["title"], "videos": playlist}, indent=2))
    produced.append({"kind": "playlist", "part": None, "tempo": None, "rel": rel, "seconds": None,
                     "mime": "application/json"})
    return produced
