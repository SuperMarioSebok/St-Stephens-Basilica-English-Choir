# Basilica Voice Coach

A small, private practice web app for the **St. Stephen's Basilica English Choir** (Budapest).
Singers practise their voice part at home on a phone browser: no app install, English UI, large buttons.

> **Status: Milestone 1, local vertical slice.** Runs on one computer for demonstration and review.
> It is not deployed, has no real choir repertoire, and is not production-ready (see
> [docs/LIMITATIONS.md](docs/LIMITATIONS.md)). The only music included is an **original test piece**,
> "Morning Light", written for this project. It is not a choir arrangement.

## What works in this slice

| Area | What it does |
|---|---|
| Roles | **Singer** practises approved songs and sends anonymous feedback. **Voice Lead** (S/A/T/B) edits only their own part, adds review notes, submits for review. **Director** uploads, confirms mappings, approves or rejects, reads feedback. |
| Import | MusicXML/MXL upload with safety checks. Every (part, staff, voice) stream is listed; a mapping to S/A/T/B is *proposed* from part names and **never auto-confirmed**. Shared staves, divisi chords, possible unisons, tenor octave, repeats, tempo changes and range problems are flagged instead of guessed. |
| Versions | Every change (notes, mapping, label, corrected upload) creates a new immutable version, **cancels the current approval** and queues new audio. History records who, when and what. |
| Approval gate | Singers see only the single approved version of a song. Drafts, versions in review and their files return 404 to singers, even with a known ID. |
| Part editor | Note list per bar (`G4:1 F#3:0.5 R:2 C4+E4:1 D5:2~`), live validation, before/after preview of single bars or ranges, or re-upload of a corrected MusicXML from which **only your part** is taken. |
| Audio | FluidSynth renders one stem per part plus mixes (full SATB; each part prominent), at **100%, 75% and 50% tempo rendered from the score** (pitch never changes). All files of a tempo have identical length and start at tick 0. |
| Player | Choose song and part; part alone / part louder / full choir; mute/solo; seek; repeat a bar range; slower speeds; jump to bar; score display with bar numbers (OpenSheetMusicDisplay). Stems are started together on one Web Audio clock. |
| Feedback | Song + bar + comment. No name, user ID or exact time stored; reviewers see the ISO week only, shuffled within the week. |
| Fallback | Director can upload an authorized recording + PDF. Loops by time only; slower speed only where the browser preserves pitch. |

| Recruiting | Public "Come sing with us" page (hidden until a director publishes it) with countdowns, an interest form for singers, volunteers, supporters and concert guests (consent; parent or guardian for under-18s; deleted after 6 months), share buttons and QR codes. |
| Welcome team | Private enquiry tracker: new → contacted → first rehearsal → probation → joined, with weekly counts (no names) and CSV export. |
| Events | Concert countdowns, free reservations with capacity and cancel codes, headcount and donations reported by the parish or charity. |
| Onboarding | One-time invite links and QR codes; the app can be added to the phone's home screen. |
| Member survey | Anonymous one-question NPS survey; results only once 5+ members answer. |
| Practice videos | Private MP4s per part (alone, louder) and full choir at 100% and 75%, with bar numbers on screen, plus a playlist file. |

No moving score cursor yet: its visual sync is not verified, so the player shows the current bar as text instead.

## Setup (Ubuntu/Debian; macOS notes below)

Requirements: Python 3.11+, Node 20+, FluidSynth and a General MIDI SoundFont.

```bash
# 1. System packages (FluidSynth is LGPL; FluidR3_GM SoundFont is MIT)
sudo apt-get install -y fluidsynth fluid-soundfont-gm

# 2. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Frontend
cd ../frontend
npm ci        # or: npm install
npm run build # produces frontend/dist, served by the backend

# 4. Demo data: demo accounts + the original test piece (prints a random demo password)
cd ../backend
python -m bvc.cli --data-dir ../data demo            # leaves the song as a draft to walk through
# or: python -m bvc.cli --data-dir ../data demo --approve   # fast-forward to an approved song

# 5. Run (two terminals)
python run_server.py --data-dir ../data            # http://127.0.0.1:8000
python -m bvc.worker --data-dir ../data            # render worker (separate process)
```

macOS: `brew install fluid-synth`, download a GM SoundFont you are licensed to use (e.g. FluidR3_GM), and set
`BVC_SOUNDFONT=/path/to/FluidR3_GM.sf2`.

For frontend development with hot reload: run the backend on port 8000, then `cd frontend && npm run dev`
(Vite proxies `/api`).

Test on a phone in the same Wi-Fi: `python run_server.py --data-dir ../data --host 0.0.0.0` and open
`http://<computer-ip>:8000`. Web Audio on some phones requires HTTPS; see the checklist.

Real users: `python -m bvc.cli --data-dir ../data add-user anna --role voice_lead --part A`
(prompts for a password of at least 10 characters).

## Tests

```bash
cd backend && python -m pytest -q
cd frontend && npm test && npm run typecheck
```

Covered: part mapping and flags (clean, shared staves, divisi, tenor octave), musical timing (pickup bar,
tempo changes, ties, tempo variants), MusicXML round trip and cross-check against music21, the approval
gate, part-level permissions, feedback unlinkability, hostile uploads (XXE, billion laughs, zip bomb,
path traversal, wrong types, oversize), and rendered audio (equal lengths, tempo scaling, **pitch identical
at 100/75/50%**, stem onsets within 15 ms of the score timeline; measured worst case 7.4 ms).

## Documentation

| Document | For whom |
|---|---|
| [docs/DEMO-WALKTHROUGH.md](docs/DEMO-WALKTHROUGH.md) | Anyone running the demo |
| [docs/COMMUNITY.md](docs/COMMUNITY.md) | Recruiting page, enquiries, events and reservations, invites, member survey, practice videos |
| [docs/content/](docs/content/) | Recruitment wording for approval, social media playbook, content calendar, approval sheet, sponsor brief draft |
| [docs/CHANGE-MANAGEMENT.md](docs/CHANGE-MANAGEMENT.md) | Music Director, voice leads, choir committee: staged rollout, stakeholders, pilot plan |
| [docs/TEST-CHECKLISTS.md](docs/TEST-CHECKLISTS.md) | Director and voice leads: acceptance, phone-browser and listening tests |
| [docs/FILES-AND-RIGHTS-NEEDED.md](docs/FILES-AND-RIGHTS-NEEDED.md) | What must be supplied before real repertoire |
| [docs/LICENSES.md](docs/LICENSES.md) | Dependency and content licence inventory |
| [docs/PRIVACY.md](docs/PRIVACY.md) | Data collected, retention, feedback anonymity limits |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | Known limitations |
| [docs/HOW-TO-TEST.md](docs/HOW-TO-TEST.md) | Mario, the Music Director, voice leads: run, share and test in plain English |
| [docs/HOSTING.md](docs/HOSTING.md) | Cheapest server options and one-command setup (`deploy/`) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How it fits together, security design |
| [docs/BACKLOG.md](docs/BACKLOG.md) | Phase-tagged backlog and open decisions |

## Layout

```
backend/bvc/      FastAPI app, workflow, importer, renderer, worker, CLI
backend/tests/    pytest suite
frontend/src/     React + TypeScript phone UI
fixtures/         original test piece (3 encodings) and its generator
docs/             everything above
```

## Licence

No licence has been chosen for this code yet; see [docs/LICENSES.md](docs/LICENSES.md) before sharing it.
