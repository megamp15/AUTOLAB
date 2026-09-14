---
tags: [gitops, naming, conventions]
status: draft
audience: operator
---

# Naming

Machines are named for **what they do**, not where they sit or when they were
made. `lab-01` tells you nothing; `jwst` tells you it observes.

The theme follows the NAS, `singularity` — cosmology and spaceflight rather
than generic space words.

## Number what is interchangeable, name what is not

The default is a **unique object per machine**. Reach for a number only when
members of a group are genuinely substitutable — where node three could be
swapped for node four and nothing would notice.

| Ask | Then |
|---|---|
| Can you say what makes this machine different from its neighbours? | give it its own name |
| Would you shrug if it were replaced by an identical one? | number it |

A cluster worker pool is the clear case for numbering: `pulsar-01`, `pulsar-02`
are deliberately identical, and inventing a distinct name for each would imply a
difference that does not exist. An observability host is the clear case against
— there is one, it does a specific job, and `jwst-01` would be pretending
otherwise.

Applied to what exists today: `sputnik` and `jwst` do different jobs, so they
get different names rather than `lab-01` and `lab-02`.

## Pools by role

Each role draws from a pool of objects whose real-world job matches the
machine's. That is what makes a name readable to someone who has never seen the
inventory.

| Role | Pool | Names |
|---|---|---|
| Storage | gravity wells — everything collapses inward | `singularity` |
| Observability | observatories and telescopes — they watch | `jwst`, `chandra`, `hubble`, `kepler` |
| Disposable / test | early probes and satellites — built to prove a thing, then discarded | `sputnik`, `pioneer`, `explorer`, `voyager` |
| Cluster control plane | navigation stars — they guide | `polaris`, `vega`, `sirius`, `canopus` |
| Cluster workers | energetic emitters — they do the work | `pulsar-NN`, `quasar-NN` — numbered, being interchangeable |
| Ingress / gateway | boundaries and waypoints | `horizon`, `lagrange` |

Pick legibility over cleverness. The name has to mean something at 2am during an
incident, which is the only time anyone reads it carefully.

## In use

| Name | Role | Why that name |
|---|---|---|
| `singularity` | NAS | everything collapses inward; it is where the data goes |
| `jwst` | observability | the James Webb telescope sees infrared, so it sees *through* the dust that blocks optical instruments |
| `sputnik` | disposable probe | the first satellite: simple, proved the concept, then burned up |

## Renaming costs a rebuild

A machine's name is baked into its first-boot cloud-init, as both the
`hostname` and the snippet filename. Changing it replaces the cloud-init file,
which replaces the VM:

```
~ file_name = "lab-02-cloud-init.yaml" -> "jwst-cloud-init.yaml"  # forces replacement
```

That is correct rather than a limitation. cloud-init runs only on first boot, so
a rename that preserved the VM would leave the guest still calling itself by the
old name — right in Proxmox, wrong inside the machine.

**Name a machine correctly when you create it.** The cost grows with every
service deployed on top.

### Do not reach for `moved` blocks

`moved` blocks look like a way to rename without rebuilding. They halve the
state churn and **break Tailscale device cleanup**.

`terraform_data.tailscale_device_cleanup` has `triggers_replace = [vm_id]`, and
a rename does not change `vm_id`. With a `moved` block that resource is updated
in place rather than destroyed, so its destroy-time provisioner never runs. The
VM is replaced regardless and rejoins under the new name, leaving the old device
on the tailnet forever.

That is precisely the orphan described in
[Tailscale device lifecycle](./tailscale-device-lifecycle.md). Let the change
destroy and recreate: the cleanup hook fires, the old device is revoked, and the
new one joins cleanly.

### What a rebuild costs

- the VM is recreated from the template — minutes, and the playbooks reproduce
  everything on it
- **a new Tailscale address**, so per-host NFS export rules on the NAS must be
  updated to match
- anything not in git is gone, which is the point of keeping it in git
