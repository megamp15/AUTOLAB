# Central Docker management

Dockhand runs on JWST at <https://dockhand.lab.pmahir.space>. Pocket ID
protects the UI through the private ingress. It can manage containers, Compose
stacks, images, networks and volumes on each registered Docker engine.
Proxmox continues to own VM creation, VM power and snapshots. Terraform and
Ansible remain the source of truth for AUTOLAB configuration.

| Host | Connection | Provisioning |
| --- | --- | --- |
| jwst | Existing local Docker socket | Central Dockhand service |
| singularity | Authenticated Hawser on its tailnet address | Workflow 12, action `management` |
| horizon | Authenticated Hawser on its tailnet address | Workflow 05, environment `lab`, playbook `docker-management` |
| magnetosphere | Authenticated Hawser on its tailnet address | Workflow 05, environment `edge`, playbook `docker-management` |
| nebula | Authenticated Hawser on its tailnet address | Workflow 05, environment `edge`, playbook `docker-management` |

Run the workflow with confirmation `apply` and the corresponding hostname as
its limit. The VM playbook requires an existing Docker engine and the machine's
`builder.docker_enabled` declaration. It skips JWST and jump-host-managed
machines, and rejects tenant environments. Tenant application management stays
on the tenant's own management plane.

The agent is an isolated Compose project at `/opt/autolab/docker-agent` on VMs
and `/volume1/docker/autolab-management` on Singularity. Each host generates its
own protected token once. Only that host's tailnet address publishes port 2376;
anonymous Docker API requests must return 401. Registration is tested through
Dockhand before the play succeeds. Application projects are not redeployed by
this playbook. Immich's external media mount stays read-only.

## Registry

The AUTOLAB connection uses the existing Distribution registry at
<https://registry.lab.pmahir.space>. Registry UI and Dockhand browse the same
backend. Dockhand does not create another image store. AUTOLAB is the default
registry connection; Docker Hub remains available in the selector. An empty
catalog means this private registry currently has no repositories.

The shared `dockhand-environment` role registers each engine and checks registry
connectivity and catalog browsing through the protected manager API. Tokens
remain on the hosts and are hidden from Ansible output.
