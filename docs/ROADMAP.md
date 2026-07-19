---
tags: [meta, roadmap, infrastructure-as-code]
status: draft
audience: maintainer
---

# Autolab roadmap

This repo is meant to **grow** from a documented single node into a reusable homelab scaffold. Proxmox is the first provider track; the later server baseline should also apply to reachable VPS hosts. Status labels match doc frontmatter.

## Now (alpha — usable on real hardware)

| Item | Tags |
|------|------|
| Proxmox bare-metal install guide | `proxmox`, `beginner` |
| Network wizard + setup scripts (USB Ethernet + Wi‑Fi failover) | `networking`, `bash`, `stable` |
| APT maintenance + optional Tailscale | `proxmox`, `operator` |
| Host-only config (`/etc/default/proxmox-network.env`) | `security`, `portable` |
| GitOps phase 2A scaffold | `gitops`, `opentofu`, `proxmox`, `terramate` | OpenTofu modules, CI validate/plan/apply workflows, R2 backend — [setup checklist](gitops/setup-checklist.md) |
| Packer phase 2B scaffold | `packer`, `templates` | `debian-13` template in `infra/packer/templates/` + Packer Build workflow |

Machine inventory (`machines` in `terraform.tfvars`) is **local-only today** — CI injects connection settings but not which VMs/LXCs to create.

## Next (planned)

| Item | Tags | Notes |
|------|------|--------|
| CI-injected or committed machine inventory | `gitops`, `opentofu` | So GitHub Apply can provision without a local `terraform.tfvars` |
| Template experiment matrix | `packer`, `templates`, `talos`, `kubernetes` | Disposable OS and cluster experiments — [template matrix](gitops/template-lab-matrix.md) |
| Builder phase 2C | `ansible`, `security`, `linux` | Enforce the provider-neutral server baseline — scaffold in `builders/ansible/` |
| VPS provider track | `vps`, `opentofu`, `providers` | Future cloud-provider stacks replace Proxmox/Packer provisioning while reusing the builder baseline |
| Second node / “real homelab” profile | `homelab` | Fork-friendly; keep this repo as the **learning** path |
| VM / service tutorials | `learning`, `self-hosted` | Optional guides that consume a working PVE node |

## Layer model

Autolab separates the work by when it can run and what it depends on:

| Layer | Proxmox path | VPS path |
|-------|--------------|----------|
| Bootstrap | Manual Proxmox install, host networking, Tailscale | Provider account, SSH key, API token |
| Provision | Packer template + OpenTofu Proxmox VM/LXC resources | OpenTofu cloud-provider server resources |
| Configure | Ansible builder roles over SSH | Same Ansible builder roles over SSH |
| Serve | Homelab services, tutorials, experiments | Project-specific services |

The VPS path does not need Packer because the provider already returns a booted server image. The shared value is the post-provisioning baseline: users, SSH policy, firewall, updates, Tailscale, deploy user, and runtime roles.

### GitOps vs GitHub Actions (terms)

| | **GitHub Actions** | **GitOps** |
|--|-------------------|------------|
| **What it is** | Automation that runs when git events happen (push, PR, schedule) | Practice: **declarative config in git** is the source of truth; a controller **continuously or repeatedly applies** it until the system matches |
| **Typical tools** | Actions workflows, `make test`, deploy scripts | Kubernetes: Argo CD, Flux; bare metal: Ansible + git, sometimes custom agents |
| **Autolab today** | Scripts workflow (`bash -n`, schema drift, Bats); OpenTofu CI (validate); manual dispatch for plan, apply, and Packer build | Bootstrap: copy `docs/proxmox`, run wizard on host. GitOps: OpenTofu stacks in git; machine inventory in local `terraform.tfvars` |
| **Autolab direction** | Actions for **lint/test/validate** and dispatch workflows against a Tailscale-reachable host | Declarative infra in git; apply reconciles Proxmox when `machines` is defined — grow toward full GitOps reconciliation |

Actions can be **part of** GitOps (e.g. validate PRs before merge), but saying “we use Actions” ≠ “we do GitOps” until something reliably applies what’s in git to the machines.

### Bootstrap vs GitOps (why network is manual-first)

You **cannot** GitOps your way onto a host that has no working uplink yet. Something has to happen **out of band** first:

| Layer | How it usually runs | Autolab today |
|-------|---------------------|---------------|
| **Bootstrap** | ISO install, local console, or SSH over whatever link works (installer Wi‑Fi/Ethernet); copy scripts via USB or `scp`; wizard writes `/etc/default/proxmox-network.env` | **This repo** — docs + bash, aimed at noobs |
| **Steady state** | Host reaches git/Actions/OpenTofu; desired state in git; reconcile VMs, LXCs, storage, backups, and server hardening | **Alpha scaffold** — CI plan/apply works; VM inventory is local `terraform.tfvars` today; Ansible hardening is phase 2C |

So **host networking is not “no GitOps ever”** — it is **not GitOps until the node can reach the internet** (or at least your laptop on LAN). After failover and SSH work, GitOps applies to **what runs on Proxmox**, not to the first cable/Wi‑Fi bring-up.

Ways people still reduce bootstrap pain without full GitOps:

- Version **scripts and templates** in git (you already do); apply by copy/`scp` once.
- Optional later: USB stick with `docs/proxmox`, or Actions that only **lint** scripts (no target host required).

**Autolab scope:** nail bootstrap + document it clearly; treat VM/LXC provisioning and the reusable Linux builder baseline as the next learning tracks.

## Non-goals (for this repo)

- Storing Wi‑Fi passwords or site-specific IPs in git
- Replacing Proxmox’s own upgrade documentation for major migrations
- One-click support for every possible NIC naming scheme without the wizard
- Treating VPS providers as the main path before the Proxmox learning path is usable
- Bundling a fixed app catalog before the reusable server baseline exists

## Compared to larger homelab repos

Repos such as [khuedoan/homelab](https://github.com/khuedoan/homelab) are excellent **multi-node Kubernetes + GitOps** references. Autolab is intentionally narrower today: **one Proxmox host at a time** (same scripts on a second laptop/server with its own env file), bash-first, tutorial-heavy, and **fully custom** to your hardware. Converge on IaC/CI over time without shipping a fixed app catalog.

## How to contribute (solo or future collaborators)

1. Add or update a guide under `docs/` with frontmatter `tags`, `status`, `audience`.
2. Keep scripts idempotent and paths explicit (`/etc/default/…`, `/root/proxmox-setup/…`).
3. Note breaking changes in the guide that owns that area (usually `00-fresh-install-network.md` or `scripts/README.md`).
4. Before merging, run or document the applicable [production-readiness gates](production-readiness.md). CI runs schema drift, Bats, `tofu validate`, and Packer validate today; plan/apply against a real host are manual dispatch workflows.
