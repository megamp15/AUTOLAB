---
tags: [proxmox, nodes, onboarding, runbook]
status: alpha
audience: operator
---

# Adding a node

Every node is its own place: the nodes are **not clustered**, and nothing here
assumes they are. A new node joins the lab by being on the tailnet as
`tag:autolab-pve`, having its own API and monitoring tokens, and being named in
the few places the repository lists nodes. After that the same workflows that
manage `xps-pve` and `pve` manage it.

Why no cluster: `xps-pve`'s only uplink is Wi-Fi, and corosync over Wi-Fi loses
quorum on every drop; a node can only join a cluster while it has no guests;
and storage, tokens, the OpenID realm and the `10.42.0.0/24` private bridge are
all per node here. See [ADR-0006](../adr/0006-tenants-are-stacks-on-a-management-plane.md)
for the per-node design.

The steps below are how `zima-pve` (ZimaBoard 2, 2026-10-16) was added, with
what went wrong on the way.

## 1. Install Proxmox

[01-bare-metal-install.md](./01-bare-metal-install.md). Plug the Ethernet cable
in **before** the installer starts: with no link it invents a network
(`192.168.100.x`) and writes that into the node's address, `/etc/hosts` and
its certificate. Give the node its LAN address in the installer
(`192.168.50.x/24`, gateway `192.168.50.1`).

Check from the node's console:

```bash
ip -br addr                 # vmbr0 has the LAN address
grep "$(hostname)" /etc/hosts   # the LAN address, not 192.168.100.x
cat /etc/resolv.conf        # see below
```

**DNS points at the node itself.** The installer writes the node's own address
as its nameserver; nothing answers there, so every lookup fails
(`curl: (6) Could not resolve host`). Point it at the router until Tailscale
takes over DNS:

```bash
sed -i 's/^nameserver .*/nameserver 192.168.50.1/' /etc/resolv.conf
```

**A certificate from the wrong network.** If `/etc/hosts` was right but the web
certificate still lists the installer's address, regenerate it (no reboot):

```bash
pvecm updatecerts --force && systemctl restart pveproxy
```

**Enterprise repositories.** A fresh install has the subscription repositories
on, so every `apt-get update` fails with `401 Unauthorized`, and so does any
installer that runs it. Node → *Updates* → *Repositories*: disable the two
`enterprise.proxmox.com` lines, *Add* → *No-Subscription*. The
`proxmox-repos` role keeps this right once the node is onboarded.

## 2. Join the tailnet, tagged

Tailscale is how CI and people reach a node. Request the tag **at login**: a
device tagged when it authenticates has key expiry off; one tagged afterwards
keeps its expiry (that is why `xps-pve`'s expires on 2026-11-21).

```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --hostname=<node> --ssh --advertise-tags=tag:autolab-pve
```

Approve the login link in the browser, signed in to the lab tailnet. The admin
console then shows the node with `tag:autolab-pve` and *Expiry disabled*.
Tailscale SSH works from then on (`ssh root@<node>.<tailnet>`, with a browser
check), and the node's DNS becomes Tailscale's (`100.100.100.100`).

## 3. Extra disks as VM storage

A SATA disk connected while the node is running may not appear at all: the
ZimaBoard's ports are only probed at boot (`ata2: SATA link down` until a
reboot). Reboot with the disk connected, then check its health before trusting
it:

```bash
lsblk -d -o NAME,SIZE,ROTA,MODEL,SERIAL
smartctl -H -A /dev/sdX | grep -E "overall-health|Reallocated|Pending|Uncorrectable|Power_On"
```

To wipe it and add it as an LVM-thin storage (here named `hdd`), address the
disk by its serial so the system disk cannot be hit by mistake. `partprobe` is
not installed on Proxmox; `partx` is:

```bash
dev=/dev/disk/by-id/ata-<MODEL>_<SERIAL>
wipefs -a "$dev"-part* ; wipefs -a "$dev"
sgdisk --zap-all "$dev"
sgdisk -n1:0:0 -t1:8e00 -c1:hdd "$dev"
partx -u "$(readlink -f "$dev")"; udevadm settle
pvcreate -y "$dev"-part1
vgcreate hdd "$dev"-part1
lvcreate -y -l 95%FREE --thinpool data hdd
pvesm add lvmthin hdd --vgname hdd --thinpool data --content images,rootdir --nodes <node>
```

## 4. Tokens, straight into GitHub

Two tokens per node. Their secrets are shown once; pipe them from the node into
`gh secret set` so they are never printed, pasted or logged. Run on your Mac,
on the lab tailnet. `-n -T` matter: without them, a multi-line command over
Tailscale SSH can leave the pipe open and `gh` waiting forever.

The node key is the node name in upper case with dashes as underscores
(`zima-pve` → `ZIMA_PVE`).

**API token** (OpenTofu, Packer):

