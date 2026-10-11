# Licence inventory

Software licences and **content permissions are separate questions**. A permissive software licence says
nothing about whether the choir may copy an arrangement, recording or lyrics.

Versions and licences below were read from the installed packages' metadata on 2026-10-11 (Python
`importlib.metadata`, npm `package.json`, Debian `copyright` files). Recheck when upgrading.

## Runtime software

| Component | Version tested | Licence | How it is used | Obligation to review |
|---|---|---|---|---|
| FluidSynth | 2.3.4 (Ubuntu package) | **LGPL-2.1-or-later** | Separate program, called as a subprocess | If you distribute FluidSynth binaries (e.g. in a container image you share), LGPL source-offer and notice obligations apply. Running it on your own server is not distribution. |
| FluidR3_GM SoundFont | Debian `fluid-soundfont-gm` | **MIT** (README: "I hereby release Fluid under the MIT license") | Instrument samples for rendering | Keep the copyright notice with redistributed SoundFont copies. Rendered audio is a work product; MIT places no restriction on it. |
| FFmpeg | 6.1.1 present on the dev machine | Ubuntu build has `--enable-gpl`: **GPL** | **Not used in Milestone 1.** Planned for MP4 export (backlog) | Before using: confirm the binary's configuration; GPL applies to distribution of FFmpeg itself; an LGPL-only build is possible if needed. |
| music21 | 10.5.0 | BSD-3-Clause | Writes the display MusicXML; cross-check in tests | Notice |
| FastAPI | 0.143.0 | MIT | Web API | Notice |
| Starlette | 1.6.0 | BSD-3-Clause | Under FastAPI | Notice |
| Uvicorn | 0.53.0 | BSD-3-Clause | Web server | Notice |
| Pydantic | 2.13.5 | MIT | Request validation | Notice |
| python-multipart | 0.0.32 | Apache-2.0 | Upload parsing | Notice; NOTICE file if any |
| defusedxml | 0.7.1 | PSF License | Safe XML parsing | Notice |
| NumPy | 2.5.3 | BSD-3-Clause (+ bundled 0BSD, MIT, Zlib, CC0) | Audio mixing | Notice |
| SQLite | system | Public domain | Database | None |
| React, React DOM | 18.3.1 | MIT | UI | Notice in shipped JS |
| OpenSheetMusicDisplay | 1.9.0 | BSD-3-Clause | Score display | Notice |
| VexFlow (via OSMD) | 1.2.93 | MIT | Engraving inside OSMD | Notice |

OSMD's open renderer does not include an audio player; this app does its own playback.

## Development-only

| Component | Version | Licence |
|---|---|---|
| Vite | 5.4.11 | MIT |
| @vitejs/plugin-react | 4.3.4 | MIT |
| Vitest | 2.1.9 | MIT |
| TypeScript | 5.6.3 | Apache-2.0 |
| pytest | 9.1.1 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |

## Not used, and why it matters

| Component | Licence | Note |
|---|---|---|
| Audiveris (OMR, scans → MusicXML) | **AGPL-3.0** | Phase 2 candidate. AGPL network clause needs review before offering it as a hosted service. |
| MuseScore Studio | GPL-3.0 | Recommended as a manual correction tool on a reviewer's own computer. |
| Verovio | LGPL-3.0 | Alternative renderer; not benchmarked yet. |
| Postiz | AGPL-3.0 | Outreach module candidate (later). |

## Content

| Item | Rights status |
|---|---|
| `fixtures/morning-light-*.musicxml` | Original test piece written for this project. Free to use for testing. Not choir repertoire. |
| Choir repertoire (Sanctus, Ndikhokhele Bawo, Gloria, ...) | **Not included.** Needs files and written permission; see FILES-AND-RIGHTS-NEEDED.md. |
| Choral Guide playlist recordings | **Not downloaded or reused.** Style reference only, subject to permission. |

## This repository's own licence

Not chosen. Decide before sharing the code with other choirs (options: MIT or Apache-2.0 for maximum reuse;
AGPL-3.0 if you want hosted forks to stay open). Do not publish the repository until this is decided.
