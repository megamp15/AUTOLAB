---
name: pull-request
description: Make a change to AUTOLAB the way the repository expects - branch, checks, commit, pull request, squash merge. Use for every change, and when CI fails on a pull request.
---

# A change, as a pull request

`main` is production: a merge can deploy. Rules are in `CONTRIBUTING.md`.

## Steps

1. Branch from an up-to-date `main`: `feat/<what>`, `fix/<what>`, `docs/<what>`.
2. Make the change. One concern per pull request.
3. Run the checks that read what you touched. Done when each exits 0.

   | touched | check |
   |---|---|
   | anything under `scripts/`, a role's template or defaults, `pocketid-clients.json`, the catalog | `python3 -m unittest discover -s scripts -p 'test_*.py'` |
   | `infra/` | `tofu fmt -check -recursive infra` |
   | `.github/`, `builders/ansible/` YAML | `yamllint .github/ builders/ansible/` |
   | a schema under `infra/` or `docs/proxmox/config/` | its generator in `CONTRIBUTING.md`, then `bash scripts/check-schema-drift.sh` |
   | a shell script | `bash -n <file>` and `shellcheck -S warning <file>` |

4. Commit with a conventional prefix and the reason: `feat(ingress): ...`,
   `fix(hermes): ...`, `docs: ...`, `ci: ...`.
5. Push and open the pull request. The body has: **What** (and why),
   **Surfaces** touched and skipped (from `surfaces`), **To deploy** (the
   runs in order, from `run-workflow`), **Proof after deploy**.
6. Wait for `90 - Scripts`, `97 - Ansible CI` and `98 - OpenTofu CI`. A
   failure in a step you did not touch: read its log before re-running.
7. Squash-merge when the user says to. Then `run-workflow`.

## Guardrails

- The repository is public. Real addresses, the tailnet name and tokens stay
  out: write `<zone>`, `<tailnet>`, `192.168.1.x`, and take values from
  variables. A new secret goes through `secret`.
- A merge that touches `roles/observability-*` or `infra/tailscale/policy.hujson`
  deploys by itself. Say so in the body.
- Session notes and hand-offs are never committed.
