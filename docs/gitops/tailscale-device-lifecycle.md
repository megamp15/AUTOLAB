---
tags: [gitops, tailscale, opentofu, lifecycle]
status: draft
audience: maintainer
---

# Tailscale device lifecycle

This document explains how a Proxmox-created machine becomes a Tailscale
device, who owns each transition, and what happens to the device record when
the machine goes away. It exists because of a real incident: destroying and
recreating `lab-01` left an orphaned device (`lab-01-1`) on the tailnet,
because OpenTofu destroyed the VM but nothing removed its Tailscale identity.

## The core problem: async join means no stored reference

OpenTofu creates the VM and hands it a join key. The VM then boots, runs
cloud-init, installs Tailscale, and joins the tailnet **asynchronously** —
minutes after the apply finished, on a machine OpenTofu no longer talks to.

The device ID that Tailscale assigns at join time is therefore **unknowable
at plan time**. OpenTofu state tracks the join *key*, never the *device*.
There is no stored reference to revoke at destroy time.

Destroy-time resolution is instead by **deterministic name + tag**: every
Autolab VM joins with hostname = machine name and carries `tag:autolab-vm`
(the tag arrives free — it is baked into the auth key). At destroy, we list
all devices with that tag whose name matches, and delete every match.

We deliberately do NOT manage the device as an OpenTofu resource. An import
workflow would be drift theater: the resource would describe something
Tailscale created outside OpenTofu, on a schedule OpenTofu cannot observe.

## State diagram

```
                    tofu apply (VM created, auth key minted)
                   │
                   ▼
             ┌────────────┐   cloud-init: install.sh + tailscale up   ┌────────────┐
             │ Provisioned │ ───────────────────────────────────────▶ │   Joined    │
             └────────────┘        (async, minutes after apply)       │  (async)   │
                                                                      └─────┬──────┘
                                                                            │ verified reachable
                                                                            ▼
                                                                      ┌────────────┐
                                        operator: tofu destroy        │   Running   │
                     ┌────────────────────────────────────────────────└─────┬──────┘
                     │ local-exec destroy hook                              │ month offline?
                     │ (delete device by name+tag)                          ▼
                     ▼                                                ┌────────────┐
               ┌────────────┐        tofu: VM disk destroyed          │  Running    │
               │   Revoked   │ ◀───────────────────────────────────  │ (offline)   │
               └─────┬──────┘                                       └────────────┘
                     │
                     ▼
               ┌────────────┐
               │  Destroyed  │   (no VM, no device record)
               └────────────┘

  Orphaned: a device record whose VM no longer exists. Caused by destroys
  before this hook existed, or state loss/rename. Cleaned manually or via
  the script; see failure matrix.
```

## Ownership table

| Transition | Owner | Mechanism |
|---|---|---|
| Provisioned | OpenTofu | `proxmox_virtual_environment_vm` + `tailscale_tailnet_key` (per-machine, reusable, expiry 3600s) |
| Provisioned → Joined | cloud-init in the guest | install.sh, retrying `tailscale up --auth-key=…`, verify with `tailscale wait` |
| Joined → Running | nobody (observation) | CI reachability checks; `tailscale wait --timeout=60s` at boot |
| Running → Revoked | OpenTofu destroy hook | `terraform_data.tailscale_device_cleanup` local-exec → `scripts/tailscale-device-delete.sh <hostname>` |
| Revoked → Destroyed | OpenTofu | normal VM destroy, ordered AFTER revocation via reversed `depends_on` |
| → Orphaned | incident path | destroy without cleanup (pre-hook destroys, state loss) |

## Why the hook lives in the graph

```hcl
resource "terraform_data" "tailscale_device_cleanup" {
  for_each         = module.machine_inputs.builder_target_vm_machines
  triggers_replace = [module.machine[each.key].vm_id]

  provisioner "local-exec" {
    when    = destroy
    command = "${path.module}/../../scripts/tailscale-device-delete.sh ${each.value.name}"
  }

  depends_on = [module.machine[each.key]]
}
```

Three properties make this the right shape:

1. **Ordering reverses for free.** `depends_on` means "create me after";
   destroy applies in reverse, so the device is revoked **before the disk
   dies** — while the VM could still technically answer, and more importantly
   so a failed cleanup aborts before infrastructure is gone.
2. **Template rebuilds clean up too.** `triggers_replace = [vm_id]` fires the
   hook whenever the VM is replaced (new template pin, forced recreation),
   not just on full destroy. This is exactly the path that created the
   `lab-01-1` orphan.
3. **It runs wherever tofu runs.** GitHub Actions destroy workflow exports
   `TAILSCALE_OAUTH_CLIENT_ID` / `TAILSCALE_OAUTH_CLIENT_SECRET`; a local
   investigation destroy works identically if you export the same names.

## Ephemeral vs persistent keys — why `ephemeral = false`

Tailscale auth keys come in two flavors, and the choice encodes a lifetime
promise about the machine:

| Property | Ephemeral node | Persistent node (our choice) |
|---|---|---|
| Auto-cleanup | Yes — deregistered shortly after going offline | No — record persists until explicitly deleted |
| Survives reboot/offline | **No** — extended power-off drops it from the tailnet permanently | Yes — identity persists in `/var/lib/tailscale/tailscaled.state` |
| Intended for | Disposable containers, CI throwaways | Long-lived servers |

