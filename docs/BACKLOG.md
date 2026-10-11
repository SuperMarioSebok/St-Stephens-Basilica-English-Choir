# Backlog (phase-tagged)

Phases follow the full roadmap. Each later phase is a gated milestone: start only after the previous one passes
review with the Music Director.

## Phase 1: finish and harden the practice slice
| Item | Why | Size |
|---|---|---|
| Load the first real piece (once files and permission arrive) | Real validation | S |
| Leader acceptance test (CHANGE-MANAGEMENT Stage 1) and fixes | Gate 1 | M |
| Practice assignment + optional self-check (no ranking) | In the full brief, not yet built | M |
| Policy switch: keep last approved version visible during review | Decision pending | S |
| Compressed audio (AAC/Opus) with a sync check after decoding | Data use on phones | M |
| HTTPS hosting, backups, systemd units, log policy for `/api/feedback` | Needed before members use it | M |
| CLI: deactivate user, delete old feedback, export history | Data minimisation | S |
| Persistent login throttling | Robustness | S |
| Optional visual score cursor, enabled only after a timing verification test against OSMD's cursor | Nice to have | M |
| Private MP4 practice video (score/section display + tenor audio, FFmpeg), with timing verified; no upload | Requested after core works | M |
| Build-versus-buy notes: Chorilo, ChoirMate, Choir Player; Verovio vs OSMD benchmark on a real score | Not researched yet | S |
| Inspect the reference YouTube playlist (style only; no media reuse) | Not done | S |

## Phase 2: Playlist Factory (needs representative files for each format first)
- Adapters into the same model: reviewed MusicXML (done), then Hybrid Sol-fa and Grid Sol-fa, only after their
  conventions are explained with examples. Manual structured entry for sol-fa as a fallback.
- Scans: Audiveris (AGPL, review obligations) → human correction in MuseScore → MusicXML → existing import.
- Review queue for every inferred symbol; source image regions kept for the reviewer.
- Batch rendering, MP4 variants, playlist manifest and upload-ready pack, all behind the review gate. No automatic
  YouTube upload.
- Smallest next milestone proposal: one staff-notation piece → approved → three MP4s (tenor alone, tenor louder,
  full) with section labels, timing verified by test.

## Phase 3: Self-practice coach (open question first)
- Ask singers: live feedback while singing, or a summary after recording? Prototype summary-after as the default.
- Research pitch and onset tools (licence, on-device vs server, accuracy on singing); benchmark on real phones.
- Consent, local processing preference, short retention, delete controls; never linked to anonymous feedback.

## Phase 4: Choir admin and tour collaboration
- Private planning workspace, templates, repertoire packs with rights and expiry, translation review, conflict
  checks in Europe/Budapest time. Fictional sample tour first. Nothing sent, booked or shared without approval.

## Outreach module (separate workstream, after the practice slice)
- Local approval board and exportable content pack first (draft → reviewer approves exact media/caption/channel →
  scheduled → result). Compare Postiz (AGPL) and Mixpost editions before building anything. Confirm channel
  ownership and admin rights for @saintstephenchoir, the Facebook page and the YouTube channel first.

## Open decisions for the Music Director
1. Pilot for all members, or tenor-only first?
2. Edits hide the song until re-approved (current), or keep the last approved version visible?
3. Who reads feedback: director only (current) or also voice leads?
4. First piece, its source file and permission.
5. Success/stop criteria and leaders' time budget.
