# Security policy

## Reporting a vulnerability

Please report security issues privately through
[GitHub private vulnerability reporting](https://github.com/megamp15/AUTOLAB/security/advisories/new).
Do not open a public issue.

Include what is affected (a script, a module, a workflow, a role), how to reproduce it, and the impact you believe it has. You should hear back within a week.

## Scope

Autolab is an alpha, single-maintainer homelab project. Only the `main` branch is supported. Areas where a report is especially useful:

- Bootstrap scripts under `docs/proxmox/scripts/` (they run as root and rewrite network config)
- Cloud-init, Tailscale enrollment, and the device cleanup hook
- The Ansible baseline (SSH hardening, firewall, `gitops` user)
- GitHub Actions workflows and composite actions (secret handling, runner tailnet identity, unpinned actions)

## Secrets

The repo is designed to contain no secrets. Wi-Fi credentials, API tokens, auth keys, and private keys live on the host or in GitHub secrets. If you find a committed secret, report it privately as above so it can be rotated before the history is cleaned.

Third-party components (Proxmox, OpenTofu, Packer, Ansible, Tailscale) should be reported to their own projects; see `docs/gitops/security-sources.md` for the advisory feeds Autolab follows.
