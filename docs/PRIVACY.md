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

**Not stored anywhere:** practice activity, what anyone played, how long, from which device; IP addresses in the
app database; analytics; advertising or tracking cookies; recordings of singers.

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
