"""Settings, read from environment variables with safe local defaults."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("BVC_DATA_DIR", ROOT / "data")).resolve()
DB_PATH = DATA_DIR / "bvc.sqlite3"
STORAGE_DIR = DATA_DIR / "storage"  # private: only served through access-checked endpoints
FRONTEND_DIST = ROOT / "frontend" / "dist"

SOUNDFONT = os.environ.get("BVC_SOUNDFONT", "/usr/share/sounds/sf2/FluidR3_GM.sf2")
FLUIDSYNTH = os.environ.get("BVC_FLUIDSYNTH", "fluidsynth")
SAMPLE_RATE = 22050
TEMPO_VARIANTS = (100, 75, 50)  # percent; rendered from the score, never by resampling audio
GM_PROGRAM = int(os.environ.get("BVC_GM_PROGRAM", "0"))  # 0 = acoustic grand piano (clear attacks)
TAIL_SECONDS = 1.5
PROMINENT_OTHERS_GAIN = 0.3

# Upload limits
MAX_SCORE_UPLOAD = 5 * 1024 * 1024
MAX_AUDIO_UPLOAD = 40 * 1024 * 1024
MAX_PDF_UPLOAD = 20 * 1024 * 1024
MXL_MAX_MEMBERS = 50
MXL_MAX_UNCOMPRESSED = 20 * 1024 * 1024
MXL_MAX_RATIO = 100

# Score limits that bound conversion work
MAX_BARS = 600
MAX_NOTES = 20000
MAX_SCORE_SECONDS = 20 * 60

# Jobs
JOB_MAX_ATTEMPTS = 3
SUBPROCESS_TIMEOUT = 120
JOB_STALE_SECONDS = 15 * 60

# Sessions
SESSION_DAYS = 30
COOKIE_SECURE = os.environ.get("BVC_COOKIE_SECURE", "0") == "1"
LOGIN_MAX_FAILURES = 8
LOGIN_LOCK_SECONDS = 15 * 60

FEEDBACK_MAX_CHARS = 1000


def set_data_dir(path) -> None:
    """Point the app at another data directory (used by tests and the CLI)."""
    global DATA_DIR, DB_PATH, STORAGE_DIR
    DATA_DIR = Path(path).resolve()
    DB_PATH = DATA_DIR / "bvc.sqlite3"
    STORAGE_DIR = DATA_DIR / "storage"
