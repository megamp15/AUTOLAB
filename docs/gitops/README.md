---
tags: [gitops, infrastructure-as-code, opentofu, proxmox, beginner]
status: draft
audience: beginner
---

# GitOps phase 2 - VM and LXC foundation

This track starts after the manual Proxmox bootstrap works:

1. Proxmox is installed.
2. Networking works.
3. The host is updated.
4. The host has joined Tailscale.

Phase 2A does one thing on purpose: create Proxmox VMs and LXCs from git, safely.

## Phase map

| Phase | Goal | Tools |
|------|------|-------|
| 2A | Create VMs and LXCs from git | OpenTofu, GitHub Actions, Tailscale runner |
| 2B | Build reusable VM templates | Packer |
| 2C | Harden and configure running servers | Ansible |
| 2D | Deploy workloads and clusters | Docker Compose, Docker Swarm, Talos, Kubernetes |

## What phase 2A includes

- OpenTofu modules for VM and LXC resources.
- Terramate for stack management, code generation, and change detection.
- Packer config for building VM templates from ISOs.
- GitHub Actions workflows for validate, plan, apply, and Packer builds.
- An ephemeral GitHub-hosted runner that joins Tailscale for each job.
- A Cloudflare R2 state backend for OpenTofu.
- GitHub Environments setup (`autolab-plan`, `autolab-apply`) with secrets.
- A security baseline for every created server.
- Documentation for Proxmox API tokens, Tailscale SSH, caching, artifacts, and state.

## What phase 2A does not include yet

- Ansible hardening roles.
- Docker Compose or Docker Swarm deployment.
- Talos or Kubernetes cluster creation.
- Public internet exposure.

## Recommended reading order

1. [01 - Tailscale SSH](./01-tailscale-ssh.md)
2. [02 - Secure GitHub runner](./02-secure-runner.md)
3. [03 - Proxmox API token](./03-proxmox-api-token.md)
4. [04 - OpenTofu VM/LXC provisioning](./04-opentofu-vm-lxc.md)
5. [05 - R2 state backend](./05-r2-state-backend.md)
6. [06 - GitHub Environments](./06-github-environments.md)
7. [GitHub Secrets & Variables Reference](./github-secrets-variables-reference.md)
8. [Server hardening baseline](./server-hardening-baseline.md)
9. [Security sources](./security-sources.md)

## Setup checklist

Every manual step to go from "Proxmox is on Tailscale" to "GitOps is fully operational": **[setup-checklist.md](./setup-checklist.md)**
