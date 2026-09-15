---
tags: [gitops, observability, grafana, prometheus, loki, alloy, proxmox]
status: draft
audience: operator
---

# Observability

Every Builder host runs a collection agent; one host runs the backends it
reports to. Which host is decided by machine policy, not by hostname.

## At a glance

```mermaid
flowchart LR
    subgraph hosts["every Builder host"]
        A1["Grafana Alloy<br/><small>metrics + logs</small>"]
    end
    subgraph stack["jwst · observability.stack = true"]
        P["Prometheus<br/><small>local disk</small>"]
        L["Loki<br/><small>local disk</small>"]
        G["Grafana<br/><small>dashboards from git</small>"]
        X["pve-exporter<br/><small>scrapes the Proxmox API</small>"]
    end
    A1 -- "remote_write" --> P
    A1 -- "push" --> L
    X --> P
    P --> G
    L --> G
    P -. "snapshot" .-> N["NAS<br/><small>durable copy</small>"]
    PVE["Proxmox API"] --> X
```

Grafana is reached over the tailnet at `http://<stack-host>:3000`. Nothing is
published to the LAN.

## Why Alloy

[Grafana Alloy](https://grafana.com/docs/alloy/latest/) is a **distribution of
the OpenTelemetry Collector**, not an alternative to it. It wraps upstream
Collector components and adds native Prometheus scrape and service discovery,
which matters because every exporter here is Prometheus-native.

One agent covers metrics, logs, traces and profiles. Tempo and Pyroscope later
are a config addition to this agent, not a re-architecture — which is why the
collection layer was settled before choosing backends.

It also embeds the node exporter, so there is no second package to install or
keep current.

## Why Prometheus and not Mimir

Mimir **requires object storage**. The NAS is the primary storage point and R2
is reserved for the irreplaceable minimum, so running Mimir would mean running
MinIO purely to back a metrics database. Its scale and multi-tenancy solve
problems two VMs do not have.

Metrics stay on **local disk**. A TSDB does heavy random I/O with `mmap` and
file locking; Prometheus documents non-POSIX filesystems as unsupported and a
possible cause of unrecoverable corruption, so the NAS holds *snapshots* rather
than the live database. Snapshots are taken through the admin API — rsyncing a
live TSDB captures half-written blocks and restores to corruption.

If retention ever outgrows local disk, that is the point where MinIO plus Mimir
starts earning its complexity. Because Alloy does the collecting either way,
that migration is a config change.

## Enabling it on a machine

Agents install everywhere automatically. The backends follow machine policy in
`infra/stacks/lab/machines.auto.tfvars`:

```hcl
builder = {
  docker_enabled = true
  observability = {
    stack = true
  }
}
```

Then run workflow **05 - Ansible Builder** with `playbook: observability`.
Use `confirm: check` first.

The stack needs Docker, so `docker_enabled` must be true on the same machine;
the role asserts this rather than failing obscurely later.

## The Proxmox read-only token

Host and guest metrics come from the agents. **Hypervisor** metrics — per-VM
usage as Proxmox accounts it, storage pools, cluster state, backup job status —
come from `prometheus-pve-exporter`, which scrapes the Proxmox **API**. It runs
on the stack host; nothing is installed on Proxmox.

That last category is the gap worth closing: without it, a VM that is powered
off and an agent that has crashed look identical, because both simply stop
reporting.

### Why not reuse `PROXMOX_API_TOKEN`

That token creates and destroys VMs — OpenTofu uses it to do exactly that. Two
reasons to keep the exporter separate:

- **Different lifetimes.** The OpenTofu token exists for the seconds a workflow
  runs. The exporter's sits on disk in a long-running container indefinitely.
- **Different lifecycles.** Rotating or narrowing the OpenTofu token would
  silently break monitoring, and the failure would look like a broken exporter
  rather than a rotated credential.

The exporter is not network-exposed — only Prometheus reaches it, inside the
compose network — so this is defence in depth rather than a live hole. It also
costs about three minutes.

### Create it

On the Proxmox host:

```bash
# 1. A user that exists only to be read from
pveum user add pve-exporter@pve

# 2. A token under it. Prints the secret once — copy it now.
pveum user token add pve-exporter@pve monitoring --privsep 1

# 3. Read-only across the datacenter — BOTH the user and the token
pveum acl modify / --users  'pve-exporter@pve'            --roles PVEAuditor
pveum acl modify / --tokens 'pve-exporter@pve!monitoring' --roles PVEAuditor
```

**Both grants are required, and this is the step that will waste your
afternoon.** With `--privsep 1` a token's effective permissions are the
*intersection* of the user's and the token's. Granting only the token leaves
that intersection empty, so the token authenticates successfully and is then
denied everything:

```
403 Forbidden: Permission check failed (/, Sys.Audit)
```

The ACL looks correct in `pveum acl list` while this is happening, which is what
makes it confusing — the grant is real, it is just being intersected with
nothing.

Privilege separation is still worth keeping. It means the token can never exceed
the user, so narrowing the user later narrows the token automatically. The
alternative, `--privsep 0`, makes the token inherit everything the user has —
exactly the property worth avoiding.

`PVEAuditor` is Proxmox's built-in read-only role: it lists and reads every
node, VM, storage pool and backup job, and changes nothing.

Through the UI instead, all three under **Datacenter → Permissions**:

| Screen | Action |
|---|---|
| **Users** → Add | User name `pve-exporter`, realm `Proxmox VE authentication server`. The form requires a password; token auth ignores it. |
| **API Tokens** → Add | User `pve-exporter@pve`, Token ID `monitoring`, **leave Privilege Separation checked**. Copy the secret. |
| **Permissions** → Add → *User Permission* | Path `/`, user `pve-exporter@pve`, role `PVEAuditor`, Propagate checked |
| **Permissions** → Add → *API Token Permission* | Path `/`, token `pve-exporter@pve!monitoring`, role `PVEAuditor`, Propagate checked |

Both rows, for the intersection reason above.

### Verify it is actually read-only

Check the grant rather than trusting the role name:

```bash
pveum acl list
```

Two lines on `/` with `PVEAuditor` — one `type: user`, one `type: token`. One
alone is not enough; see the intersection rule above.

Then confirm the token resolves to actual permissions rather than an empty set:

```bash
curl -sk -H "Authorization: PVEAPIToken=pve-exporter@pve!monitoring=SECRET" \
  https://<pve-host>:8006/api2/json/access/permissions
```

`{"data":{}}` means the intersection is empty — the user grant is missing.
A populated object listing `Sys.Audit`, `VM.Audit` and friends is correct.

`/nodes` is a poor test here: Proxmox filters that endpoint by permission rather
than denying it, so it returns HTTP 200 with a plausible-looking body even when
the token can see nothing.

### Where the values go

| Name | Kind | Value |
|---|---|---|
| `PVE_EXPORTER_TOKEN_ID` | **variable** | `pve-exporter@pve!monitoring` |
| `PVE_EXPORTER_TOKEN_SECRET` | **secret** | the UUID from step 2 |

The ID is a **variable**, not a secret: it is an identifier, and knowing it
grants nothing without the secret. Secrets are also masked in run logs, so
storing an identifier as one means a failed authentication shows `***` exactly
where you need to see which token was used.

`PROXMOX_HOST` is reused as the scrape target; no new variable is needed.

Leaving these unset is supported — the exporter container is omitted rather
than shipped broken, and everything else works.

## How the secret reaches the host

Workflow 05 renders the values into a `0600` JSON file and passes it with
`--extra-vars @file`. Deliberately not inline: `--extra-vars` on the command
line lands in the runner's process list, and shell interpolation risks the value
reaching the run log. The file is written by Python from environment variables,
so no secret is ever part of a shell string, and removed in an `always()` step.

On the host the token lands in `/opt/autolab/observability/pve.yml` at mode
`0600`, mounted read-only into the container — rather than an environment
variable, which would be visible in `docker inspect` and the container's
process list.

## Dashboards as code

Dashboards live in `roles/observability-stack/files/dashboards/` and are
provisioned with `allowUiUpdates: false`. A dashboard clicked into a container
volume is one disk failure from gone, and cannot be reviewed.

Editing one in the UI would drift from git and be reverted on the next run, so
the provider locks it and says so.

## Network exposure

Container ports bind to the **tailnet address only**, discovered at deploy time.
This is not merely belt-and-braces: Docker writes its own iptables rules ahead
of ufw's, so a port published on `0.0.0.0` is reachable from the LAN **despite**
the baseline's default-deny firewall.

Grafana allows anonymous viewing, which is deliberate — reaching it at all
already required passing the tailnet SSH/ACL policy, and a second password to
lose helps nobody in a single-operator lab. Editing still requires a login.

## Things that will mislead you

**Agents must start after the backends.** `prometheus.remote_write` retries
indefinitely and recovers on its own; `loki.write` gives up — *"no retries left,
dropping data"* — and does not resume when the backend appears later. The
failure is asymmetric, so metrics look healthy while logs are silently absent.
The playbook runs the stack play first and waits for both backends to report
ready.

**`cache_valid_time` can skip the refresh you just needed.** It means "skip the
update if the cache is younger than this", and `harden.yml` refreshes the cache
minutes earlier in a normal run. A repository added immediately before a package
install is therefore never fetched, and the package appears not to exist. After
adding a repository the refresh has to be unconditional.

**`docker.io` ships no Compose.** Debian packages Compose v2 separately as
`docker-compose`, installed at the CLI plugin path. Without it
`community.docker.docker_compose_v2` refuses to run at all.

**A Proxmox token can authenticate and still be denied everything.** With
privilege separation its permissions are the intersection of the user's and the
token's, so granting only the token yields an empty set. The failure is
`403 Sys.Audit` while `pveum acl list` shows a correct-looking grant. Check
`/access/permissions` — `{"data":{}}` is the tell.

**`apt_repository` needs gpg.** It shells out to `gpg` or `apt-key`, neither
present on a minimal Debian 13 image, and `apt-key` is removed from Debian
entirely. `deb822_repository` writes the sources file directly and is the native
format on this release.

## Related docs

- [NAS storage](./nas-storage.md) — where snapshots land
- [Naming](./naming.md) — why the stack host is called `jwst`
- [GitHub secrets & variables](./github-secrets-variables-reference.md)
