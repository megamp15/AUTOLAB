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
| aurora | Authenticated Hawser on its tailnet address | Workflow 05, environment `edge`, playbook `docker-management` |

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

## Tags

Every container the repository deploys carries a `dockhand.tags` label, so
**Group by tag** on the Containers page puts what belongs together in one
band. The tag names what the container is part of:

| tag | containers |
| --- | --- |
| the app's name (`cosmos`, `sure`, `forgejo`, ...) | an app and its own database, worker, cache or search |
| `qr` | `qr`, `qr-public` and the tunnel connector that reaches it |
| `home` | the home page, its API, dash |
| `observability` | Prometheus, Loki, Tempo, Grafana, exporters, cAdvisor, Alloy |
| `docker` | Dockhand and its proxy, Hawser, the registry and its UI, Diun |
| `ingress` | Traefik, Pocket ID, the lab's tunnel connector |
| `dns` | Pi-hole |
| `immich` | Immich's four containers, the photo jobs, the public share proxy |

The label is in each service's compose template. A tag added by hand in
Dockhand stays in Dockhand's own database and is not in the repository.
A label reaches a container when it is recreated. Workflow 12's `adopt`
writes Immich's compose file and never recreates, so Immich's own containers
take their tag at the next `docker compose up -d` in its directory, an
upgrade for instance.

## Health

Every container has a healthcheck, so the Health column says something for
each row. Where the image has a client, the check is a request to the app's
own health path. An nginx that only proxies is checked for its listener, so a
sick upstream does not show as two sick containers. The tunnel connectors ask
`cloudflared tunnel ready`, which is true only while the tunnel is connected.

Two have none: `rustdesk-hbbs` and `rustdesk-hbbr`. Their image has no shell
and no client to probe with. Tempo's image is the same; it is off by default.

## Registry

The AUTOLAB connection uses the existing Distribution registry at
<https://registry.lab.pmahir.space>. Registry UI and Dockhand browse the same
backend. Dockhand does not create another image store. AUTOLAB is the default
registry connection; Docker Hub remains available in the selector. An empty
catalog means this private registry currently has no repositories.

The shared `dockhand-environment` role registers each engine and checks registry
connectivity and catalog browsing through the protected manager API. Tokens
remain on the hosts and are hidden from Ansible output.
