# Autolab Ansible Builder

Phase 2C configures Linux hosts after they exist. Current Builder targets are
cloud-init-capable Proxmox VMs. LXC Builder targets are deferred until they
meet the same reachable-host contract; future provider-neutral reachable Linux
hosts, including VPS hosts, remain intended. Once SSH is reachable, the builder
should apply the same server baseline.

## Scope

This scaffold is intentionally provider-neutral:

- Proxmox-specific work stays in `docs/proxmox/`, `infra/stacks/`, and
  `infra/packer/`.
- VPS-specific work belongs in future provider stacks under `infra/`.
- Shared Linux configuration belongs here as Ansible roles.

## Layout

```text
builders/ansible/
  ansible.cfg
  inventories/
    lab/
      hosts.example.yml
    vps/
      hosts.example.yml
  playbooks/
    harden.yml
  roles/
    base-linux/
    ssh-hardening/
    firewall/
    tailscale/
    gitops-user/
    docker-host/
```

## First run

Copy an example inventory and replace the placeholder host values:

```bash
cd builders/ansible
cp inventories/lab/hosts.example.yml inventories/lab/hosts.yml
ansible-playbook -i inventories/lab/hosts.yml playbooks/harden.yml --check
```

Do not commit real inventories with public IPs, private hostnames, usernames, or
secrets unless they are intentionally public.

## Baseline contract

The `harden.yml` playbook is the common baseline every managed server should
eventually receive:

- package cache refresh and security update policy
- non-root admin user
- separate `gitops` deploy user
- root/password SSH disabled
- firewall defaults
- Tailscale/private management access (VM install, join, and retry are owned by cloud-init)
- optional Docker runtime

Role tasks are placeholders until each role is implemented and tested. Keep each
role idempotent and safe to run repeatedly. A future Tailscale role may only add
post-join policy or configuration if it earns a real need.
