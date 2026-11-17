---
name: nas
description: Work with the NAS (singularity) in AUTOLAB - its Docker projects, Immich, photo jobs, NAS mounts on VMs, and export rules. Use for a new mount, a permission error on a share, an Immich change, or NAS telemetry.
---

# The NAS

singularity is a UGOS appliance, not a VM: it has its own inventory and its
own workflow (`12`). What is managed and what is not:
`docs/gitops/singularity.md`. Mounts: `docs/gitops/nas-storage.md`.

## Its Docker projects

`12` defaults to read-only inspection.

| `action` | does |
|---|---|
| `inspect` | reads the projects and containers; changes nothing |
| `adopt` | writes the tracked Compose files to the existing directories, with backups; never runs `up`, pulls or recreates |
| `telemetry` | the agent and cAdvisor |
| `management` | the Dockhand agent |
| `photos` | the photo service |
| `start`, `stop`, `restart` | Compose's own commands on Immich's existing containers |

1. `gh workflow run 12_nas.yml --ref main -f action=inspect -f confirm=check`.
   Read what is there.
2. The action, `confirm=check`, then `confirm=apply`.
3. Done when the run's container identities match before and after (it
   checks), and the app answers.

## A mount on a VM

1. Declare it in the machine's `builder.storage` (`new-vm`): `protocol =
   "nfs"` when the NAS can see the host's own tailnet address, `"smb"` for a
   tenant VM behind the node's NAT. The server is the MagicDNS name, the
   mount point is named for the share.
2. **By hand, on the NAS**: the export rule. Give the user these steps:
   UGOS → Shared Folder → the share → NFS Permissions → add the host by its
   tailnet name, read/write, squash *No mapping* (PBS's host is the
   exception: *map all users to admin*). Then check the folder's
   permissions still list what they did.
3. `run-workflow`: `04`, then `05` `storage`, `limit=<host>`, check then
   apply. The role writes a probe file as the user that will use the mount
   before it creates anything, so a wrong rule fails at the top with a
   readable message.
4. Unmount with `state: absent` on the entry, then remove it in a later
   change. Deleting the entry stops managing the mount; it does not undo it.

## When a share refuses

| symptom | cause |
|---|---|
| permission denied right after someone edited a user in UGOS | saving a user's permissions rewrites every folder's ACLs; restore the folder's mode by hand (the datastore: `chmod 750 /mnt/autolab/ark` on the NAS side) |
| a rebuilt VM cannot mount | its tailnet address changed and the export rule names the old one |
| a non-root user cannot write | the share root's mode: use the per-host directory the role creates, or sudo |

## Guardrails

- The playbook does not install Docker, upgrade UGOS or touch disks.
- A live database never sits on an NFS or SMB mount.
- Photo jobs can move files: they are started on purpose, never by a
  generic restart.
