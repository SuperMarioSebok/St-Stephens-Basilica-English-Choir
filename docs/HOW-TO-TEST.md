# How to run, test and share Basilica Voice Coach

Plain-English guide for Mario (who runs it), the Music Director and the voice leads.

**Only Mario installs anything.** The app runs on Mario's computer. Everyone else just opens a link in their
phone or PC browser and logs in. Nothing needs installing on the Music Director's PC or iPhone.

---

## Part 1. Mario: run it on your PC (once, about 30 minutes)

### Windows
The easiest route is Windows' built-in Linux (WSL). Open **PowerShell as administrator**:
```
wsl --install -d Ubuntu
```
Restart, open **Ubuntu** from the Start menu, choose a username and password, then follow the Linux steps below
inside that Ubuntu window.

### Mac
Install [Homebrew](https://brew.sh), then: `brew install python node fluid-synth git`. Download the FluidR3_GM
SoundFont (MIT licence) and before starting the app run
`export BVC_SOUNDFONT=/path/to/FluidR3_GM.sf2`. Then follow the steps below from step 2.

### Linux / WSL Ubuntu
```bash
# 1. Tools
sudo apt-get update
sudo apt-get install -y git python3-venv nodejs npm fluidsynth fluid-soundfont-gm
# (Node must be version 20 or newer: check with `node -v`. If older, install from https://nodejs.org)

# 2. Get the code (the repository is public, so no login is needed)
git clone https://github.com/SuperMarioSebok/St-Stephens-Basilica-English-Choir.git
cd St-Stephens-Basilica-English-Choir

# 3. Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Frontend (the phone screens)
cd ../frontend
npm ci
npm run build

# 5. Check everything works: all automated tests should pass
cd ../backend
python -m pytest -q
cd ../frontend && npm test && cd ../backend

# 6. Demo data: demo accounts + the original test piece. WRITE DOWN the password it prints.
python -m bvc.cli --data-dir ../data demo
```

### Start it (every time you want to test)
Open **two** terminal windows, in each one: `cd St-Stephens-Basilica-English-Choir/backend && source .venv/bin/activate`
```bash
# Window 1: the app
python run_server.py --data-dir ../data
# Window 2: the audio maker (must run too, or songs stay at "audio queued")
python -m bvc.worker --data-dir ../data
```
Open **http://127.0.0.1:8000** on the PC and log in as `director` with the demo password.

Stop with `Ctrl+C` in both windows. Your data stays in the `data` folder.

---

## Part 2. Mario: test on your Android phone

The phone needs to reach your PC. Two options:

**A. Secure link (recommended; also what you will use for the Music Director).** Install the free Cloudflare tool
`cloudflared` ([download page](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/);
on Ubuntu/WSL: download the `.deb` from that page and `sudo dpkg -i cloudflared-linux-amd64.deb`). No account is
needed. Start the app with secure cookies, then the tunnel in a **third** window:
```bash
# Window 1 instead of the command above:
BVC_COOKIE_SECURE=1 python run_server.py --data-dir ../data
# Window 3:
cloudflared tunnel --url http://localhost:8000
```
It prints an address like `https://some-random-words.trycloudflare.com`. Open that on the phone.

**B. Same Wi-Fi only (Linux or Mac, not WSL):** `python run_server.py --data-dir ../data --host 0.0.0.0`, then on
the phone open `http://<your PC's IP address>:8000`. Some phones restrict audio on plain `http`, so prefer option A.

**About the secure link:** anyone with the address sees the login page, so only send it privately, give each
person their own password, and close the tunnel (`Ctrl+C`) after the test session. The address changes every
time you start it. Your PC must stay on and awake while others test.

---

## Part 3. Mario: create real accounts (instead of sharing the demo password)

```bash
python -m bvc.cli --data-dir ../data add-user music_director --role director --name "Music Director"
python -m bvc.cli --data-dir ../data add-user lead_soprano --role voice_lead --part S --name "Soprano lead"
python -m bvc.cli --data-dir ../data add-user lead_alto    --role voice_lead --part A --name "Alto lead"
python -m bvc.cli --data-dir ../data add-user lead_tenor   --role voice_lead --part T --name "Tenor lead"
python -m bvc.cli --data-dir ../data add-user lead_bass    --role voice_lead --part B --name "Bass lead"
```
Each command asks for a password (10+ characters). Send each person their username and password **in a private
message**, never in a group chat.

To test the singer's view, the Music Director and the leads can also use the demo `singer` account.

---

## Part 4. The test plan

The app currently holds only **"Morning Light"**, a short piece written for testing. It is not a choir
arrangement. Real pieces come later, once we have the files and permission.

### Round 1. Mario alone (PC + Android, about 45 minutes)
Do this before sending anything to the Music Director.
1. Everything in `docs/DEMO-WALKTHROUGH.md`, on the PC.
2. On Android: log in as `singer`, press Practise, play, switch Tenor alone / louder / full choir, slow to 50%,
   repeat bars 4 to 5, show the score, send a feedback note.
3. Write down anything confusing or broken. Fix or note it before Round 2.

**Pass:** you could do all of it on the phone without help, and the sound matched the score.

### Round 1b. New community features (Mario, about 30 minutes)
Do this right after updating the server (`sudo bash /opt/bvc/app/deploy/update.sh`). Full guide: `docs/COMMUNITY.md`.
1. **Public page:** log in as a director → Songs → **Community** → **Public page**. Fill in the rehearsal times and
   the sign-up deadline (2026-10-24). Press **Preview the page**. Do **not** publish until the wording is approved.
2. **Concert:** **Events** → Add an event with the real date once known; tick "Show on the public page" and, if
   wanted, "Allow free reservations". Check the countdown on the preview.
3. **Form:** in a private browser window (logged out), open the page once it is published (or test on the server
   before announcing it) and send yourself an enquiry; try "I am under 18" and check that a parent or guardian is
   required.
4. **Tracker:** **Enquiries** → move your test entry to "On probation" → **Create app invite** → open the link on
   your Android phone → choose a username and password → you land on the songs page.
5. **Survey:** **Member survey** → open "Test" → answer it on the phone → close it → delete nothing (results stay
   hidden under 5 answers; that is expected).
6. **Videos:** on the test piece's **Review** page → **Make practice videos** → wait a minute → Refresh → play one.
7. Delete your test enquiry afterwards.

**Pass:** each step works on the PC and the Android phone; the public page is still unpublished until the wording
is approved.

### Round 2. The Music Director (their PC + iPhone, about 30 minutes, then a 15-minute call)
Before they start: on the iPhone, **turn the silent switch off** (otherwise there is no sound) and use headphones.

Ask them to try, in this order:
1. **As a singer** (demo `singer` account, iPhone): open the song, press Play, choose their own voice part, try
   "alone", "louder" and "full choir", slow it down to 50%, repeat a couple of bars, open the score.
2. **Send a test feedback note** ("Report a problem").
3. **As the director** (their own account, on the PC): open Review, look at the part mapping and "Things to check",
   listen, approve or request changes, and read the feedback note (it shows no name and no time).

Questions for the call:
- Was it easy to use on the iPhone? What was confusing?
- Did the parts sound right and together? Was the slow version useful?
- Would this help singers arrive at rehearsal knowing their notes?
- Who should be the four voice leads for the next round?
- Which real piece would they like to try first, and is there a MusicXML or notation file for it?
- What would make them say "stop, this isn't helping"?

**Pass:** the Music Director is comfortable with it and says yes to Round 3. Nothing goes to voice leads without their yes.

### Round 3. Voice leads (each on their own phone, about 2 weeks)
The Music Director invites them, or agrees that Mario does. Each lead:
1. Practises as a singer (their part alone and louder, slow, repeat bars).
2. Opens **Edit my part**, makes one small deliberate change to their own part, presses the "Original, then edit"
   button to hear it, and saves it. They will see the song disappear from the singer view until the Music Director approves:
   that is how it should work.
3. Adds a review note and presses **Submit for review**.
4. The Music Director listens and approves or requests changes.
5. Everyone fills in the checklist in `docs/TEST-CHECKLISTS.md` (sections B and D) and notes phone model and
   anything that failed.

Then a 20-minute debrief: did it work on every phone, how many minutes did it cost each person, is it ready for
a real piece?

**Pass (Gate 1):** works on every leader's phone (or the problem is understood), parts sound right, workload is
acceptable, the Music Director is happy to move to a real piece and later to all members.

### After that
Real pieces (needs files and permission), then a 3-week pilot with all members if the Music Director agrees. See
`docs/CHANGE-MANAGEMENT.md`.

---

## If something goes wrong

| Problem | Fix |
|---|---|
| No sound on iPhone | Silent switch off, volume up, press Play again |
| "Audio is not ready yet" or "audio queued" | Window 2 (the worker) is not running; start it |
| Link stopped working | The tunnel was closed or the PC slept; restart it and send the new link |
| Can't log in after many tries | Wait 15 minutes (login lock) |
| `fluidsynth` or SoundFont not found | Re-run the install step, or set `BVC_SOUNDFONT` to the `.sf2` file |
| `demo` says users already exist | The demo runs only on an empty data folder; it was already done |

---

## Part 5. Should it run in the cloud for free?

**For the tests above: not needed.** Mario's PC plus the free Cloudflare link costs nothing and is enough for
the Music Director and the voice leads. The only downside is that the PC must be on during testing.

**For the pilot with all members** the app should be online all the time. It needs a server that can install
FluidSynth, keep files on disk (the database and audio) and run the audio worker in the background. That rules
out most "free app hosting" plans:

| Option | Free? | Fits this app? |
|---|---|---|
| Mario's PC + Cloudflare link | Yes | Yes for testing; not for a pilot (PC must stay on) |
| Free "app hosting" tiers (Render, Hugging Face Spaces, PythonAnywhere, ...) | Yes | **No**: they sleep when idle and/or lose files on restart, or cannot install FluidSynth or run a worker |
| Oracle Cloud "Always Free" virtual machine, EU region | Yes (asks for a card to verify identity) | **Yes**: a real small server. Needs someone comfortable with Linux setup and updates |
| Google Cloud free small VM | Yes | Technically yes, but the free tier is in US regions only: not ideal for EU choir data |
| Small paid EU server (e.g. Hetzner, OVH, Scaleway) | No, typically a few euros a month (check current prices) | **Yes**, simplest and most reliable |

Free-tier rules change often: check the provider's current terms before relying on one. Nothing is signed up for
or deployed until the choir agrees who runs and pays for it (see `docs/FILES-AND-RIGHTS-NEEDED.md`, item 12).
