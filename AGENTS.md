# AUTOLAB

Infrastructure as code for a homelab. `main` is production: a merge can
deploy. Changes go through a pull request, squash-merged.

- Vocabulary: `CONTEXT.md`.
- How each concern works and why: `docs/gitops/`, one page per concern.
- Adding, removing, renaming or moving a service or machine, or changing
  its port, login or what an agent reaches: follow
  `docs/gitops/definition-of-done.md` so home, dash and the docs match what
  is deployed.
- Pocket ID groups, logins and users, and which of them are code:
  `docs/gitops/pocket-id.md`.
- Recurring jobs (a new VM, a service, a deploy, updates, a restore) have
  agent skills in `.claude/skills/`. The list is in `write-skill`.
- Contribution rules, commits, docs style: `CONTRIBUTING.md`.
