---
tags: [gitops, packer, proxmox, templates, talos, kubernetes]
status: draft
audience: operator
---

# Template experiment matrix

Autolab keeps two implemented Linux template paths (`debian-13` and
`ubuntu-26.04`), plus a menu of **disposable experiments** to learn the
framework. Experiments are meant to be destroyed when done — not permanently
supported OS lines.

**Source of truth for buildability:** `infra/packer/template-catalog.yaml`
- `templates:` with `status: implemented` → runnable from CI and local Packer
- `experiments:` → documented only until promoted

## Runnable today

| Target | Phase | What works | What does not |
|--------|-------|------------|---------------|
| `debian-13` | 2B Packer + 2A OpenTofu | Packer Build workflow; template VM ID `9000`; clone via local `terraform.tfvars` + `tofu apply` | Ansible hardening; CI-injected `machines` |
| `ubuntu-26.04` | 2B Packer + 2A OpenTofu | Buildable candidate; Subiquity autoinstall; distinct template VM ID `9001`; workflow selection is wired | First successful Packer build and `template-validation`; Ansible hardening; CI-injected `machines` |

**Smoke test path:**

1. Packer Build → select `debian-13` (`9000`) or `ubuntu-26.04` (`9001`)
2. Local `terraform.tfvars` with one `builder_target` VM → `tofu apply`
3. SSH as `autolab` with your injected key
4. Destroy the VM; keep the template

Ubuntu 26.04 is a buildable candidate, not a claim of real-hardware
validation. Treat it as promotable only after one successful Packer build and
one successful `template-validation` run.

## Documented experiments (not runnable yet)

These rows are **design notes only**. They do not appear in the Packer Build
workflow dropdown and `scripts/resolve-packer-template.sh` rejects them.

| Target | `provisioning_class` | Blocker today | First step when promoted |
|--------|---------------------|---------------|--------------------------|
| `ubuntu-24.04` | `builder_target` | No Packer template dir; Subiquity autoinstall not written | Add `infra/packer/templates/ubuntu-24.04/` + catalog `status: implemented` |
| `rocky-9` | `builder_target` | No kickstart template | Same pattern as Ubuntu |
| `alpine` | `builder_target` | No minimal template | Same pattern |
| `talos` | `cluster_os` | OpenTofu blocks `cluster_os` at plan time; no Talos module | OpenTofu VM resources + `talosctl` workflow (may skip Packer) |

## Phase ownership

| Layer | Owns | Status |
|-------|------|--------|
| **2B Packer** | ISO → Proxmox template | `debian-13` and `ubuntu-26.04` |
| **2A OpenTofu** | Clone template → running VM/LXC | Works for `builder_target` with local tfvars |
| **2A cloud-init** | Admin user, SSH keys, optional Tailscale join | Wired for builder-target VMs |
| **2C Ansible** | OS hardening after SSH works | Scaffold only (`TODO` debug tasks) |
| **`cluster_os`** | Talos-style machines | Recognized in schema; plan fails until implemented |

## Talos virtual cluster (experiment design)

Talos is the main **framework power** experiment: special-purpose VMs configured
via `talosctl`, not SSH + Ansible.

Recommended disposable cluster on the XPS node:

| Node | Count | CPU | Memory | Disk |
|------|-------|-----|--------|------|
| Control plane | 1 | 2–4 cores | 4–8 GB | 32+ GB |
| Worker | 2 | 2–4 cores | 4–8 GB | 32+ GB |

**Not implemented.** Intended shape when wired:

1. OpenTofu creates Proxmox VMs with `provisioning_class = "cluster_os"`.
2. Talos Image Factory assets + `talosctl gen config` / `apply-config` / `bootstrap`.
3. Verify with `talosctl health` and `kubectl get nodes`.
4. Destroy all VMs and generated configs when done.

Talos may never need Packer — Image Factory + OpenTofu is the likely first path.

## Packer layout (implemented pattern)

Each **implemented** template gets its own directory:

```text
infra/packer/
  template-catalog.yaml
  templates/
    debian-13/          # implemented
    ubuntu-26.04/       # implemented
```

Installer automation per OS (when built):

| Template | Installer |
|----------|-----------|
| Debian | preseed (`debian-13-preseed.cfg.tpl`) |
| Ubuntu | Subiquity autoinstall |
| Rocky/Alma | kickstart |
| Alpine | answer file |

## Experiment lifecycle

Tag disposable machines in `terraform.tfvars`:

```hcl
tags = ["experiment:debian-template-smoke"]
```

Destroy via OpenTofu when finished. Promote to keeper only if you intentionally
keep the template or VM.

## Acceptance checks by target

| Target | Smoke test (when runnable) | Destroy check |
|--------|---------------------------|---------------|
| `debian-13` | Packer build + OpenTofu clone + SSH as `autolab` | Destroy cloned VM; keep template `9000` |
| `ubuntu-26.04` | Packer build + OpenTofu clone + SSH as `autolab` | Destroy cloned VM; keep template `9001` |
| `ubuntu-24.04` | Packer build + clone + SSH | Destroy unless promoted to implemented |
| `rocky-9` / `alpine` | Packer build + Ansible fact gather (after 2C) | Destroy test host |
| `talos` | `talosctl health`; `kubectl get nodes` Ready | Destroy all Talos VMs + local configs |

## Related docs

- [Packer README](../../infra/packer/README.md)
- [GitHub Secrets & Variables Reference](./github-secrets-variables-reference.md)
- [Server hardening baseline](./server-hardening-baseline.md) — 2A cloud-init vs 2C Ansible
