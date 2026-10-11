# Demo walkthrough (about 15 minutes)

Uses only the original test piece "Morning Light". Start from a fresh data folder:

```bash
cd backend
python -m bvc.cli --data-dir ../data-demo demo     # note the printed password
python run_server.py --data-dir ../data-demo       # terminal 1
python -m bvc.worker --data-dir ../data-demo       # terminal 2
```

Open `http://127.0.0.1:8000`. Use a phone-sized window (browser dev tools, 390 px wide) to see the real layout.

## 1. Singer sees nothing yet
Log in as `singer`. The song list is empty: the imported song is a draft. Log out.

## 2. Director checks the import
Log in as `director` → **Review** on "Morning Light".
- **Part mapping**: each part shows a proposed source (e.g. "Tenor · staff 1 · voice 1 · 27 notes, F#3–E4") and
  "not confirmed".
- **Audio**: status `done` (or `queued` until the worker picks it up; press Refresh).
- **Decision** lists why it is not ready: four mappings unconfirmed.
- Press **Confirm all four as shown**. A new version (v2) is created and rendered.

Optional: upload `fixtures/morning-light-shared-staves.musicxml` via **Add a song** to see shared-staff and
divisi flags, or `fixtures/morning-light-tenor-octave.musicxml` to see the tenor octave warning. Fix it by
choosing "Sing one octave lower than written" for the tenor.

## 3. Voice Lead edits only their part
Log in as `lead_t` → **Edit my part**.
- Change bar 1 from `B3:1 B3:1 C4:1 G3:1` to `B3:1 B3:1 C4:1`: the row says "Adds up to 3 beats; this bar needs 4".
- Make it `B3:1 B3:1 C4:1 A3:1`. Press **▶ Original, then edit** to hear both.
- Add a summary and **Save 1 changed bar as a new version**. You land on v3.
- Try another part: the API refuses (the UI only shows your part). `lead_s` cannot edit the tenor either.
- Add a **review note**, wait for audio (reload), then **Submit for review**.

## 4. Director approves
Log in as `director` → **Review**. Listen in the embedded player (switch part, slow down, repeat bars), read the
flags and **History and notes** (shows "lead_t … bar 1: … → …"). Press **Approve for singers**.

## 5. Singer practises
Log in as `singer` → **Practise**.
- Part defaults to the singer's part (Tenor). **Tenor alone / Tenor louder / Full choir**.
- **Play**, then **50%**: same pitch, slower, position kept.
- **Repeat bars** 4 to 5 → **Repeat**. The bar display stays in 4–5.
- **Jump to bar**, **Mute or solo single parts**, **Show score**.
- **Report a problem in bar N** → send a comment.

## 6. Approval cancelled by an edit
As `lead_t`, change any bar and save. As `singer`, the song has disappeared until the director approves the new
version. This is deliberate (see LIMITATIONS for the alternative).

## 7. Director reads feedback
`director` → **Read feedback**: song, bar, comment and ISO week only.

## 8. Fallback path
`director` → **Add a song** → **Recording plus PDF**. Use only a recording you have the right to use (for example
one you made yourself). Approve it like any version. Singers get time-based repeats and a PDF button.
