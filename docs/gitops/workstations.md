---
tags: [gitops, workstation, wsl, tailscale]
status: draft
audience: operator
---

# Workstations

A **workstation** is a Linux environment on a machine a person sits at — today
WSL2 Ubuntu on the owner's desktop, `quasar` — that is part of the lab while
that machine is on and simply absent while it is off. It is where editing and
heavy builds happen: it has the desktop's CPU, memory and GPU, which no VM
here can spare.

It is declared in `builders/ansible/inventories/workstations/hosts.yml`,
configured by `playbooks/workstation.yml` through workflow **13 -
Workstation**, and tagged `tag:autolab-ws` on the tailnet.

## How it differs from a VM

| | VM (`tag:autolab-vm`) | workstation (`tag:autolab-ws`) |
|---|---|---|
| created by | OpenTofu | a person, by hand |
| inventory | generated from OpenTofu output, `linux_servers` | committed, `workstations`, **not** in `linux_servers` |
| configured by | `05`, on merge for observability | `13`, dispatched by hand while it is on |
| off | an outage | normal |
| baseline | `harden.yml` | `workstation.yml`: base-linux, gitops-user, admin-users, motd |
| monitored, backed up | yes | no |

Left out of the baseline, on purpose:

- **ssh-hardening, fail2ban** — no sshd listens. Access is Tailscale SSH only.
- **firewall** — WSL2 in its default NAT mode is not reachable from the LAN at
  all, and inbound traffic arrives only on `tailscale0`. ufw inside WSL2 is
  untested here.
- **observability, updates-report** — a host that is off for a day would raise
  "Updates report is stale" and agent alerts every night. Its code lives in git.
- **reboot** — rebooting a WSL distro stops it, and nothing inside it brings it
  back; the desktop's keep-alive task does, at the next logon.

Not in `linux_servers` because `05` deploys observability to `limit=all` on
every merge and fails on any host it cannot reach.

## Access

```sh
ssh pmahi@quasar          # the WSL account: your code is in ~/code
ssh megamp15@quasar       # the lab's operator account
```

VS Code: Remote-SSH to `pmahi@quasar` from another machine; at the desktop
itself, the WSL extension (`code .` in the distro). Both open the same files.

The tailnet policy allows members as `pmahi`, `megamp15` and `gitops` in
check mode (re-authenticate every 12 h), and CI as `gitops` only. Never root.

## Setting one up

On Windows:

1. Install WSL2 and a distribution. Keep the default NAT networking, **not**
   `networkingMode=mirrored`: the distro needs its own interface to be its own
   tailnet node, separate from the Windows host's.
2. Keep it running while you are logged in: a scheduled task, at logon, that
   runs `conhost.exe --headless wsl.exe -d <distro> -u root --exec /bin/sleep infinity`.
   WSL otherwise stops the distro shortly after the last window closes.

In the distro:

3. Install Tailscale with the official script and join, after this policy is
   on main:

   ```sh
   sudo tailscale up --hostname=quasar --ssh --advertise-tags=tag:autolab-ws
   ```

4. Run the first baseline **by hand, on the machine itself**: it creates
   `gitops`, which is the only account CI uses here, so there is no bootstrap
   account to open and close in the policy.

   ```sh
   sudo apt-get install -y ansible-core
   cd ~/code/AUTOLAB/builders/ansible
   ansible-galaxy collection install -r requirements.yml
   ansible-playbook -i inventories/workstations/hosts.yml playbooks/workstation.yml \
     --limit quasar -c local -e ansible_host=localhost -K
   ```

5. From then on: workflow `13`, `confirm=check`, then `apply`, while it is on.

Adding a second workstation is a line in the inventory and steps 1–5.

## The GPU

WSL2 passes the desktop's NVIDIA GPU through: the Windows driver provides
`/usr/lib/wsl/lib/libcuda.so` and `nvidia-smi` in the distro. Do **not**
install a Linux NVIDIA driver inside WSL. For CUDA builds, install only the
CUDA toolkit (the `wsl-ubuntu` repository); for containers, the NVIDIA
Container Toolkit.
