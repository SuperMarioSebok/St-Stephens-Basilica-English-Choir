# Test checklists

Automated tests prove the logic. These checklists cover what only people can judge: does it sound right, is it
usable on real phones, does it help rehearsal. **The Music Director and the four Voice Leads run sections A–C
before any choir member sees the app** (see CHANGE-MANAGEMENT.md, Stage 1).

Record results in a simple table: tester, device/browser, item, pass/fail, note. Do not record singers' names
in pilot feedback.

## A. Director review checklist (per song version, before approving)

- [ ] Title, composer/arranger and edition match the printed copy the choir sings from.
- [ ] Rights note says who permitted member-practice use, and it is true.
- [ ] Each of S, A, T, B is mapped to the right staff and voice; "confirmed by" shows a real person.
- [ ] Every flag under "Things to check" is understood: shared staves, divisi, possible unisons, tenor octave,
      repeats/endings (NOT expanded in audio), tempo changes, grace notes skipped.
- [ ] Bar numbers in the player match the printed copy (pickup shown as bar 0).
- [ ] Tempo at 100% is the tempo you want people to learn at.
- [ ] Listening checks in section C pass for every part.
- [ ] History shows no unexplained changes since the last approved version.
- [ ] Decision: approve, or request changes with a note saying what to fix.

## B. Phone-browser checklist

Test on at least: one recent iPhone (Safari), one older iPhone if available, one recent Android (Chrome), one
budget Android, one tablet or laptop. Note OS and browser version.

| # | Check | Expected |
|---|---|---|
| B1 | Open the address, log in | Large readable form, no zooming needed, password manager works |
| B2 | Song list | Only approved songs, test piece labelled as a test |
| B3 | Practise → Play | Sound within ~2 s on Wi-Fi; on iPhone check the **silent switch is off** (Web Audio is muted by it) |
| B4 | Tenor alone / louder / full choir | Change is immediate, no restart, no clicks |
| B5 | Speed 75% and 50% | Slower, **same pitch**, continues from the same bar |
| B6 | Repeat bars 4 to 5 | Repeats seamlessly; no drift between parts after 10 repeats |
| B7 | Jump to bar, seek slider | Lands on the right bar; all parts together |
| B8 | Mute / solo | Works per part |
| B9 | Show score | Readable after pinch-zoom; bar numbers visible |
| B10 | Lock the screen while playing, unlock | Note behaviour (may pause on iOS; acceptable, record it) |
| B11 | Phone call / headphones unplugged | Note behaviour |
| B12 | Mobile data (4G) | Load time acceptable for a 3-minute piece (record seconds) |
| B13 | Report a problem | Bar pre-selected; sends; thank-you screen |
| B14 | Large text setting (accessibility) | Layout still usable |
| B15 | Dark mode | Readable |
| B16 | Logged out after 30 days / log out button | Returns to login |
| B17 | Over plain HTTP on LAN | Some browsers block audio features without HTTPS; record. Real hosting must use HTTPS. |

## C. Listening checklist (per part, at 100% and 50%)

Use headphones, with the printed score in hand.

- [ ] Every pitch matches the printed part (play "part alone"). Mark wrong bars as review notes.
- [ ] Octave is right (tenor especially; a tenor line sounding an octave high is the classic error).
- [ ] Rhythm and ties match; held notes are held, not re-struck.
- [ ] At 50%, pitch is identical to 100% (compare one long note).
- [ ] "Part louder": your part is clearly audible over the others.
- [ ] Full choir: parts sound together, no part early or late, including after jumping and looping.
- [ ] Divisi passages: you know what you should sing (the app plays both notes).
- [ ] Repeats/endings: audio plays bars once in written order. If the piece has repeats, decide whether that
      is acceptable for practice or whether the score must be written out.
- [ ] The piano sound is acceptable for learning notes (it is not sung text).

## D. Voice Lead editor checklist

- [ ] You can open only your own part for editing.
- [ ] A deliberately wrong bar length shows a clear error before saving.
- [ ] Before/after preview helps you hear the change.
- [ ] After saving, the song disappears for singers until the director approves (expected).
- [ ] Re-uploading a corrected MusicXML changes only your part.
- [ ] Your change appears in History with your name and the bars changed.
