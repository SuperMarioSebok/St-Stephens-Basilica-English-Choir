# Change management and rollout plan

**Goal:** better use of rehearsal time (less note-learning, more ensemble music) and stronger engagement of
singers, leaders, sponsors and partner choirs, introduced in a way that respects the Music Director's authority
and singers' privacy.

> The Choir Charter was mentioned but was not included in the upload. Once it is shared, align the roles,
> decision rules and goals below with it. Nothing here is agreed yet: this is a proposal for the Music Director.

## 1. Principles

1. **The rehearsal comes first.** The app supports home practice; it never replaces the director's teaching or
   interpretation.
2. **The Music Director decides musical questions.** Nothing reaches singers without the director's approval.
3. **Leaders test before members.** The director and the four voice leads use it first, on their own phones,
   with real music, before anyone else is asked to.
4. **Voluntary and no surveillance.** Nobody is tracked, ranked or checked for practice. Using paper and
   rehearsal only remains fine.
5. **Rights first.** Only material with written permission is loaded.
6. **Small steps with exit points.** Each stage ends with a go, adjust or stop decision.

## 2. Stakeholders

| Stakeholder | Interest | Influence | What they need from us | Involvement |
|---|---|---|---|---|
| **Music Director** (Elvis) | Rehearsal quality, musical accuracy, own time | Decisive | Short proposal, control over approval, low workload, the right to stop | Sponsor and approver; agrees on success/stop criteria |
| **Voice leads** (S, A, T, B) | Their section learning notes correctly | High | Editing rights for their own part only, clear workload limits, recognition | Co-testers, part owners, first-line helpers for their section |
| **Choir members** | Learning notes easily; not being judged | Collectively high | Simple phone use, large buttons, privacy, optional | Pilot users; anonymous feedback |
| **Choir coordinator / committee** | Organisation, communication, reputation | Medium–high | Clear plan, no extra admin, fit with the Charter | Approves communication and the rollout calendar |
| **Basilica / parish leadership** | Liturgy, reputation, use of the Basilica name | High for public matters | Assurance that practice is private and nothing is published in their name | Informed before any public or sponsor activity |
| **Rights holders** (publishers, arrangers) | Copyright | Veto per piece | A specific, written permission request | Asked per piece, before loading |
| **Project lead / volunteer developer** | Delivering something useful and maintainable | Medium | Honest feedback and clear decisions | Builds, supports, reports maintenance effort |
| **Hosting / IT volunteer** (to be found) | Reliability, security | Medium | Simple deployment, backups | From Stage 2 |
| **Potential sponsors** | Visible community value | Later | Honest results, no inflated claims | Stage 4 only |
| **Partner choirs** (Hungary, Europe, worldwide) | Shared methods, exchange | Later | A reusable, documented method; respectful collaboration | Stage 4 only |

## 3. Who decides what (RACI)

R = does the work, A = accountable/decides, C = consulted, I = informed

| Decision or task | Music Director | Voice leads | Coordinator | Project lead | Members |
|---|---|---|---|---|---|
| Whether to run a pilot at all | **A** | C | C | R (proposes) | I |
| Which piece(s) and when | **A** | C | I | C | I |
| Success and stop criteria | **A** | C | C | R (drafts) | I |
| Part mapping and note corrections | C | **R** (own part) | | C | |
| Approving a song version for singers | **A/R** | C | | | I |
| Announcing the pilot to the choir | **A** | C | R | C (drafts text) | I |
| Accounts and passwords | I | | **A** | R | |
| Reading anonymous feedback | **A/R** | (if agreed) | | | |
| Continue, adjust or stop after the pilot | **A** | C | C | C | C (survey) |
| Any public, sponsor or partner-choir activity | C | C | **A** (with parish) | R | I |

## 4. Staged rollout

### Stage 0. Agreement with the Music Director (1 meeting, about 30 minutes)
- Show the demo with the original test piece (DEMO-WALKTHROUGH.md).
- Agree: one first piece, its source files and permission, the pilot dates, success/stop criteria (section 6),
  the maximum time voice leads will spend, and who reads feedback.
- Decide the approval policy (does an edit hide the song until re-approved?) and whether the pilot is for all
  members (your stated preference) or starts tenor-only, as originally proposed.
- **Gate 0:** the director says yes, in their own words, to a specific plan. No date is fixed before this.

### Stage 1. Leader acceptance test (about 2 weeks)
Participants: the Music Director and the four voice leads only.
1. **Week A, the test piece:** each person logs in on their own phone and works through TEST-CHECKLISTS.md
   sections B and D. Voice leads try one deliberate edit and see it go through review.
2. **Week B, the first real piece:** voice leads confirm the mapping and listen to their part against the printed
   copy (section C). The director runs section A and approves.
3. A 20-minute debrief: problems found, fixes needed, workload per person (minutes), readiness for members.
- **Gate 1 (all must be true):** every part was heard and confirmed correct by its voice lead; the app worked on
  every leader's phone, or the problem is understood; leader workload fits what they agreed; the director is
  comfortable showing it to the choir.

### Stage 2. Pilot with all choir members (3 weeks)
Introduce it at rehearsal, led by the director (not by the developer): a 5-minute live demo on a projector or
phone, a printed one-page guide with the address, and voice leads as helpers for their section.

