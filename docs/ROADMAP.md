---
tags: [meta, roadmap, infrastructure-as-code]
status: draft
audience: maintainer
---

# Autolab roadmap

This repo is meant to **grow** from a documented single node into a reusable homelab scaffold. Proxmox is the first provider track; the later server baseline should also apply to reachable VPS hosts. Status labels match doc frontmatter.

## Now (alpha — usable on real hardware)

| Item | Tags | Notes |
|------|------|-------|
| Proxmox bare-metal install guide | `proxmox`, `beginner` | |
| Network wizard + setup scripts (USB Ethernet + Wi‑Fi failover) | `networking`, `bash`, `stable` | |
| APT maintenance + optional Tailscale | `proxmox`, `operator` | |
| Host-only config (`/etc/default/proxmox-network.env`) | `security`, `portable` | |
| GitOps phase 2A | `gitops`, `opentofu`, `proxmox`, `terramate` | OpenTofu modules, CI validate/plan/apply/destroy workflows, R2 backend — [setup checklist](gitops/setup-checklist.md) |
| Packer phase 2B | `packer`, `templates` | Catalog-driven builds: `debian-13`, `ubuntu-24.04`, `ubuntu-26.04` ([catalog](../infra/packer/template-catalog.yaml)) |
| Builder phase 2C | `ansible`, `security`, `linux` | Debian-family baseline over Tailscale SSH (updates, SSH hardening, firewall, `gitops` user, named operator accounts, login screen), opt-in Docker and NFS/SMB storage, `tailscale-update`; workflow 05 bootstraps as `autolab` then runs as `gitops` |
| Proxmox under Ansible | `ansible`, `proxmox` | Workflow `07 - Proxmox Node` with a static inventory: no-subscription repositories, subscription notice removal. Was the prerequisite for backups, since PBS ships the same enterprise repository |
| Backup phase 3 | `backup`, `pbs`, `3-2-1` | Proxmox Backup Server as packages on a managed VM (`ark`), chunk store on the NAS over NFS, client-side encryption with the key kept off the node, nightly vzdump of every guest, prune / GC / verify jobs. Restore is a workflow (`08 - PBS Restore`) and has been run: a backup booted. A morning ntfy digest reports last night's run and each guest's newest backup age. Still open: Backblaze B2 as a second datastore with a sync job — [backups](gitops/backups.md) |
| Tenancy | `gitops`, `tenant`, `tailscale` | A tenant is a stack with its own GitHub Environment; its VMs enrol on the tenant's tailnet and the Builder reaches them over the hypervisor's private bridge. First tenant `qnta` is live: applied, hardened through the hypervisor, destroyed and re-applied with the device leaving and rejoining the tenant's console; its VMs mount the NAS over SMB and report to the provider's observability stack over the bridge — [tenants](gitops/tenants.md), ADR-0006 |
| Observability phase 2D | `observability`, `grafana`, `prometheus`, `loki` | Alloy on every host; Prometheus, Loki, Grafana and the Proxmox exporter on the machine marked `observability.stack`. Dashboards owned by Git Sync and editable in the UI; datasources, alert rules and delivery provisioned from files. Five alert rules, each fired deliberately and confirmed delivered to a phone — [observability](gitops/observability.md) |

Machine inventory is **committed desired state**: `infra/stacks/lab/machines.auto.tfvars` declares the `lab` VMs and is what the plan, apply, and Builder workflows read. Connection settings still come from GitHub secrets and variables.

## Next (planned)

| Item | Tags | Notes |
|------|------|--------|
| `template-validation` and `integration-test` environments | `gitops`, `packer`, `opentofu`, `integration-test` | Validate ephemeral candidates, then test later server layers on a persistent canary before promoting to `lab` |
| Template experiment matrix | `packer`, `templates`, `talos`, `kubernetes` | Disposable OS and cluster experiments — [template matrix](gitops/template-lab-matrix.md) |
| Builder for LXC targets | `ansible`, `lxc` | LXC Builder targets are deferred until they meet the same reachable-host contract as cloud-init VMs |
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
| **Autolab today** | Scripts workflow (`bash -n`, schema drift, OpenTofu and Packer validate, Bats); OpenTofu CI (validate); manual dispatch for Packer build, plan, apply, destroy, and the Ansible Builder | Bootstrap: copy `docs/proxmox`, run wizard on host. GitOps: OpenTofu stacks and the `lab` machine map in git; apply reconciles Proxmox on dispatch |
| **Autolab direction** | Actions for **lint/test/validate** and dispatch workflows against a Tailscale-reachable host | Declarative infra in git; apply reconciles Proxmox from the committed `machines` map on dispatch — grow toward automatic reconciliation |

Actions can be **part of** GitOps (e.g. validate PRs before merge), but saying “we use Actions” ≠ “we do GitOps” until something reliably applies what’s in git to the machines.

### Bootstrap vs GitOps (why network is manual-first)

You **cannot** GitOps your way onto a host that has no working uplink yet. Something has to happen **out of band** first:

| Layer | How it usually runs | Autolab today |
|-------|---------------------|---------------|
| **Bootstrap** | ISO install, local console, or SSH over whatever link works (installer Wi‑Fi/Ethernet); copy scripts via USB or `scp`; wizard writes `/etc/default/proxmox-network.env` | **This repo** — docs + bash, aimed at noobs |
| **Steady state** | Host reaches git/Actions/OpenTofu; desired state in git; reconcile VMs, LXCs, storage, backups, and server hardening | **Alpha** — CI plan/apply/destroy works against the committed `lab` machine map; the Ansible Builder hardens the resulting VMs and mounts NAS storage over the tailnet; backups are not managed yet |

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
