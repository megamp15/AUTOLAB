---
name: autolab
description: "Explain and help operate the owner's homelab from the AUTOLAB repository checkout."
version: 1.0.0
author: AUTOLAB
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Homelab, AUTOLAB, Proxmox, Ansible, OpenTofu]
    related_skills: []
---

# AUTOLAB

## When to use

Questions about the homelab: what runs where, how a service is deployed,
what a workflow does, why something is designed the way it is, what to run
to change it. Also when drafting a change for the owner to review.

## Where to look

A read-only checkout of the public repository is at `/workspace/autolab`,
refreshed by Ansible. Start with:

- `CONTEXT.md`: the vocabulary.
- `docs/gitops/README.md` and the pages under `docs/gitops/`: one page per
  concern (services, observability, ingress, backups, cosmos, hermes ...).
- `infra/stacks/lab/machines.auto.tfvars`: the machines and what each runs.
- `builders/ansible/roles/`: how each thing is configured.
- `.github/workflows/`: the numbered workflows the owner dispatches.

Prefer the docs over guessing from code; the docs say why.

## What you may do

- Read and explain anything in the checkout.
- Read Grafana, Prometheus and Loki through the Grafana MCP when it is
  configured; alert state and metrics are read-only.
- Tell the owner the exact workflow, inputs and order to run, and what to
  check first (`confirm: check` before `apply`, always).
- Draft a change as a patch or a branch for the owner to review.

## What you may not do

- The checkout is read-only; you cannot and must not change the lab from
  here. No `git push`, no workflow dispatch, no SSH to other hosts.
- Never read, print or ask for secrets, tokens or `.env` files.
- A change to `main` ships to production; the owner merges, never you.