| Week | Focus | Leaders' role | What we learn |
|---|---|---|---|
| 1 | Onboarding and one piece. Everyone logs in, finds their part, plays it alone, then "louder" | Voice leads help in the break; collect "couldn't log in" cases | Can people use it? Which phones fail? |
| 2 | Difficult passages. The director names 2–3 bar ranges to practise with **Repeat bars** at 75% or 50% | Voice leads mention the bars in rehearsal; check whether they improved | Does targeted home practice show up in rehearsal? |
| 3 | Rehearsal usefulness and feedback. Short anonymous survey; feedback form open all week | Director estimates rehearsal minutes spent on note-learning for this piece compared with a similar earlier piece | Was it worth it? What should change? |

Members who prefer not to use phones are not chased or counted. Nobody's usage is recorded.

- **Gate 2:** review against the agreed criteria → continue, adjust, or stop. The director decides.

### Stage 3. Regular use (after a positive Gate 2)
Add repertoire at a pace voice leads can sustain (suggestion: at most one new piece every two weeks). Move to
proper HTTPS hosting with backups. Review every term.

### Stage 4. Sponsors and exchange with other choirs (separate workstream, later)
Only after Stage 3 shows value, and with the coordinator's and the parish's agreement:
- **Sponsors:** a short, honest brief (what the choir does, what the pilot showed, what support would allow).
  Draft for review; nothing sent automatically.
- **Partner choirs in Hungary, Europe and worldwide:** share the method, not our members' data. Offer the
  open-source code once its licence is chosen, the test piece, the checklists, and an online exchange session.
  Ideas: a joint practice-track workshop, swapping permitted arrangements, singing visits. Each choir keeps its own
  installation, repertoire, rights and reviewers.
- Public content (Instagram, Facebook, YouTube) follows the outreach module's approval rules: consent for
  identifiable singers, no copyrighted rehearsal tracks, choir reviewer approves exact content. Channel ownership
  and admin rights must be confirmed first.

## 5. Communication plan

| When | Who to whom | Message | Channel |
|---|---|---|---|
| Stage 0 | Project lead → Director | Proposal and demo | In person |
| Start of Stage 1 | Director → voice leads | Invitation to test, time expected, what feedback is wanted | In person or direct message |
| Gate 1 | Director → committee | Ready for a pilot; plan and dates | Meeting |
| Pilot week 1 | Director → choir | What it is, that it is optional and private, how to log in | Rehearsal + printed guide; WhatsApp text drafted for the director to send |
| Each pilot week | Director → choir | This week's focus (piece, bars) | Rehearsal; optional WhatsApp |
| End of pilot | Director → choir | Thank you, what we learned, what happens next | Rehearsal |
| Stage 4 | Coordinator → sponsors / partner choirs | Brief and invitation | Reviewed drafts only |

Drafts can be prepared, but nothing is sent on anyone's behalf, and a chat reaction is not taken as approval.

## 6. Proposed success and stop criteria (to agree with the Music Director)

Measure usefulness and effort, not individual singers.

| Measure | How | Proposed target |
|---|---|---|
| Rehearsal time on note-learning for the pilot piece | Director's estimate, compared with a similar earlier piece | Noticeably lower, in the director's judgement |
| Accuracy of practice audio | Wrong notes reported in approved versions | None left unfixed for more than one week |
| Usefulness for singers | Anonymous end-of-pilot survey (3 questions, 1–5 scale + one comment) | Most respondents rate it 4 or 5 |
| Usability | Voice leads' log of people who could not get it working | Every case solved or explained |
| Leader workload | Minutes per week each voice lead and the director spend | Within what they agreed in Stage 0 |
| Volunteer maintenance | Hours per week for the project lead | Sustainable (agree a ceiling, e.g. 2 hours) |

**Stop or pause if:** the director judges it distracting, approved audio is found wrong twice, leader workload
exceeds what was agreed, a rights question is raised, or privacy concerns are raised and cannot be resolved quickly.

## 7. Likely concerns and responses

| Concern | Response |
|---|---|
| "I'm not good with technology." | Optional; voice leads help; large buttons; one address; no install. |
| "Will they see whether I practised?" | No. The app records no practice activity. Feedback is stored without names. |
| "The piano doesn't sound like singing." | True; it is for notes and rhythm. Interpretation comes from rehearsal. |
| "What if the notes are wrong?" | Voice leads check every part; the director approves; singers can report a bar. |
| "More work for leaders." | Limits agreed up front; one piece at a time; workload is a stop criterion. |
| "Is this allowed (copyright)?" | Only pieces with written permission; members-only; recorded per song. |
| "Does this replace the director?" | No. The director controls what is published and how it is used. |

## 8. Agenda for the Stage 0 meeting (30 minutes)

1. The problem in the director's words: where does rehearsal time go? (5 min)
2. Demo on a phone with the test piece (8 min)
3. Choose the first piece; check what source file exists and who can give permission (5 min)
4. Pilot shape: all members or tenor first; dates; who reads feedback; approval policy (7 min)
5. Success and stop criteria; leaders' time budget (5 min)