```bash
ssh -n -T root@<node>.<tailnet> \
  'pvesh create /access/users/root@pam/token/autolab --privsep 0 --output-format json' \
| python3 -c 'import sys,json; print("root@pam!autolab=" + json.load(sys.stdin)["value"])' \
| gh secret set PROXMOX_API_TOKEN_<KEY> -R megamp15/AUTOLAB
```

**Monitoring token** (read-only; the user **and** the token both need
`PVEAuditor`, see [observability](../gitops/observability.md)):

```bash
ssh -n -T root@<node>.<tailnet> 'set -e
pveum user add pve-exporter@pve --comment "AUTOLAB monitoring, read-only"
pveum acl modify / --users pve-exporter@pve --roles PVEAuditor
t=$(pvesh create /access/users/pve-exporter@pve/token/monitoring --privsep 1 --output-format json)
pveum acl modify / --tokens "pve-exporter@pve!monitoring" --roles PVEAuditor
printf "%s" "$t"' \
| python3 -c 'import sys,json; print(json.load(sys.stdin)["value"])' \
| gh secret set PVE_EXPORTER_TOKEN_SECRET_<KEY> -R megamp15/AUTOLAB
```

If a run dies after the token was created but before `gh` stored it, the secret
is gone: remove the token (`pveum user token remove <user> <tokenid>`) and run
it again; re-run the `acl modify` for a token, since removing it drops its
grant.

**Heartbeat** (optional): a Healthchecks.io check for the node, then
`gh secret set HEALTHCHECKS_PING_URL_<KEY> -R megamp15/AUTOLAB` and paste the
ping URL at the prompt.

Check by name: `gh secret list -R megamp15/AUTOLAB | grep <KEY>`.

## 5. Name it in the repository

One PR (`zima-pve`'s was #215):

| Where | What |
|---|---|
| `builders/ansible/inventories/hypervisors/hosts.yml` | the node under `proxmox_nodes` |
| `builders/ansible/playbooks/proxmox.yml` | its entry in `autolab_pve_backup_by_node`, `enabled: false` until its key is saved; its Wi-Fi interface in `autolab_pve_wifi_by_node` if it has one |
| `.github/workflows/01_…` and `02_…` | the node in the `node` choices |
| `.github/workflows/05_ansible-builder.yml` | `AUTOLAB_PVE_TOKEN_SECRET_<KEY>` (a workflow cannot list secrets) |
| `.github/workflows/07_proxmox-node.yml` | `AUTOLAB_HEARTBEAT_<KEY>` and its line in the heartbeat map |

Monitoring, the homepage's node row and the `<node>.lab.<zone>` route follow
from the inventory with no further change.

## 6. Onboard

CI reaches nodes only as `gitops`: the tailnet policy does not let `tag:ci`
SSH as root (a `bootstrap: true` run fails at once with *tailnet policy does
not permit you to SSH as user "root"*). So the first `gitops` account is made by
hand, exactly as the `gitops-user` role makes it, from your Mac as root over
Tailscale SSH (your admin account may); the role owns it from the first run on.
Proxmox ships without `sudo`:

```bash
ssh -n -T root@<node>.<tailnet> 'set -e
command -v sudo >/dev/null || apt-get install -y sudo
id gitops >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo gitops
printf "gitops ALL=(ALL) NOPASSWD:ALL\n" > /tmp/90-gitops
visudo -cf /tmp/90-gitops && install -m 0440 /tmp/90-gitops /etc/sudoers.d/90-gitops
rm /tmp/90-gitops'
```

(`pve` was onboarded instead with a temporary policy rule letting CI in as
root, #174, reverted in #178. The account by hand needs no policy change.)

After the PR is merged:

1. **07 - Proxmox Node**, limit `<node>`, `bootstrap: false`, `confirm: check`;
   read the diff; then again with `confirm: apply`.
2. **01 - Bootstrap private VM network**, node `<node>`: the `vmbr1`
   `10.42.0.1/24` bridge with NAT that guests use. It runs as `gitops` with
   sudo, so `gitops` must exist first (07 above).
3. **05 observability** picks up the exporter target on its next run.
4. **Pocket ID** → client `proxmox` → add the callback URLs
   `https://<node>.lab.<zone>` with and without the trailing slash.
5. **Backups:** after the first 07 apply, save `/etc/pve/priv/storage/ark.enc`
   in the password manager and R2 (`autolab-keys`), then set the node's
   `enabled: true` in a PR. See [backups](../gitops/backups.md).
6. **Updates:** 07 with `tags=updates` brings Proxmox to the version the other
   nodes run.

## Related

[05-tailscale.md](./05-tailscale.md) · [03 API token](../gitops/03-proxmox-api-token.md) ·
[observability](../gitops/observability.md) · [backups](../gitops/backups.md) ·
[ingress](../gitops/ingress.md)
