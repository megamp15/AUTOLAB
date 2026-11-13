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
| photo-sort | `/volume1/docker/photo-sort` | Import sorter and duplicate utility; explicit jobs only |
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

## What the photo scripts currently do

The source was recovered from the NAS into
`builders/ansible/roles/nas-projects/files/`. Neither job calls the Immich API.

### photo-sort

`sort.py` reads recording dates with ExifTool and supports these modes:

| Mode | Current behavior |
|---|---|
| `plan` | Writes `plan.txt`; does not move media |
| `apply` | Sorts loose files and events; writes undo commands to `moves.log` |
| `dupes` | Calls `dupes.py` to write a byte-identical duplicate report |
| `dupes-apply` | Applies the report's keep choices; defaults to moving extra copies into `_duplicates` |
| `undo` | Executes NAS-local `undo.sh` once, then renames it |

`_inbox/loose` is recursive: a folder uploaded there does not become an event.
Each photo/video goes to `library/YYYY/MM`; undated files go to `_no_date`.
Each directory directly under `_inbox/events` is one event. The event is placed
as a group under its dominant recording month, or the previous month if that
month contains at least half as many dated files. Existing event directories
are merged without overwriting files. Dates, not event folder names, decide
placement. The script also handles event directories directly inside a year.

`dupes.py` compares file size, a partial SHA-1 and then the full SHA-1. It
prefers copies in event folders, then loose dated library files. The generated
`duplicates.csv` has editable keep choices. `DUPLICATES=delete` enables a
separate permanent-deletion branch that rechecks a matching kept copy.
Adoption does not execute it.

The live Compose file was last set to `MODE=dupes-apply`. The managed default
is now `${MODE:-plan}`. The stopped legacy container keeps its old environment
until a new explicit job is created; generic lifecycle controls therefore
never start that container.

**Live Photos.** A HEIC/JPEG and the MOV beside it (same folder, same name apart
from the extension) are one photo, and `pairs.py` is what both scripts use to
see that. The still decides the month for both; a name clash renames both with
the same `_N`; a pair counts as a duplicate only when both halves are; and
`dupes-apply` removes a half only when its other half is being removed too,
otherwise it logs that it left it alone. A pair whose halves were renamed apart,
or a name with two stills, is not recognisable and is treated as separate files.
The link is the name, not Apple's ContentIdentifier, which would need ExifTool
to read and is not used yet. `scripts/test_photo_sort.py` runs the real scripts
against a throwaway library with a stand-in ExifTool.

The sorter also moves XMP sidecars, but does not track Immich asset IDs.

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

Immich's `/mnt/mahir-personal` mount remains read-only. A separate Photo Jobs
service will own plan/review/run actions, durable job status and logs. It will
replace editing a shared `MODE` value. The intended workflow is:

1. Preview and run `_inbox` sorting with explicit event/loose semantics.
2. Review duplicates in Immich or a generated report.
3. Preview NAS cleanup from explicitly selected Immich trash assets.
4. Resolve each asset's exact source path and linked Live Photo partner,
   validate both against the allowed media root, and quarantine the selected
   originals with a reversible manifest. An absent API result is never a
   deletion instruction.

This service and its deletion workflow are subsequent implementation work.
The adoption phase does not enable automatic sorting or deletion.

## Docker management and the UGOS desktop

`action=management` deploys a token-authenticated Hawser agent on Singularity,
registers it in the existing Dockhand on jwst, and tests the connection against
the NAS engine. Only after that succeeds does it remove the Portainer
container. Its bind-mount data stays under `/volume1/docker/portainer`.
No Immich or photo container is recreated by this action.

The manager opens at `https://dockhand.lab.pmahir.space`. Select `singularity`
in its environment selector. Hawser only listens on the NAS Tailscale address;
its Docker API requires the generated agent token. That token stays on the
NAS and in Dockhand's protected connection settings.

The separate `dockhand-launcher` container has no Docker socket. Its port 9000
only redirects to the protected Dockhand URL. To add it to the UGOS desktop:
Docker → Containers → `autolab-management-dockhand-launcher-1` → … → Desktop
shortcut. Use name **Dockhand** and access port **9000**. Keep Tailscale enabled
on the device opening it. This uses UGOS's supported shortcut mechanism,
without editing its internal desktop configuration.

Reference: [UGOS Docker desktop shortcuts](https://support.ugnas.com/detail/article/en-US/715).
