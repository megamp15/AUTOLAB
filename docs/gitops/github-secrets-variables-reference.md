---
tags: [gitops, github, secrets, variables, reference]
status: draft
audience: operator
---

# GitHub Secrets & Variables Reference

Single source of truth for every secret and variable the Autolab GitOps workflows need.

## Repository variables (non-sensitive)

Set at **Settings → Secrets and variables → Actions → Variables**.

| Variable | Example | Where to get it |
|----------|---------|-----------------|
| `PROXMOX_HOST` | `<proxmox-host>` | Short Tailscale MagicDNS name. Run `hostname` on Proxmox host, or Tailscale admin → Machines. Full FQDN also works (e.g. `<proxmox-tailnet-host>`). |
| `PROXMOX_NODE_NAME` | `pve` | Proxmox node name in web UI left sidebar. Often `pve`. Run `hostname` on host to confirm — usually matches, but check UI if unsure. |
| `PROXMOX_INSECURE_TLS` | `true` | Optional. Keep `true` for Proxmox's default self-signed certificate. |
| `SSH_PUBLIC_KEYS` | `ssh-ed25519 AAAA... user@laptop` | Your **laptop's** public SSH key. Run `cat ~/.ssh/id_ed25519.pub`. Create on laptop with `ssh-keygen -t ed25519 -C "autolab@your-laptop"` if needed. |

## Secrets (sensitive)

Set at **Settings → Secrets and variables → Actions → Secrets**.

| Secret | Example | Where to get it |
|--------|---------|-----------------|
| `TAILSCALE_OAUTH_CLIENT_ID` | `tskey-client-abc123` | Tailscale admin console → Settings → OAuth clients → Create client → Custom scopes → Keys: Auth Keys Write → Tag: `tag:ci-runner` |
| `TAILSCALE_OAUTH_SECRET` | `tskey-client-secret-xyz` | Same OAuth client creation screen. **Shown only once** — copy immediately. |
| `PROXMOX_ENDPOINT` | `https://<proxmox-tailnet-host>:8006` | Proxmox API URL over Tailscale. Format: `https://<PROXMOX_HOST>:8006`. Tailscale IP also works: `https://<tailscale-ip>:8006`. Prefer MagicDNS hostname. |
| `PROXMOX_API_TOKEN` | `gitops@pve!opentofu=SECRET` | Proxmox web UI → Datacenter → Permissions → API Tokens → Add. Create user `gitops@pve`, token ID `opentofu`. Grant: `PVEVMAdmin` on node, `Datastore.AllocateSpace` + `Datastore.AllocateTemplate` on storage, VM.* permissions. **Full token string shown once.** |
| `R2_ACCOUNT_ID` | `a1b2c3d4e5f6...` | Cloudflare dashboard → R2 → URL shows `https://dash.cloudflare.com/<ACCOUNT_ID>/r2/...` |
| `R2_ACCESS_KEY_ID` | `abc123...` | Cloudflare R2 → Manage R2 API Tokens → Create API token → Object Read & Write. **Shown once.** |
| `R2_SECRET_ACCESS_KEY` | `xyz789...` | Same as above. **Shown once.** |
| `AUTOLAB_ADMIN_SSH_PUBLIC_KEY` | `ssh-ed25519 AAAA... user@laptop` | Same content as `SSH_PUBLIC_KEYS` — laptop public key. Stored as secret so workflows have one consistent source. |
| `TAILSCALE_VM_AUTHKEY` | `tskey-auth-abc123...` | Optional for first plan smoke test. Later: Tailscale → Auth keys → Ephemeral + Reusable, tag `tag:autolab-vm`. |

## Packer-only GitHub values

Only needed when running `.github/workflows/packer-build.yml`.

| Name | Type | Example | Where to get it |
|------|------|---------|-----------------|
| `PACKER_SSH_PASSWORD` | Secret | `packer` | Temporary password used during automated install. Pick a generated value. |
| `PROXMOX_STORAGE_POOL` | Variable | `local-lvm` | Proxmox storage for template disks. |
| `PROXMOX_CLOUD_INIT_STORAGE_POOL` | Variable | `local-lvm` | Optional. Leave unset to use `PROXMOX_STORAGE_POOL`. |
| `PROXMOX_NETWORK_BRIDGE` | Variable | `vmbr0` | Proxmox bridge for the build VM. |
| `PACKER_ISO_FILE` | Variable | `local:iso/debian-12.8.0-amd64-netinst.iso` | ISO path after uploading the Debian installer to Proxmox. |
| `PACKER_ISO_CHECKSUM` | Variable | `sha256:...` | Optional. Leave empty to skip checksum verification. |
| `PVE_SSH_PRIVATE_KEY` | Secret | `-----BEGIN OPENSSH PRIVATE KEY-----...` | Optional. Only used if the Packer build needs SSH access to the Proxmox host. |

## GitHub Environments (must exist)

Create at **Settings → Environments**.

| Environment | Workflow | Protection |
|-------------|----------|------------|
| `autolab-plan` | `opentofu-plan.yml` | No required reviewers (Free/Team). Enterprise: optional. |
| `autolab-apply` | `opentofu-apply.yml` | Free/Team: manual `confirm: apply` input is the gate. Enterprise: can add required reviewers. |

## Quick checklist

- [ ] `PROXMOX_HOST` = `<proxmox-host>` (or `<proxmox-tailnet-host>`)
- [ ] `PROXMOX_NODE_NAME` = `pve` (confirm in Proxmox UI)
- [ ] `PROXMOX_INSECURE_TLS` = `true` unless you installed a trusted Proxmox certificate
- [ ] `SSH_PUBLIC_KEYS` = laptop `~/.ssh/id_ed25519.pub`
- [ ] `TAILSCALE_OAUTH_CLIENT_ID` = Tailscale OAuth client ID
- [ ] `TAILSCALE_OAUTH_SECRET` = Tailscale OAuth client secret
- [ ] `PROXMOX_ENDPOINT` = `https://<proxmox-tailnet-host>:8006`
- [ ] `PROXMOX_API_TOKEN` = full Proxmox API token string
- [ ] `R2_ACCOUNT_ID` = Cloudflare account ID
- [ ] `R2_ACCESS_KEY_ID` = R2 access key ID
- [ ] `R2_SECRET_ACCESS_KEY` = R2 secret access key
- [ ] `AUTOLAB_ADMIN_SSH_PUBLIC_KEY` = same laptop public key
- [ ] `TAILSCALE_VM_AUTHKEY` = optional now
- [ ] Environment `autolab-plan` exists
- [ ] Environment `autolab-apply` exists

## Notes

- **Proxmox node name** — not Tailscale hostname. Cluster node label in Proxmox sidebar. Run `hostname` on host; default often `pve`.
- **SSH key** — create on **laptop**, not Proxmox. Public key injected into VMs/LXCs via cloud-init.
- **Tailscale IP `<tailscale-ip>`** — stable on tailnet; MagicDNS preferred for `PROXMOX_ENDPOINT`.
- **Proxmox API token** — never root password. Dedicated `gitops@pve` user + token.
- **Repo-level secrets/vars** work for personal-lab smoke test. Copy into environment secrets before real apply runs.

## Related docs

- [Setup checklist](./setup-checklist.md) — ordered steps
- [03 - Proxmox API token](./03-proxmox-api-token.md)
- [06 - GitHub Environments](./06-github-environments.md)