Ephemeral looks like free cleanup, but it silently deletes the wrong thing:
a homelab VM powered off for a month is *normal*, and ephemeral semantics
would drop `lab-01` off the tailnet during exactly that period. Persistent
enrollment plus our explicit destroy hook is the correct pairing for the
`lab` stack.

Ephemeral enrollment belongs to the future disposable experiment track
(`template-validation` candidates), where machines are born to die quickly.
It will be wired when that environment exists — not before.

## Failure matrix

| Scenario | Outcome | Recovery |
|---|---|---|
| Cleanup succeeds, VM destroy fails | Device gone, VM alive, state consistent | Re-run destroy; cleanup is a no-op second pass (0 matches → exit 0) |
| Cleanup fails (API down, bad creds) | Apply aborts BEFORE VM destruction; nothing lost | Fix cause, re-run destroy |
| State lost or machine renamed | Hook cannot match the old name → orphan possible | Run the script manually with the old hostname, or delete in admin console |
| Duplicate devices exist (e.g. `lab-01-1`) | Script deletes ALL name+tag matches | Intentional: duplicates are always stale identities of the same machine |

The state-loss hole is accepted for now. A future backstop — a weekly
report-only sweep listing `tag:autolab-vm` devices offline beyond N days,
opening an issue instead of deleting anything — is deliberately deferred;
no code or workflow for it exists yet.

## Manual fallback

The script is the manual tool. From any machine with the OAuth client creds:

```sh
export TAILSCALE_OAUTH_CLIENT_ID=…     # k1234… from admin console
export TAILSCALE_OAUTH_CLIENT_SECRET=…
scripts/tailscale-device-delete.sh lab-01
```

Equivalent raw API calls, if you need to do it by hand:

```sh
TOKEN=$(curl -sS -u "$TAILSCALE_OAUTH_CLIENT_ID:$TAILSCALE_OAUTH_CLIENT_SECRET" \
  -d grant_type=client_credentials https://api.tailscale.com/api/v2/oauth/token \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -sS -H "Authorization: Bearer $TOKEN" \
  https://api.tailscale.com/api/v2/tailnet/-/devices   # find the id

curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
  https://api.tailscale.com/api/v2/device/<DEVICE-ID>
```

Last resort: the admin console Machines page → delete.

## Version strategy: always-current stable

Two lanes keep Tailscale current, split along the same ownership line as
everything else:

| Lane | Owner | Mechanism |
|---|---|---|
| First boot (new VMs) | cloud-init | Official installer `curl -fsSL https://tailscale.com/install.sh \| sh` — resolves the **current stable release at boot time**, adds the official apt repo, enables `tailscaled`. This is Tailscale's recommended bootstrap path and is CI-tested upstream. |
| Existing hosts | Ansible | `playbooks/tailscale-update.yml` → `tailscale-update` role: re-asserts the official apt repo (keyring style) and `apt: state=latest`. Run it via **05 - Ansible Builder** with playbook `tailscale-update`. |

Deliberate choices:

- **Stable track everywhere.** Unstable ships multiple builds per week with
  no staging delay; wrong for hosts CI depends on being reachable.
- **No `tailscale set --auto-update`.** Known race (upstream #10400): the
  built-in updater can interrupt dpkg mid-run when it collides with
  unattended-upgrades, leaving the host needing `dpkg --configure -a`.
  Upgrade timing stays under GitOps control.
- **No version pinning.** If a release ever breaks CI reachability, pinning
  via `TAILSCALE_VERSION=` (installer) or `apt-get install tailscale=<ver>`
  is the documented escape hatch — added then, not speculatively.

## Secrets and scopes

| Name | Where | Scope | Used by |
|---|---|---|---|
| `TAILSCALE_OAUTH_CLIENT_ID` / `TAILSCALE_OAUTH_CLIENT_SECRET` | GitHub secrets (`TAILSCALE_VM_OAUTH_*`), exported by plan/apply/destroy workflows | OAuth client scoped `devices:core:read_write` ONLY | Destroy-time cleanup hook (and manual runs) |
| Per-machine auth key | Minted by `tailscale_tailnet_key`, embedded in cloud-init user-data | `tag:autolab-vm`, reusable, expires 3600s | First-boot join only |

Setup instructions: create a dedicated OAuth client in the Tailscale admin
console (Settings → OAuth clients) with **only** the `devices:core:read_write`
scope — not the CI-runner client, and never with `auth_keys` scope (least
privilege: cleanup can list/delete devices, nothing else). Store as GitHub
secrets `TAILSCALE_VM_OAUTH_CLIENT_ID` / `TAILSCALE_VM_OAUTH_SECRET`.

Accepted tradeoff: the join key lands in OpenTofu state and plan artifacts
(embedded in cloud-init user-data). Blast radius is capped by the 1-hour
expiry, the single-tag scoping, and the private R2 bucket. If this ever
becomes unacceptable, the escape hatch is minting keys outside OpenTofu and
passing them in — documented here, built never until needed.
