# Architecture

```
 phone browser (React, Web Audio)          one origin, HTTPS in production
        │  session cookie + X-BVC header
        ▼
 FastAPI (backend/bvc/app.py) ── role check on every route ── workflow.py (versions, approval gate)
        │                                                   │
        │  SQLite (users, sessions, songs, versions,         │  private storage folder
        │  changes, review_notes, jobs, assets, feedback)    │  (sources, stems, mixes, score)
        ▼                                                   ▼
 render worker process (worker.py) ── render.py ── FluidSynth (subprocess, no shell, timeout)
```

## One musical timeline
`model.py` holds the canonical score model: bars (ticks, labels, pickup), a tempo map and, per voice part, notes
with integer tick durations (480 per quarter). The same model produces:
- the MIDI for each stem (render.py),
- the bar timeline sent to the player (bar start seconds at 100%; other tempos divide exactly by the factor),
- the MusicXML shown in the score view (music21),
- the bar text in the voice-lead editor.
So audio, loops and bar labels cannot disagree about where bar 5 is.

## Import and mapping
`musicxml_import.inspect` walks the MusicXML itself (with `<backup>`, `<forward>`, `<chord>`, staves and voices)
and returns every (part, staff, voice) stream. `propose_mapping` suggests S/A/T/B from part names but marks every
entry unconfirmed. `extract_part` turns one explicitly chosen stream into bars and raises flags rather than guessing.
A version cannot be submitted until all four parts are confirmed (a part may be confirmed as "not in this piece")
and no error-level flag remains.

## Versions and approval
Versions are immutable rows. Edits insert a new version, revoke any approved version of the song, supersede
pending ones and queue a render job. Approval targets one version id and is refused if a newer version exists or
audio is not rendered. Singers are served only the version whose status is `approved`; every other version, and
its files, returns 404 to them.

## Jobs
Jobs live in SQLite (`jobs` table) with status, attempts and error text. The worker claims one job at a time,
bounds work by score size, subprocess timeout and max attempts (3), requeues jobs left "running" by a crash, and
skips jobs for versions that were superseded before rendering. Old drafts' generated audio is deleted.

## Security summary
- Uploads: size limits; MusicXML parsed with defusedxml (entities and external references refused); MXL read in
  memory with member-count, total-size and compression-ratio limits and path checks; audio/PDF checked by magic
  bytes. Stored files get random server-chosen names; user file names are never used on disk or in commands.
- Subprocess: argument list, no shell, timeout.
- Auth: scrypt hashes, random session tokens stored hashed, HttpOnly SameSite=Strict cookie, login throttling.
- CSRF: state-changing requests need the `X-BVC` header (no CORS is enabled).
- Headers: CSP `default-src 'self'`, nosniff, no-referrer, `Cache-Control: no-store` on API and files.
- Files are only reachable through `/api/assets/{random id}` with a role and approval check.

## Hosting path (later, needs approval)
One small EU virtual server (or an existing choir/parish server), Caddy or Nginx for HTTPS, systemd units for
`run_server.py` and `bvc.worker`, nightly backup of the `data/` folder. Migration options if it grows: Postgres
instead of SQLite, object storage for audio. Costs are not estimated here because no provider has been chosen;
get current prices before deciding.
