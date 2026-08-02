---
tags: [gitops, github, packer, proxmox, setup]
status: draft
audience: operator
---

# Manual GitHub UI setup for Packer

Add these values in the repository at **Settings → Secrets and variables →
Actions**. Do not commit them.

## Variables

| Name | Required | Value |
|---|---:|---|
| `PROXMOX_HOST` | Yes | Current Proxmox host's Tailscale MagicDNS name or Tailscale IP. It is both the API host and SSH bastion. |
| `PROXMOX_LAN_IP` | Yes for Debian 13 | PVE's LAN IP, used by the temporary PVE-local preseed server; do not use the Tailscale/API host here. |
| `PROXMOX_PORT` | No | API HTTPS port. Omit it to use `8006`; set only for a non-standard port. |
| `PROXMOX_NODE_NAME` | Yes | Node name shown in the Proxmox UI. |
| `PROXMOX_INSECURE_TLS` | No | `true` for the usual self-signed certificate. |
| `SSH_PUBLIC_KEYS` | Yes | Public keys for the temporary build VM, comma-separated. |

Current Packer defaults are API port `8006`, bridge `vmbr0`, and VM disk
storage `local-lvm`. Cloud-init storage uses the same storage unless overridden.
Do not add `PACKER_ISO_URL` or `PACKER_ISO_CHECKSUM`: the selected implemented
entry in `infra/packer/template-catalog.yaml` owns the ISO URL and checksum.

## Secrets

| Name | Required | Value |
|---|---:|---|
| `TAILSCALE_OAUTH_CLIENT_ID` | Yes | Tailscale OAuth client ID for the ephemeral CI runner. |
| `TAILSCALE_OAUTH_SECRET` | Yes | Matching Tailscale OAuth client secret. |
| `PROXMOX_API_TOKEN` | Yes | Full token: `USER@REALM!TOKENID=TOKEN_SECRET`. |
| `PACKER_SSH_PASSWORD` | Yes | Generated temporary build-VM password, not the PVE password or SSH key. |
| `PVE_SSH_PRIVATE_KEY` | Yes | Private key for SSH from the runner to `PROXMOX_HOST`. |

## PVE SSH bastion key setup

The current workflow uses the `root` PVE account. The public key must be in
that account's `authorized_keys`; the matching private key must work locally
and be pasted into GitHub.

1. Generate an Ed25519 pair in Bitwarden or locally. For a local key, for
   example, run `ssh-keygen -t ed25519 -f ~/.ssh/pve_ci_key`.
2. For the optional Bitwarden path, create the local files and paste the
   exported values into them:

   ```bash
   touch ~/.ssh/autolab-packer-pve-bitwarden
   touch ~/.ssh/autolab-packer-pve-bitwarden.pub
   ```

   Paste the exported Bitwarden **private** key into
   `~/.ssh/autolab-packer-pve-bitwarden` and its **public** key into the
   `.pub` file. Do not use `sudo` when editing a user-owned `~/.ssh` key file.
   A Bitwarden key does not automatically make macOS `ssh` use it.
3. Add the **public** key (including `ssh-ed25519`) to the intended PVE
   account's `~/.ssh/authorized_keys` on the current Proxmox host. On PVE, the
   command to append it is:

   ```bash
   printf '%s\n' 'ssh-ed25519 AAAA... comment' >> ~/.ssh/authorized_keys
   ```

   Run that as the intended account (the current workflow uses `root`), and
   ensure the `.ssh` directory and `authorized_keys` belong to that account.
4. Check permissions:

   ```bash
   chmod 700 ~/.ssh
   chmod 600 ~/.ssh/autolab-packer-pve-bitwarden
   chmod 644 ~/.ssh/autolab-packer-pve-bitwarden.pub
   ```

   The private key must be owned by your user and not group/world-writable.
   Check the PVE account's `.ssh` directory and `authorized_keys` permissions
   too.
5. Test from your laptop. Replace the placeholder with the current host name
   or IP; the docs intentionally use a placeholder instead of a personal IP:

   ```bash
   ssh -i ~/.ssh/autolab-packer-pve-bitwarden root@<proxmox-host-or-ip>
   ```

   For detailed diagnosis, add verbose output and force this identity:

   ```bash
   ssh -vvv -o IdentitiesOnly=yes -i ~/.ssh/autolab-packer-pve-bitwarden root@<proxmox-host-or-ip>
   ```

   Confirm verbose output shows the matching key being offered. Also check the
   host, account, Tailscale reachability, public-key placement, and paths.
6. Paste the complete private-key file, including `BEGIN` and `END` lines, into
   the `PVE_SSH_PRIVATE_KEY` GitHub secret. Do not paste the public key there.

`PVE_SSH_PRIVATE_KEY` authenticates the CI runner to PVE; `SSH_PUBLIC_KEYS` is
injected into the temporary build VM. They are separate keys/uses.

## Run it

Open **Actions → 02 - Packer Build → Run workflow**, select `debian-13` or
`ubuntu-26.04`, and start the workflow. It joins Tailscale, connects to the
current host, downloads the catalog-owned ISO into `local`, and uses `vmbr0`
and `local-lvm` defaults.

Normal machine lifecycle changes are not local `tofu apply` or `tofu destroy`;
use the protected GitHub Actions flow.
