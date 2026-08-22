---
tags: [gitops, tailscale, ssh, security]
status: draft
audience: beginner
---

# Step 1 - Tailscale SSH

Proxmox is joined to Tailscale during phase 1. Builder VMs enroll during
cloud-init, then cloud-init enables their Tailscale SSH host feature. The
approved Builder transport is Tailscale SSH for both bootstrap and regular
automation; do not add or reuse a VM SSH key for CI.

## Enable Tailscale SSH on a Linux host

Verify enrollment and the host feature:

```bash
tailscale status
tailscale ip -4
```

The first Builder connection is as `autolab`; after `harden.yml` creates the
account, regular runs use `gitops`:

```bash
tailscale ssh autolab@HOSTNAME
tailscale ssh gitops@HOSTNAME
```

`HOSTNAME` can be the MagicDNS name or the Tailscale IP.

## Tailnet policy

Tailscale SSH is controlled by the tailnet policy, not by VM `authorized_keys`.
The policy is configured manually by the tailnet administrator. Use exactly
`tag:ci-runner` for ephemeral CI runners and `tag:autolab-vm` for Builder VMs.
The runner needs a network grant to the VM tag and SSH accept rules limited to
`autolab` for bootstrap and `gitops` afterward. Never include `root`.

Example shape:

```json
{
  "ssh": [
    {
      "action": "accept",
      "src": ["tag:ci-runner"],
      "dst": ["tag:autolab-vm"],
      "users": ["autolab", "gitops"]
    }
  ]
}
```

The `tagOwners` entry and tag assignment authority must be owned by the
tailnet administrator, not by a VM or CI job. Keep this policy in the
Tailscale admin console first; version it later only through an approved
tailnet-policy workflow.

The VM enrollment credential is a short-lived, reusable-per-VM key managed by
OpenTofu and stored in remote state so subsequent reconciliation can reuse it.
Before replacing a VM, manually retire its old `tag:autolab-vm` device first;
otherwise the stable MagicDNS target can become suffixed or stale. Terraform
does not automatically clean up Tailscale devices. Revoke/expire the old
enrollment key and remove the stale machine after retirement.

## Security notes

- Tailscale SSH does not modify `/etc/ssh/sshd_config` or VM
  `~/.ssh/authorized_keys`; Ansible still applies the server hardening policy.
- `PVE_SSH_PRIVATE_KEY` is only a Proxmox bastion key. Never reuse it for a VM.
- CI authenticates its tailnet runner through GitHub OIDC/WIF; do not store or
  rotate a Tailscale OAuth client secret for Builder transport.
- Do not allow root login, and do not expose SSH from lab machines publicly.

## Builder workflow

Use the persistent canary for the first bootstrap (this documents the
procedure and does not claim that a canary run has occurred):

1. Provision/enroll the VM and confirm its `tag:autolab-vm` policy.
2. Run workflow **05 - Ansible Builder** as `autolab` to apply `harden.yml`.
3. Confirm the SSH policy for `gitops`, then run the regular Builder path as
   `gitops`.
4. Run the optional Docker playbook only after the baseline is healthy.
- Do not expose SSH from lab machines to the public internet.

Sources:

- [Tailscale SSH](https://tailscale.com/docs/features/tailscale-ssh)
- [Tailnet policy syntax](https://tailscale.com/kb/1337/acl-syntax/)
