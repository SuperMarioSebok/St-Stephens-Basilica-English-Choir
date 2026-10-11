# Hosting on a small server (test phase)

Goal: an always-on, HTTPS test server that Mario pays for the first 3 months (budget HUF 6,000 in total, about
HUF 2,000 a month), then the choir decides whether to take it over.

## Which server

Prices below come from web searches on 2026-10-11. The providers' own price pages could not be opened from the
environment that wrote this, and third-party sites disagreed, so **check the order page before buying**.
Hungarian private buyers pay **27% VAT** on top of net prices (a VAT-registered organisation may not).
Exchange rate assumed: about 363 HUF per euro (mid-September 2026).

| Option | Size | Net price found | Est. with 27% VAT | 3 months | Contract | Fit |
|---|---|---|---|---|---|---|
| **netcup VPS piko** (Nuremberg) | 1 vCore, 1 GB RAM, 30 GB | €1.54/month (G11s) to €2.21/month (G11.5s) | ≈ €2.0–2.8 ≈ HUF 710–1,020/month | ≈ HUF 2,100–3,100 | **12-month minimum** | Cheapest that works. 1 GB is tight but fine for testing (the setup adds swap). You are committed for a year: ≈ HUF 8,500–12,200 in total |
| **Hetzner Cloud CX23** (Germany/Finland) | 2 vCPU, 4 GB RAM, 40 GB | €5.49–5.99/month (raised twice in 2026) | ≈ €7.0–7.6 ≈ HUF 2,530–2,760/month | ≈ HUF 7,600–8,300 | **Hourly billing, cancel any time** | Most comfortable and flexible; slightly over budget |
| Oracle Cloud Always Free (EU region) | ARM VM | €0 | €0 | €0 | Card needed for identity check | Free but more setup work; availability of free capacity varies |

**Recommendation for your budget:** netcup VPS piko fits HUF 6,000 for 3 months. The catch is the 12-month term:
if the choir does not take it over, you pay the remaining 9 months (roughly HUF 6,000–9,000 more).
If you would rather be able to stop after 3 months, Hetzner CX23 costs about HUF 1,600–2,300 more than the budget
for the 3 months but can be deleted at any time.

Both run Ubuntu 24.04, which the setup script expects.

## A free web address (needed for HTTPS)
Use [DuckDNS](https://www.duckdns.org) (free): log in, create a subdomain such as `stephens-choir-practice`, and
set its IP to your server's IP. Your address becomes `https://stephens-choir-practice.duckdns.org`.
Do not use the Basilica's name or domain without permission from the parish.

## Set it up (about 30 minutes)

1. **Buy the server** with Ubuntu 24.04. Note the IP address and root password (or add your SSH key).
2. **Point DuckDNS** at that IP.
3. **Log in** from your PC (Windows: PowerShell or the Ubuntu window): `ssh root@<server-ip>`
4. **Run the setup**:
   ```bash
   apt-get update && apt-get install -y git
   git clone https://github.com/SuperMarioSebok/St-Stephens-Basilica-English-Choir.git /root/bvc-setup
   # GitHub asks for your username and a personal access token (the repository is private)
   sudo bash /root/bvc-setup/deploy/setup-server.sh stephens-choir-practice.duckdns.org
   ```
   Halfway through it prints a key and waits. On GitHub: repository → **Settings → Deploy keys → Add deploy key**,
   paste it, keep "Allow write access" **unticked**, save, then press Enter on the server.
   Afterwards you can delete `/root/bvc-setup`.
5. **Create accounts** (each asks for a password, 10+ characters):
   ```bash
   sudo bash /opt/bvc/app/deploy/add-user.sh mario director
   sudo bash /opt/bvc/app/deploy/add-user.sh elvis director
   sudo bash /opt/bvc/app/deploy/add-user.sh lead_tenor voice_lead T
   sudo bash /opt/bvc/app/deploy/add-user.sh singer_test singer
   ```
6. **Add the test piece**: log in as `mario`, choose **Add a song**, upload
   `fixtures/morning-light-test-piece.musicxml` from the repository, tick "test piece", and in the rights note
   write "Original test piece written for this project". Confirm the four parts, wait for the audio, approve.
7. Open the address on your Android, then send it to Elvis.

## Looking after it
- **Update** after new code is pushed: `sudo bash /opt/bvc/app/deploy/update.sh`
- **Is it running?** `systemctl status bvc-web bvc-worker`; logs: `journalctl -u bvc-worker -n 50`
- **Backups** are made every night in `/var/backups/bvc` (14 days). Also download one now and then:
  `scp root@<server-ip>:/var/backups/bvc/* .` from your PC.
- Security updates install automatically. The firewall only allows SSH and the website.
- **Handing over to the choir:** give a choir-appointed person the server login and the provider account, or
  move the data: copy `/opt/bvc/data` to the new server and run the same setup there.

## What this does not cover
No email sending, no payment, nothing public beyond the login page (and the page is marked "noindex" for
search engines). Before real choir music goes on it, read `docs/FILES-AND-RIGHTS-NEEDED.md`.
