# Contributing

Thank you for helping the English Choir of St. Stephen's Basilica. This is a volunteer project; small,
careful changes are the most welcome.

## How a change happens
1. **Issue.** Describe the problem or idea in a GitHub issue (use the templates). Agree on it before coding.
2. **Branch.** Create a branch from `main`, e.g. `feature/interest-form` or `fix/audio-loop`.
3. **Pull request.** Push the branch and open a pull request. Fill in the template.
4. **One review.** Someone else from the team reviews it.
5. **Tests green.** The automatic checks (GitHub Actions) must pass.
6. **Merge.** The reviewer merges. Then Mario updates the server with `sudo bash /opt/bvc/app/deploy/update.sh`.

Nobody merges their own pull request, and nobody pushes directly to `main`.

## Run the tests before you open a pull request
```bash
cd backend && python -m pytest -q
cd ../frontend && npm test && npm run typecheck
```
Setup instructions are in [docs/HOW-TO-TEST.md](docs/HOW-TO-TEST.md).

## A good pull request description
- **What** changed, in one or two plain sentences.
- **Why**: link the issue.
- **How you tested it**: tests, and what you tried on a phone.
- **Anything people must do**: a new setting, a server command, wording to approve.

## House rules
- The repository is public. Read the "Never commit" list in [docs/HOSTING.md](docs/HOSTING.md).
- We are "the English Choir of St. Stephen's Basilica", never "the Basilica Choir".
- Nothing in the app posts, sends or publishes on anyone's behalf.
- Personal data: collect the minimum, ask for consent, delete on schedule ([docs/PRIVACY.md](docs/PRIVACY.md)).
- Plain English in the interface: short sentences, no jargon.
