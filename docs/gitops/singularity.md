---
tags: [gitops, nas, docker, observability, photos]
status: active
audience: operator
---

# Singularity

Singularity is a physical UGOS appliance in the lab. Its declaration is
`builders/ansible/inventories/nas/hosts.yml`, separate from Proxmox's generated
VM inventory. The NAS playbook manages existing Docker projects and telemetry.
It does not install Docker, upgrade UGOS, repartition disks or run the VM
hardening roles.

The confirmed NAS SSH account is `root`. The dedicated `tag:autolab-nas`
allows the CI runner to reach only that appliance as root; the VM SSH rules
continue to deny root. Apply the policy before assigning the NAS tag:

```sh
# After the policy PR is merged and workflow 06 succeeds, on the NAS:
tailscale up --advertise-tags=tag:autolab-nas --ssh
```

## Existing projects

| Project | Existing location | Management |
|---|---|---|
| Immich | `/volume1/docker/immich` | Adopt Compose; retain `.env`, OAuth config, database and media paths |
| Portainer (retired) | `/volume1/docker/portainer` | Container removed after Dockhand verification; data retained |
| photo-jobs | `/volume1/docker/photo-jobs` | The photo service (below). Built from `apps/photo-jobs`; workflow 12 `photos` |
| photo-sort (retired) | `/volume1/docker/photo-sort` | The old sorter. Replaced by photo-jobs; its container and `moves.log` history stay on the NAS |
| immich-export | `/volume1/docker/immich-export` | Import the existing generated migration script; explicit jobs only |
| autolab-observability | `/volume1/docker/autolab-observability` | Managed Alloy and cAdvisor project |

Workflow **12 - NAS** defaults to read-only inspection. `action=adopt` writes
the tracked Compose files and photo source to those existing directories,
with backups of changed files. It never runs `compose up`, pulls images,
recreates containers or starts a photo job. Container identities are checked
before and after adoption. Application secrets remain on the NAS.

```sh
gh workflow run 12_nas.yml --ref main -f action=inspect -f confirm=check
gh workflow run 12_nas.yml --ref main -f action=adopt -f confirm=apply
gh workflow run 12_nas.yml --ref main -f action=telemetry -f confirm=apply
```

Explicit `start`, `stop` and `restart` actions use Compose's commands for
existing Immich containers. They never use `up` or `down`.
Photo jobs are excluded because starting them can modify files.

## Observability

Alloy reads the NAS's host proc/sys/filesystem mounts and Docker logs.
cAdvisor reads the actual Docker root discovered from `docker info`, which
is `/volume1/@docker` on this appliance. Exporter listeners stay on loopback.
The agents write to the existing Prometheus and Loki on jwst over Tailscale.
All metric and log series identify the appliance as `singularity`.

Grafana's **Autolab / Singularity NAS** dashboard covers host usage, the main
volume, sensors, network, container CPU/memory and Docker logs. Existing Host
and Container selectors discover the NAS from telemetry. `/home` and
`/volume1` expose the same filesystem and must not be added together. The
reported volume capacity is logical filesystem capacity, not raw drive sizes.
RAID/sensor panels show only metrics the NAS kernel exposes. SMART health is
not inferred from a successful Alloy scrape.

UGOS shows the agents under Containers. Its Projects list can omit a Compose
project created over SSH; that does not prevent IaC from managing it.

## Photo Jobs

The photo workflow is a web app, `apps/photo-jobs`, running as one container on
the NAS at <https://photos.lab.pmahir.space> (Pocket ID admins only). It
replaced the old `sort.py` and `dupes.py` scripts, whose behaviour it carries
over. See `apps/photo-jobs/README.md` for what it does.

**Plan, review, apply, undo.** A scan returns the exact moves; each can be
unticked; apply makes only the ticked ones and writes a run record; undo puts a
run's files back. Nothing is deleted: duplicates are filed under `_duplicates/`
beside the kept copy. A Live Photo's still and clip are dated, named and ticked
as one. The Immich containers mount the media folder read-only; Photo Jobs is
the only thing that moves files in it.

**Deploying it.** Workflow **12 - NAS**, `action=photos`, `confirm=check` then
`apply`. It copies `apps/photo-jobs` to `/volume1/docker/photo-jobs`, builds the
image there, and starts only that project. It requires the `PHOTO_JOBS_TOKEN`
environment secret (the play stops without it), proves the API refuses a request
without the token, and proves the Immich containers kept the same IDs and start
times. Updating is the same run: the app changes in git, the run rebuilds the
image, and a rerun with nothing changed reports no changes.

**Who can reach it.** Traefik on horizon routes `photos.lab.<zone>` to the NAS
with the Pocket ID admin login in front, then adds the token as
`X-Autolab-Photos-Token`. The service refuses `/api/*` without it, so reaching
the NAS's port directly gets nothing. Run workflow 05 `ingress` after the secret
exists; with no token there is no route at all.

State (scan plans and run records) is under `/volume1/docker/photo-jobs/state`.

### immich-export

`export.sh` is a generated, one-time migration of **15,654** mappings. It
copies from the old `/volume1/docker/Immich-Upload` tree into
`/home/Mahir/media/old_immich_upload_extracted`, restoring dated directories
and original names from the old migration's mapping. Files absent from that
mapping are placed under `_not_in_old_database`. Its old source mount is
read-only; `cp -pn` preserves timestamps and does not overwrite destinations.

This is not a live Immich export, synchronization process or deletion bridge.
The imported generated file is intentionally unchanged. Its NAS-local
`manifest.tsv` and reports are runtime data. Its failure counter is printed,
but the script does not return failure just because some copies failed, and
existing destination files are not content-verified. These are requirements
for the replacement, not reasons to rerun the migration during adoption.

## Next photo workflow

Photo Jobs sorts the inbox and files duplicates. Still to do, in this order:

1. Review duplicates against Immich, not only against the files.
2. Preview NAS cleanup from explicitly selected Immich trash assets.
3. Resolve each asset's exact source path and linked Live Photo partner,
   validate both against the allowed media root, and quarantine the selected
   originals with a reversible manifest. An absent API result is never a
   deletion instruction.
