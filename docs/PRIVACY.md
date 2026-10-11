# Privacy and data (Milestone 1)

Written for a Hungarian/EU community choir. This is a technical description, not legal advice; have the choir's
data-protection contact review it before launch.

## What is stored

| Data | Where | Who sees it | Retention |
|---|---|---|---|
| Account: username, display name, role, voice part, password hash (scrypt) | SQLite | Director (via database) | Until the account is deleted |
| Session: hashed token, expiry | SQLite | Nobody (used for login) | 30 days, purged on login |
| Song files, versions, mapping, history (who changed what, when) | SQLite + private storage folder | Director, voice leads | Kept for audit; generated audio of old drafts is deleted automatically |
| Review notes (named) | SQLite | Director, voice leads | With the song |
| **Feedback**: song, optional bar, comment, ISO week | SQLite | Director | Suggest deleting after the pilot review (manual for now) |

| **Enquiries** (public interest form): first name, email or phone, interests, voice type, message, parent or guardian's name and contact for under-18s, whether they want concert news, the channel they came from | SQLite | Directors and the welcome team | Deleted 6 months after the last status change, or when the person joins with an invite |
| **Reservations**: first name, email or phone, number of people, the channel | SQLite | Directors and the welcome team | Deleted 30 days after the event; only the total is kept |
| **Weekly counts** of enquiries and statuses | SQLite | Directors, welcome and comms teams | Kept; contain no names |
| **Invites**: name, role, voice part, a hashed one-time token | SQLite | Directors | Kept with the account history |
| **Member survey**: score 0–10 and optional comment, with no user id; separately, a keyed hash noting that a member answered | SQLite | Directors (results only once 5+ answers) | Until the survey is deleted |
| **Friday numbers** (followers, headcounts) | SQLite | Directors, welcome and comms teams | Kept; contain no names |

**Rate limiting:** the public forms count submissions per network address **in memory only** for 10 minutes, to
stop spam. Addresses are never written to disk.

**Not stored anywhere:** practice activity, what anyone played, how long, from which device; IP addresses in the
app database; analytics; advertising or tracking cookies; recordings of singers.

## Children
Anyone who ticks "I am under 18" must give a parent or guardian's name and contact, and the parent or guardian
must agree. The welcome team contacts the parent or guardian. No photos or videos of children are published
without written parental consent.

## Cookies
One strictly necessary cookie, `bvc_session` (HttpOnly, SameSite=Strict), to keep you logged in. No others.

## Feedback anonymity, and its limits
- The feedback table has no user, session, version or timestamp column; this is enforced by a test.
- The server stores the ISO week only; the list is shuffled within a week.
- You must be logged in to send feedback (keeps the app private), but the account is not passed to storage.
- The web server's access log is **switched off** (`run_server.py`). A reverse proxy or host (e.g. Nginx, Caddy,
  a cloud provider) in front of the app may log requests with IP and time; configure it to not log
  `/api/feedback`, or to drop IPs, before launch.
- **Limits:** in a small choir, writing style, the bar mentioned, or the fact that only one tenor practised that
  week can identify someone. We say "not stored with your name", never "completely anonymous".

## Data minimisation and deletion
- No email addresses are required. Accounts can use first names or nicknames.
- Deleting a user: set `active = 0` (keeps history readable) or remove the row once their history is no longer
  needed. A CLI command for this is in the backlog.
- Hosting: prefer an EU-based server. Do not send scores or feedback to third-party AI or cloud services without
  the choir's approval; this app does not.
