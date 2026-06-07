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
| `infra/connection-schema.yaml` | `infra/modules/proxmox-connection/variables.tf`, `infra/packer/connection-vars.pkr.hcl`, `infra/_base/connection-variables.tm.hcl`, `.github/actions/configure-proxmox-connection/action.yml` | `scripts/generate-connection-adapters.sh` |
| `docs/proxmox/config/network-env-schema.yaml` | `docs/proxmox/config/network.env.example`, `docs/proxmox/scripts/lib/network-env-schema.sh` | `scripts/generate-network-env-adapters.sh` |
| `infra/r2-config.yaml` | `infra/terramate.tm.hcl`, `scripts/lib/r2-defaults.sh` | `scripts/generate-r2-config.sh` |

The drift check runs `scripts/check-schema-drift.sh` (or an inline CI step that re-runs the generator and `git diff --exit-code`).

### 2 — Generated adapter semantic validation

Beyond literal drift, each generated adapter is validated for **semantic correctness**:

- **OpenTofu adapters** — verified via `tofu validate` in the consuming module or stack.
- **Packer adapters** — verified via `packer validate` against a template that includes the connection variables.
- **CI adapter** (`action.yml`) — verified via `yamllint` and a dry-run that checks every `ci_env` name resolves in the workflow environment.
- **Network-env bash adapter** — verified via `bash -n` and a unit test that sources it and checks expected variable names.

### 3 — Bats tests

Bash automated test suite (`tests/*.bats`) must pass on the runner. Tests cover:

- **Pure-function libraries** under `docs/proxmox/scripts/lib/` — sourced and exercised with known inputs.
- **Generator scripts** — run in a temp directory and the output compared against expected content.
- **Network-env schema helpers** — key iteration, default injection, validation matchers.

Run: `bats tests/`

### 4 — Bootstrap dry-run

A CI-only workflow that simulates the **bootstrap phase** without touching a real Proxmox host:

1. Copies `docs/proxmox/scripts/` into a clean container or VM.
2. Creates a synthetic `/etc/default/proxmox-network.env` from the `.example` file.
3. Runs `configure-proxmox-network-env.sh` and `setup-proxmox-network.sh --dry-run`.
4. Asserts no errors and that expected config files (`interfaces`, `wpa_supplicant.conf`) would be written.

This gate ensures bootstrap scripts do not regress when schema or code changes.

### 5 — OpenTofu validate / plan

For changes that affect **GitOps** (phase 2A):

1. `tofu validate` passes for every changed stack and module.
2. `tofu plan` succeeds (no plan-time connection required — `proxmox-connection` is a validation-only module).
3. Plan output is uploaded as an artifact for review.

Run from the stack directory after `tofu init` with connection variables sourced from CI secrets.

### 6 — Packer validate / build decision

For changes that affect **Packer templates** (phase 2B):

1. `packer validate` passes for every template in `infra/packer/`.
2. CI decides **whether to build** based on the change set:
   - Schema-only or metadata changes → validate only.
   - Template variable or connection adapter changes → validate only.
   - Base image, provisioning script, or boot command changes → full `packer build` against a real Proxmox host.

### 7 — One real Proxmox host smoke test

Before a tagged release or a major refactor lands, run a **live smoke test** against a single reachable Proxmox host (the `lab` stack or a dedicated test node):

1. Bootstrap the network env from scratch using current scripts.
2. Run `tofu apply` for a minimal machine (one VM or LXC) and verify it reaches `running` state.
3. Run `tofu destroy` to clean up.
4. Assert the host returns to the state before the test (connection config is preserved).

This gate is manual for alpha; it becomes automated in CI once an ephemeral Tailscale connection to a test host is available.

## When gates apply

| Gate | CI (PR) | CI (main) | Pre-release | Local dev |
|------|---------|-----------|-------------|-----------|
| Schema drift | Required | Required | Required | Recommended |
| Adapter semantic validation | Required | Required | Required | Recommended |
| Bats tests | Required | Required | Required | Recommended |
| Bootstrap dry-run | Required | Required | Required | Recommended |
| OpenTofu validate/plan | Required | Required | Required | Recommended |
| Packer validate/build | On change | On change | Required | Recommended |
| Real host smoke test | Manual | Manual | Required | Optional |

## Checklist template

Use this for release PRs or phase transitions:

```markdown
**Production-readiness checklist**

- [ ] Schema drift check passes (`scripts/check-schema-drift.sh`)
- [ ] Adapter semantic validation passes (`tofu validate`, `packer validate`, `bash -n`)
- [ ] Bats tests pass (`bats tests/`)
- [ ] Bootstrap dry-run passes (CI container)
- [ ] OpenTofu validate/plan passes for changed stacks
- [ ] Packer validate passes for changed templates; build decision documented
- [ ] Real Proxmox host smoke test completed (link to run log)
```
