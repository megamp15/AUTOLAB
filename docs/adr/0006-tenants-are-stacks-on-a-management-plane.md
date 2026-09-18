# ADR-0006: A tenant is a stack, reached over the management plane

## Status

Accepted — 2026-09-18

## Context

The hypervisor will host VMs for more than one owner: the personal lab and a
business with its own tailnet, its own people and its own CI. The business
wants separation — its VMs on its network, invisible from the lab — and the
provider wants one set of modules, workflows and baseline roles rather than
a fork per owner.

A Proxmox cluster is a single trust domain: root on one node is root on all.
Separation at the host layer is therefore not on offer without separate
clusters, and separate clusters give up the quorum and HA the second and
third nodes are meant to provide. The separation that is on offer is at the
guest layer: which tailnet a VM enrols on, and who can reach it there.

Two mechanical facts shape the answer. A VM runs one `tailscaled` and is on
one tailnet. And the Builder reaches VMs by MagicDNS name over the provider's
tailnet, authenticating through Tailscale SSH — neither of which exists for a
VM on someone else's tailnet.

## Decision

**A tenant is a stack.** `infra/stacks/<tenant>/` has its own machine map,
its own state in R2 and a GitHub Environment of the same name. The
environment carries the tenant tailnet's OAuth client under the *same secret
names* the provider uses, so the unchanged plan, apply, destroy and Builder
workflows enrol that stack's VMs on that tailnet. The stack declares
`tenant = "<name>"` and enrols under `TAILSCALE_VM_TAG`.

**The Builder reaches tenant VMs over the management plane.** The node's
private bridge (`vmbr1`, `10.42.0.0/24`) is the provider's network; the
tailnet is the tenant's. For a tenant stack the Builder inventory names each
VM by bridge address with `ProxyJump` through the hypervisor, which the
runner already reaches as `tag:autolab-pve`. This requires a static
`ipv4_address` and `ipv4_gateway` per machine (enforced at plan time), a
Builder SSH keypair for plain `sshd` (`BUILDER_SSH_*`), and an SSH rule from
the hypervisor's bridge address, which the stack injects so it cannot be
omitted.

**The tenant owns everything from the VM up.** Its tag, its SSH policy, its
swarm, its services. The provider owns everything from the VM down.

## Consequences

- The provider's own stack is unchanged: `tenant = null`, dialled by name,
  no key, no jump. Its VMs are not rebuilt by this change.
- The runner never joins a tenant tailnet and holds no tenant credential
  beyond a tag-scoped OAuth client that can mint join keys and delete the
  devices it created.
- The two planes are now explicit. Provider services that should reach
  tenant VMs — backups, monitoring — go over the bridge, which means `jwst`
  and later `ark` want declared bridge addresses too.
- `common_tags` carries `tenant-<name>` so the lab's alert rules can tell a
  tenant guest from an unmonitored one of their own.
- A second node must share `vmbr1` as one L2 segment. A NAT bridge per node
  gives each node its own isolated `10.42.0.0/24`, and a migrated VM would
  keep an address nothing on the other node can reach.
- The alternatives — sharing tenant nodes into the provider's tailnet,
  running a second `tailscaled` per VM, or a runner on both tailnets — were
  rejected: the first is manual per device and does not survive a rebuild,
  the other two put the provider's access path inside the tenant's network,
  which is the wrong dependency direction. The provider must reach the box
  when the tenant's network is the thing that is broken.
