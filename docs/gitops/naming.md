---
tags: [gitops, naming, conventions]
status: draft
audience: operator
---

# Naming

Machines are named for **what they are**, not where they sit. `lab-01` tells you
nothing; `hubble` tells you it observes.

The theme follows the NAS, `singularity` — cosmology rather than generic space.

## The rule

| Kind | Convention | Examples |
|---|---|---|
| **Singletons** — one of a thing | a unique named object | `singularity` (NAS), `hubble` (observability) |
| **Fleets** — scale out | object *class* + number | `pulsar-01..N`, `polaris-01..03` |

The split is what makes this survive a cluster. Unique things get proper names;
anything you might run several of gets a class name and a number, so the fifth
worker is obviously `pulsar-05` and nobody has to invent a name or remember
which telescope is already taken.

## Current and reserved

| Name | Role | Status |
|---|---|---|
| `singularity` | NAS — everything collapses inward | in use |
| `hubble` | observability — it observes | in use |
| `voyager-01` | disposable probe, sent out to test the unknown | in use |
| `polaris-NN` | cluster control plane — the navigation star | reserved |
| `pulsar-NN` | cluster workers — emit energy on a cycle | reserved |
| `horizon` | ingress / gateway — an event horizon is a boundary | reserved |
| `lagrange` | edge or relay — a Lagrange point is a stable waypoint | reserved |

Pick legibility over cleverness. The name has to mean something at 2am during
an incident, which is the only time anyone reads it carefully.

## Renaming costs a rebuild

A machine's name is baked into its first-boot cloud-init, as both the
`hostname` and the snippet filename. Changing it forces the cloud-init file to
be replaced, which forces the VM to be replaced. There is no in-place rename:

```
~ file_name = "lab-02-cloud-init.yaml" -> "hubble-cloud-init.yaml"  # forces replacement
~ data      = (sensitive value)                                     # forces replacement
```

That is not a limitation to work around. cloud-init only runs on first boot, so
a rename that preserved the VM would leave the guest still calling itself by the
old name — correct in Proxmox, wrong inside the machine.

### Do not reach for `moved` blocks

`moved` blocks look like the fix: they rename state entries and halve the churn.
They also **break Tailscale device cleanup**.

`terraform_data.tailscale_device_cleanup` has
`triggers_replace = [vm_id]`, and a rename does not change `vm_id`. With a
`moved` block the cleanup resource is *updated in place* rather than destroyed,
so its destroy-time provisioner never runs. The VM is replaced regardless and
rejoins under the new name, leaving the old device on the tailnet forever.

That is precisely the orphan described in
[Tailscale device lifecycle](./tailscale-device-lifecycle.md). Let the rename
destroy and recreate: the cleanup hook fires, the old device is revoked, and the
new one joins cleanly.

### What a rename actually costs

- both VMs rebuilt from the template — minutes, and the playbooks reproduce
  everything on them
- **new Tailscale addresses**, so per-host NFS export rules on the NAS must be
  updated to match
- anything not in git is gone, which is the point of keeping it in git

Rename early. The cost grows with every service deployed on top.
