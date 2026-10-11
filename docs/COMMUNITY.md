# Community features: recruiting, events, invites, member survey

Everything here lives in the same app as the practice player. Log in, then press **Community** on the songs page.

## Who sees what

| Role | Can do |
|---|---|
| **Director** | Everything: edit and publish the public page, events, enquiries, invites, member survey, Friday numbers |
| **Welcome team** (`welcome`) | Read and update enquiries; see reservations; see counts. Cannot publish or invite |
| **Communications team** (`comms`) | See counts and events; type the Friday numbers. Never sees names or contact details |
| Singers and voice leads | Answer the member survey; nothing else here |

Create team accounts with an invite (Community → Invites) or on the server:
`sudo bash /opt/bvc/app/deploy/add-user.sh comms_member comms`.

## 1. The "Come sing with us" page
Address: `https://<your-address>/#/join`. It stays **hidden until a director presses Publish**.
1. Community → **Public page**: edit the wording (rehearsal times and place, sign-up deadline, etc.).
2. Press **Preview the page** and send the wording for approval (the parish priest and the choir master).
3. Once approved, press **Publish**.
4. Print the QR code shown on that tab for posters and the church door.

The page shows a countdown to the sign-up deadline and to the next public event, the interest form, upcoming
events with **Reserve a place**, and **Share** buttons (WhatsApp, Facebook, copy link).

Links carry only the channel they were shared through (`?src=whatsapp`, `?src=qr` …), so we can see which channels
work. They never record who shared them.

## 2. Enquiries (interest form)
- The form asks for a first name, email or phone, what they'd like to do (sing, volunteer, support, come to the
  concert), voice type (only for singers) and an optional message.
- Consent is required. **Under-18s must give a parent or guardian's name and contact, and the parent or guardian
  must agree.** Contact the parent or guardian, not the young person.
- "Keep me updated about concerts" is a separate, optional box. Only contact people about concerts if they ticked it.
- Community → **Enquiries**: move each person along: New → Contacted → Came to a rehearsal → On probation →
  Joined (or Volunteer, Not now). Add notes.
- When someone is **On probation**, a director can press **Create app invite**: the person gets their practice
  account and their enquiry record is deleted (the anonymous counts stay).
- Entries are deleted automatically **6 months after their last change**.

## 3. Events, countdowns and reservations
- Community → **Events** → Add an event (e.g. the Christmas Concert). Tick **Show on the public page** for the
  countdown and **Allow free reservations** if you want people to pre-book. Set the number of places if seating is
  limited.
- Each event has its own page (`#/event/<number>`) and QR code to share.
- People who reserve get a code to cancel. Reservation details are deleted **30 days after the event**; the total
  is kept.
- After the event, enter the **headcount** and the **donations reported by the parish or charity**. The choir
  never handles money; this is only for measuring.

## 4. Invites (easy sign-in)
Community → **Invites**: name, role, voice part → **Create invite**. Send the link privately or show the QR code.
It works once and expires after 14 days. **New link** replaces an old or expired one.

## 5. Member survey (NPS)
Community → **Member survey** → open a survey with a title (e.g. "Baseline, November 2026"). Members see one
question on their songs page: *How likely are you to recommend singing with our choir to a friend? (0–10)* plus an
optional comment.
- Answers are stored **without names**. The app only notes that someone answered, so they aren't asked twice.
- Results (score from −100 to +100) appear once **at least 5 people** have answered.
- Suggested rounds: a baseline in early November and a second one the week after the Christmas Concert.

## 6. This week (KPIs)
Counts per week: new enquiries, how many want to sing or help, contacted, first rehearsals, on probation, joined.
No names. Download the last 12 weeks as CSV for the Friday check.
**Friday numbers**: type follower counts and attendance from each platform each Friday.

## Practice videos (Playlist Factory, first slice)
On a song's **Review** page (director): **Make practice videos**. The worker makes private MP4s for each part
(alone and louder) plus the full choir, at 100% and 75% speed, with the bar number on screen, plus a
`playlist.json` listing them in order. Singers see them under **Practice videos** in the player once the version
is approved. Nothing is uploaded anywhere.
