---
tags: [gitops, infrastructure-as-code, opentofu, proxmox, beginner]
status: draft
audience: beginner
---

# GitOps phase 2 - VM and LXC foundation

The agreed template and machine lifecycle is documented in
[Template lifecycle](./template-lifecycle.md). It introduces the planned
`template-validation`, persistent `integration-test`, and long-lived `lab`
environments without claiming that the future multi-stack architecture exists
today.

This track starts after the manual Proxmox bootstrap works:

1. Proxmox is installed.
2. Networking works.
3. The host is updated.
4. The host has joined Tailscale.

Phase 2A provisions Proxmox VMs and LXCs with OpenTofu. The **stack code** lives in git; the **machine inventory** (`machines` map) lives in local `terraform.tfvars` today — CI does not inject it yet.

## Phase map

| Phase | Goal | Tools |
|------|------|-------|
| 2A | Provision VMs and LXCs with OpenTofu | OpenTofu, GitHub Actions, Tailscale runner, R2 state |
| 2B | Build reusable VM templates | Packer |
| 2C | Harden and configure running servers | Ansible |
| 2D | Deploy workloads and clusters | Docker Compose, Docker Swarm, Talos, Kubernetes |

## What phase 2A includes (shipped scaffold)

- OpenTofu modules for VM and LXC resources (`proxmox-connection`, `machine-normalization`, `proxmox-compute`, `cloud-init`).
- Terramate for stack management, code generation, and change detection.
- GitHub Actions workflows: OpenTofu CI (validate), manual plan, manual apply.
- An ephemeral GitHub-hosted runner that joins Tailscale for each job.
- A Cloudflare R2 state backend for OpenTofu.
- GitHub Environments (`autolab-plan`, `autolab-apply`) with secrets and variables.
- Cloud-init baseline for builder-target VMs (admin user, SSH keys, qemu-guest-agent, optional Tailscale join).
- Documentation for Proxmox API tokens, Tailscale, caching, artifacts, and state.

## What phase 2B includes (shipped scaffold)

- Packer template catalog with implemented `debian-13` and `ubuntu-26.04` templates under `infra/packer/templates/`.
- Packer Build GitHub Actions workflow.

## What is not included yet

- Ansible hardening roles (phase 2C — roles are debug placeholders).
- `cluster_os` provisioning (Talos experiments are documented but blocked at plan time).
- CI-injected `machines` map (VM creation needs local `terraform.tfvars`).
- Docker Compose, Docker Swarm, Talos/Kubernetes cluster deployment.
- Public internet exposure.

## Recommended reading order

1. [01 - Tailscale SSH](./01-tailscale-ssh.md)
2. [02 - Secure GitHub runner](./02-secure-runner.md)
3. [03 - Proxmox API token](./03-proxmox-api-token.md)
4. [04 - OpenTofu VM/LXC provisioning](./04-opentofu-vm-lxc.md)
5. [05 - R2 state backend](./05-r2-state-backend.md)
6. [06 - GitHub Environments](./06-github-environments.md)
7. [GitHub Secrets & Variables Reference](./github-secrets-variables-reference.md)
8. [Template experiment matrix](./template-lab-matrix.md)
9. [Template lifecycle](./template-lifecycle.md)
10. [Server hardening baseline](./server-hardening-baseline.md)
11. [Security sources](./security-sources.md)

## Setup checklist

From "Proxmox is on Tailscale" to working CI pipelines and your first disposable VM:
**[setup-checklist.md](./setup-checklist.md)**
