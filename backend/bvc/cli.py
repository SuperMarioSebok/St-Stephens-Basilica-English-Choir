"""Admin commands.

    python -m bvc.cli add-user USERNAME --role singer|voice_lead|director [--part S|A|T|B]
    python -m bvc.cli demo [--approve]     # demo accounts + the original test piece (LOCAL DEMO ONLY)
"""
from __future__ import annotations

import argparse
import getpass
import secrets
from pathlib import Path

from . import auth, config, db, workflow, worker

DEMO_USERS = [
    ("director", "director", None, "Director (demo)"),
    ("lead_s", "voice_lead", "S", "Soprano Lead (demo)"),
    ("lead_a", "voice_lead", "A", "Alto Lead (demo)"),
    ("lead_t", "voice_lead", "T", "Tenor Lead (demo)"),
    ("lead_b", "voice_lead", "B", "Bass Lead (demo)"),
    ("singer", "singer", "T", "Singer (demo)"),
]
FIXTURE = config.ROOT / "fixtures" / "morning-light-test-piece.musicxml"


def demo(approve: bool) -> None:
    db.init()
    password = "practise-" + secrets.token_hex(3)
    with db.closing() as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            raise SystemExit("Database already has users; use a fresh BVC_DATA_DIR for the demo.")
    ids = {}
    for username, role, part, name in DEMO_USERS:
        ids[username] = auth.create_user(username, password, role, part, name)
    director = {"id": ids["director"], "username": "director", "role": "director", "voice_part": None}
    res = workflow.create_score_song(director, FIXTURE.name, FIXTURE.read_bytes(),
                                     "Original test piece written for this project. Not a choir arrangement.",
                                     is_test_piece=True)
    print(f"Imported test piece as song {res['song_id']}, version {res['version_id']} (draft)")
    if approve:
        import json
        with db.closing() as conn:
            mapping = json.loads(workflow.get_version(conn, res["version_id"])["mapping_json"])
        vid = workflow.set_mappings(director, res["version_id"], {vp: mapping[vp] for vp in mapping})
        worker.run_once()
        workflow.submit(director, vid)
        workflow.decide(director, vid, True, "Demo approval of the original test piece")
        print(f"Mapping confirmed, audio rendered, version {vid} approved")
    print("\nDemo accounts (local demo only; all share one password):")
    for username, role, part, _ in DEMO_USERS:
        print(f"  {username:9s} {role}{' ' + part if part else ''}")
    print(f"  password: {password}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir")
    sub = ap.add_subparsers(dest="cmd", required=True)
    au = sub.add_parser("add-user")
    au.add_argument("username")
    au.add_argument("--role", required=True, choices=["singer", "voice_lead", "director"])
    au.add_argument("--part", choices=["S", "A", "T", "B"])
    au.add_argument("--name")
    d = sub.add_parser("demo")
    d.add_argument("--approve", action="store_true")
    args = ap.parse_args()
    if args.data_dir:
        config.set_data_dir(args.data_dir)
    if args.cmd == "add-user":
        db.init()
        pw = getpass.getpass("Password (10+ characters): ")
        uid = auth.create_user(args.username, pw, args.role, args.part, args.name)
        print(f"created user {uid}")
    elif args.cmd == "demo":
        demo(args.approve)


if __name__ == "__main__":
    main()
