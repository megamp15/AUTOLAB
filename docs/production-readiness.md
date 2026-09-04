---
tags: [meta, production-readiness, quality]
status: draft
audience: maintainer
---

# Production-readiness gates

This document defines the **stop criteria** a change must pass before Autolab is considered production-ready for the phase it targets. Gates apply during CI or local pre-merge workflows; a failing gate blocks the merge.

## Gates

### 1 — Schema drift checks

Any change to a schema YAML must be paired with a regeneration of its adapters, and CI must detect that the committed adapters are **in sync** with their source schema.

| Schema | Adapter(s) | Generator |
|--------|------------|-----------|
| `infra/connection-schema.yaml` | `infra/modules/proxmox-connection/variables.tf`, `infra/packer/templates/*/connection-vars.pkr.hcl`, `infra/_base/connection-variables.tm.hcl`, `.github/actions/configure-proxmox-connection/action.yml` | `scripts/generate-connection-adapters.sh` |
| `docs/proxmox/config/network-env-schema.yaml` | `docs/proxmox/config/network.env.example`, `docs/proxmox/scripts/lib/network-env-schema.sh` | `scripts/generate-network-env-adapters.sh` |
| `infra/r2-config.yaml` | `infra/terramate.tm.hcl`, `scripts/lib/r2-defaults.sh` | `scripts/generate-r2-config.sh` |
| `infra/packer/template-schema.yaml` | `.github/actions/configure-packer-template/action.yml` | `scripts/generate-packer-template-adapters.sh` |

The drift check runs `scripts/check-schema-drift.sh` (or an inline CI step that re-runs the generator and `git diff --exit-code`).

### 2 — Generated adapter semantic validation

Beyond literal drift, each generated adapter is validated for **semantic correctness**:

- **OpenTofu adapters** — verified via `tofu validate` in the consuming module or stack.
- **Packer adapters** — verified via `packer validate` against a template that includes the connection variables.
- **CI adapter** (`action.yml`) — verified via `yamllint` in CI (`.yamllint` at the repo root); the Bats suite checks that every `ci_env` name resolves.
- **Network-env bash adapter** — verified via `bash -n` and a unit test that sources it and checks expected variable names.

### 3 — Bats tests

Bash automated test suite under `docs/proxmox/scripts/tests/*.bats` must pass. Tests cover:

- **Pure-function libraries** under `docs/proxmox/scripts/lib/`
- **Generator scripts** — run in a temp directory; output compared to expected content
- **Schema drift gate** — `schema-drift-gate.bats`
- **Packer template catalog** — `packer-template-catalog.bats`

Run: `bats docs/proxmox/scripts/tests/`

### 4 — Bootstrap dry-run

**Runs in CI** via `scripts/bootstrap-dry-run.sh` (also runnable locally with Docker).

It simulates the **bootstrap phase** without touching a real Proxmox host:

1. Copies `docs/proxmox/` into a clean `debian:trixie-slim` container at `/root/proxmox-setup/`.
2. Creates a synthetic `/etc/default/proxmox-network.env` from the `.example` file plus placeholder values.
3. Runs `setup-proxmox-network.sh --config <env> --dry-run --skip-apt`.
4. Asserts the run exits 0, renders `interfaces` and `wpa_supplicant.conf`, and writes nothing under `/etc` or `/usr/local/bin`.

The interactive wizard (`configure-proxmox-network-env.sh`) reads `/dev/tty` and is not exercised here; its pure logic is covered by the Bats suite.

### 5 — OpenTofu validate / plan

For changes that affect **GitOps** (phase 2A):

1. `tofu validate` passes for every changed stack and module — **runs in CI** (`90_scripts.yml`, `98_opentofu-ci.yml`).
2. `tofu plan` against a real host — **manual dispatch** via `03_opentofu-plan.yml` today.
3. Plan output uploaded as an artifact when using the plan workflow.

Run plan from the stack directory after `tofu init` with connection variables from GitHub secrets and variables.

### 6 — Packer validate / build decision

For changes that affect **Packer templates** (phase 2B):

1. `packer validate` for each catalog-resolved implemented template — **runs in CI** via `scripts/resolve-packer-template.sh`.
2. Full `packer build` — **manual dispatch** via `02_packer-build.yml` against a real Proxmox host.

### 7 — One real Proxmox host smoke test

Before a tagged release or a major refactor lands, run a **live smoke test** against a single reachable Proxmox host (the `lab` stack or a dedicated test node):

1. Bootstrap the network env from scratch using current scripts.
2. Run `tofu apply` for a minimal machine (one VM or LXC) and verify it reaches `running` state.
3. Run `tofu destroy` to clean up.
4. Assert the host returns to the state before the test (connection config is preserved).

This gate is manual for alpha; it becomes automated in CI once an ephemeral Tailscale connection to a test host is available.

## When gates apply

**Implemented in CI today:** `90_scripts.yml` runs `bash -n`, ShellCheck, yamllint,
schema drift, `tofu validate`, Packer validate for every implemented catalog template,
Bats, the Python unit tests under `scripts/`, the Tailscale device cleanup self-check,
and the bootstrap dry-run. `97_ansible-ci.yml` runs playbook syntax-check and
ansible-lint. `98_opentofu-ci.yml` runs `tofu fmt` and `tofu validate`.

**Manual / dispatch today:** `tofu plan`, `tofu apply`, `packer build`, real host
smoke test.

**Target gates** (not automated yet): a real-host smoke test from CI once an
ephemeral test node is available.

| Gate | CI (PR) | CI (main) | Pre-release | Local dev |
|------|---------|-----------|-------------|-----------|
| Schema drift | Yes | Yes | Required | Recommended |
| Bats tests | Yes | Yes | Required | Recommended |
| ShellCheck, yamllint, ansible-lint | Yes | Yes | Required | Recommended |
| OpenTofu validate | Yes | Yes | Required | Recommended |
| Packer validate (implemented templates) | Yes | Yes | Required | Recommended |
| OpenTofu plan (real host) | Manual | Manual | Required | Optional |
| Packer build (real host) | Manual | Manual | Required | Optional |
| Bootstrap dry-run | Yes | Yes | Required | Recommended (Docker) |
| Real host smoke test | Manual | Manual | Required | Optional |

## Checklist template

Use this for release PRs or phase transitions:

```markdown
**Production-readiness checklist**

- [ ] Schema drift check passes (`scripts/check-schema-drift.sh`)
- [ ] Adapter semantic validation passes (`tofu validate`, `packer validate`, `bash -n`)
- [ ] Bats tests pass (`bats docs/proxmox/scripts/tests/`)
- [ ] Bootstrap dry-run passes (`bash scripts/bootstrap-dry-run.sh`)
- [ ] OpenTofu validate/plan passes for changed stacks
- [ ] Packer validate passes for changed templates; build decision documented
- [ ] Real Proxmox host smoke test completed (link to run log)
```
