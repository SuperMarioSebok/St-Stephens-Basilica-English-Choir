# Known limitations (Milestone 1)

## Not production-ready
- Local demo only. No HTTPS, backups, monitoring or hosting set up. Must sit behind HTTPS before real use
  (cookies are marked `Secure` when `BVC_COOKIE_SECURE=1`).
- Login throttling is in memory (resets on restart; per server process).
- No password reset or self-service account management; the director creates accounts with the CLI.
- Single server process + single worker assumed. SQLite is fine for a choir; not for many concurrent writers.

## Music
- **Sound is a General MIDI piano** (FluidR3_GM), not singing and not words. It teaches pitches and rhythm only.
- **Repeats, endings, D.C./D.S./coda are flagged but not expanded**: audio plays bars once in written order.
- Grace and cue notes are skipped (flagged). Unpitched notes, microtones and `score-timewise` files are refused.
- Divisi chords are played in full; the app does not decide who sings which note.
- Lyrics, dynamics, articulations and fermatas are ignored in audio. Fermatas therefore have no hold.
- Tempo changes are honoured from `<sound tempo>`; gradual changes (rit., accel.) are not.
- Transposing-instrument parts (`<transpose>`) are flagged, not converted.
- Note spelling is kept, but the display score is regenerated from the app's model by music21, so its layout
  differs from the printed edition (beaming, system breaks, no lyrics).
- The voice-lead editor works bar by bar in text (`G4:1`). Usable by musicians, not a notation editor.
- Correction re-uploads must keep the same bar structure; structural changes need a new import by the director.
- Rhythm finer than the internal grid (480 per quarter; triplets are fine) is refused.

## Player
- **No moving score cursor.** The bar display is driven by the same timeline as the audio and is verified by tests;
  a visual cursor on the notation is not.
- Speeds are fixed (100/75/50%) because they are rendered from the score. No continuous slider.
- Audio files are uncompressed WAV (22.05 kHz mono): about 40 MB per version for the 25-second test piece at
  three tempos. A 4-minute piece would be roughly 400 MB per version on the server and ~25 MB per tempo per
  part on the phone's data plan. Compressed formats are a backlog item (needs a sync check after decoding).
- Phones decode all four stems into memory. Long pieces at 50% may stress older phones: test before rollout.
- iPhone: Web Audio is silent when the ring/silent switch is on. Playback may stop when the screen locks.
- Fallback recordings: slower speed relies on the browser's pitch-preserving time-stretch; quality varies, and the
  option is hidden where the browser does not offer it.

## Approval behaviour (a policy choice to confirm with the director)
Any edit cancels the current approval, so the song disappears for singers until the new version is approved. This
follows the brief literally. Alternative: keep the last approved version visible until the new one is approved.
That is a small change; choose before the pilot.

## Feedback anonymity
See PRIVACY.md. In a small choir, wording or timing can identify a writer; anonymity is not absolute.

## Not done in this milestone
Practice assignments and self-check, MP4 export, OMR, sol-fa formats, outreach module, recording/pitch analysis,
tour planning: see BACKLOG.md. The reference YouTube playlist was not inspected or downloaded. The build-versus-buy
comparison (Chorilo, ChoirMate, Choir Player, Verovio benchmark) has not been researched yet.
