# Packer for Autolab — VM template automation

This is **phase 2B**: automating VM template creation with [Packer](https://www.packer.io/).

## How it works

Packer builds VM templates from an ISO on your **running Proxmox host**. There is no chicken-and-egg problem — Proxmox is already running (phase 1), so Packer can connect to it via the API and build templates at any time.

The flow is:

1. Proxmox is running and accessible (phase 1 — already done)
2. Packer connects to the Proxmox API over Tailscale
3. Packer boots a VM from an ISO, provisions it, and converts it to a template
4. OpenTofu creates VMs from that template

You can also create a template manually as a quick start (see `docs/gitops/04-opentofu-vm-lxc.md`), but Packer is the recommended approach for reproducible, version-controlled templates.

## How Packer connects to Proxmox

Packer uses the HashiCorp Proxmox Packer plugin
and connects to the Proxmox API over Tailscale (same network as OpenTofu).

Your `proxmox_endpoint` should use the Tailscale MagicDNS name or Tailscale IP
of the Proxmox host, e.g. `https://pve.example.ts.net:8006`.

The Packer connection variables mirror the `proxmox-connection` OpenTofu module
so that both tools share the same conceptual schema for "how we connect to Proxmox".
The schema stores the Proxmox token as `USER@REALM!TOKENID=TOKEN_SECRET`;
the Packer template splits that value into the `username` and `token` fields
required by the Proxmox Packer plugin.

## Layout

```text
infra/packer/
├── README.md                  # this file
├── connection-vars.pkr.hcl   # Proxmox connection variables (generated from schema)
├── template-vars.pkr.hcl     # Template-specific variables (hand-maintained)
├── debian-12.pkr.hcl         # Debian 12 cloud-init template build
├── debian-12-preseed.cfg.tpl # preseed template for automated install
└── debian-12.pkrvars.example # example variable overrides (copy to .pkrvars.hcl)
```

The Packer template catalog seam is `scripts/resolve-packer-template.sh`.
Callers choose a template name such as `debian-12`; the script owns the mapping
to the Packer directory, template file, and description used by CI.

Environment-specific variable files (`.pkrvars.hcl`) are **not committed** —
they contain secrets like API tokens. Copy the `.example` file and fill in your
values:

```bash
cp infra/packer/debian-12.pkrvars.example infra/packer/debian-12.pkrvars.hcl
# edit infra/packer/debian-12.pkrvars.hcl with your values
cd infra/packer
packer init .
packer validate -var-file=debian-12.pkrvars.hcl .
packer build -var-file=debian-12.pkrvars.hcl .
```

## Configurable variables

Connection variables are **auto-generated** from `infra/connection-schema.yaml` by `scripts/generate-connection-adapters.sh`. They live in `connection-vars.pkr.hcl` — do not edit that file manually.

Template-specific variables are **hand-maintained** in `template-vars.pkr.hcl`. Override them via `.pkrvars.hcl` files, `PKR_VAR_` environment variables, or GitHub vars/secrets in CI.

| Variable | Default | Secret? | Description |
|---|---|---|---|
| `proxmox_endpoint` | — | Yes | Proxmox API URL |
| `proxmox_api_token` | — | Yes | Proxmox API token in `USER@REALM!TOKENID=TOKEN_SECRET` format; the Packer template splits it for plugin auth |
| `proxmox_node_name` | — | No | Proxmox node name |
| `proxmox_insecure_tls` | `true` | No | Skip TLS verification |
| `storage_pool` | `local-lvm` | No | Storage pool for VM disks |
| `cloud_init_storage_pool` | `null` (defaults to `storage_pool`) | No | Separate pool for cloud-init drive |
| `iso_file` | `local:iso/debian-12.8.0-amd64-netinst.iso` | No | Proxmox ISO storage path |
| `iso_checksum` | `""` (skip verification) | No | ISO checksum (e.g. `sha256:abc...`) |
| `boot_iso_type` | `scsi` | No | Packer boot ISO device type (`scsi`, `ide`, `sata`, `virtio`) |
| `ssh_password` | `packer` | Yes | Temporary SSH password for provisioning |
| `network_bridge` | `vmbr0` | No | Proxmox bridge for build VM |
| `vm_template_name` | `autolab-debian-12-template` | No | Template name |
| `vm_id_base` | `9000` | No | Starting VM ID |
| `ssh_public_keys` | `[]` | No | SSH keys to inject |

### GitHub CI variables and secrets

In the Packer workflow, these map to GitHub repository variables and secrets:

| Packer variable | GitHub type | GitHub name |
|---|---|---|
| `proxmox_endpoint` | Secret | `PROXMOX_ENDPOINT` |
| `proxmox_api_token` | Secret | `PROXMOX_API_TOKEN` |
| `ssh_password` | Secret | `PACKER_SSH_PASSWORD` |
| `proxmox_node_name` | Variable | `PROXMOX_NODE_NAME` |
| `proxmox_insecure_tls` | Variable | `PROXMOX_INSECURE_TLS` |
| `storage_pool` | Variable | `PROXMOX_STORAGE_POOL` |
| `cloud_init_storage_pool` | Variable | `PROXMOX_CLOUD_INIT_STORAGE_POOL` |
| `iso_file` | Variable | `PACKER_ISO_FILE` |
| `iso_checksum` | Variable | `PACKER_ISO_CHECKSUM` |
| `network_bridge` | Variable | `PROXMOX_NETWORK_BRIDGE` |
| `ssh_public_keys` | Variable | `SSH_PUBLIC_KEYS` |

## Adding new templates

Add a new `.pkr.hcl` file for each OS variant (e.g. `ubuntu-24.04.pkr.hcl`).
Share connection variables through `connection-vars.pkr.hcl` (generated) and template-specific variables through `template-vars.pkr.hcl`. Override with environment
variable files as needed.

Then add the template name to `scripts/resolve-packer-template.sh` so CI callers
do not need to know template file paths.
