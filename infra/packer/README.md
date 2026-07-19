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

## Before the first build

The Debian template is ready to test once these operator-owned values exist:

1. Proxmox can reach the pinned installer URL and download it directly to the
   `local` storage pool:
   `https://cdimage.debian.org/debian-cd/13.6.0/amd64/iso-cd/debian-13.6.0-amd64-netinst.iso`.
2. GitHub repository variables describe the Proxmox node:
   `PROXMOX_HOST`, `PROXMOX_ENDPOINT`, `PROXMOX_NODE_NAME`, `PROXMOX_STORAGE_POOL`,
   `PROXMOX_NETWORK_BRIDGE`, `PACKER_ISO_URL`, `PACKER_ISO_CHECKSUM`, and
   `SSH_PUBLIC_KEYS`.
3. GitHub repository secrets provide credentials:
   `TAILSCALE_OAUTH_CLIENT_ID`, `TAILSCALE_OAUTH_SECRET`,
   `PROXMOX_API_TOKEN`, and `PACKER_SSH_PASSWORD`.

`PACKER_SSH_PASSWORD` is not an SSH key you generate. It is a temporary
installer password used only while Packer connects to the build VM during the
image build. The template locks the temporary account before converting the VM
to a reusable template. Use a generated random password for GitHub; it does not
need to match your Proxmox root password or laptop SSH key.

## Layout

```text
infra/packer/
├── README.md                  # this file
├── template-schema.yaml       # Packer template CI vocabulary
└── templates/
    └── debian-13/
        ├── connection-vars.pkr.hcl   # generated Proxmox connection variables
        ├── template-vars.pkr.hcl     # Debian-specific variables
        ├── debian-13.pkr.hcl         # Debian 13 cloud-init template build
        ├── debian-13-preseed.cfg.tpl # preseed template for automated install
        └── debian-13.pkrvars.example # example overrides
```

The Packer template catalog lives in `template-catalog.yaml`. Only entries with
`status: implemented` are buildable. Disposable experiment ideas stay in the same
catalog under `experiments` and in `docs/gitops/template-lab-matrix.md` until
they are promoted.

`scripts/resolve-packer-template.sh` resolves implemented catalog entries to
the Packer directory, template file, Proxmox template identity, and CI metadata.

The Packer CI setup seam is `.github/actions/setup-packer-pipeline`. It resolves
the catalog entry, joins Tailscale, emits Connection variables for Packer, emits
template-specific variables, and installs Packer before the workflow runs
`packer init`, `packer validate`, and `packer build`.

Environment-specific variable files (`.pkrvars.hcl`) are **not committed** —
they contain secrets like API tokens. Copy the `.example` file and fill in your
values:

```bash
cp infra/packer/templates/debian-13/debian-13.pkrvars.example infra/packer/templates/debian-13/debian-13.pkrvars.hcl
# edit infra/packer/templates/debian-13/debian-13.pkrvars.hcl with your values
cd infra/packer/templates/debian-13
packer init .
packer validate -var-file=debian-13.pkrvars.hcl .
packer build -var-file=debian-13.pkrvars.hcl .
```

## Configurable variables

Connection variables are **auto-generated** from `infra/connection-schema.yaml` by `scripts/generate-connection-adapters.sh`. They live in each implemented template directory as `connection-vars.pkr.hcl` — do not edit those files manually.

Template-specific Packer variables are **hand-maintained** in each template directory's `template-vars.pkr.hcl`. Their GitHub CI vocabulary is defined in `template-schema.yaml` and rendered to `.github/actions/configure-packer-template/action.yml` by `scripts/generate-packer-template-adapters.sh`. Override values via `.pkrvars.hcl` files, `PKR_VAR_` environment variables, or GitHub vars/secrets in CI.

For now, `template-schema.yaml` generates only the `configure-packer-template` adapter. The `setup-packer-pipeline` inputs and the `packer-build.yml` `with:` block still forward those values manually. That is intentional while Autolab has one Packer template; generate that forwarding only after adding another template or after variable churn proves the manual forwarding is causing drift.

| Variable | Default | Secret? | Description |
|---|---|---|---|
| `proxmox_endpoint` | — | No | Proxmox API URL |
| `proxmox_api_token` | — | Yes | Proxmox API token in `USER@REALM!TOKENID=TOKEN_SECRET` format; the Packer template splits it for plugin auth |
| `proxmox_node_name` | — | No | Proxmox node name |
| `proxmox_insecure_tls` | `true` | No | Skip TLS verification |
| `storage_pool` | `local-lvm` | No | Storage pool for VM disks |
| `cloud_init_storage_pool` | `null` (defaults to `storage_pool`) | No | Separate pool for cloud-init drive |
| `iso_url` | `https://cdimage.debian.org/debian-cd/13.6.0/amd64/iso-cd/debian-13.6.0-amd64-netinst.iso` | No | Pinned URL for the installer ISO |
| `iso_checksum` | `sha256:65273beed27b2df543b68b65630ba525cfbad8df2b12035732b2dff87d6664e7` | No | ISO checksum (e.g. `sha256:abc...`) |
| `boot_iso_type` | `scsi` | No | Packer boot ISO device type (`scsi`, `ide`, `sata`, `virtio`) |
| `ssh_password` | `packer` | Yes | Temporary build-only SSH password for provisioning |
| `network_bridge` | `vmbr0` | No | Proxmox bridge for build VM |
| `vm_template_name` | `autolab-debian-13-template` | No | Template name |
| `vm_id_base` | `9000` | No | Starting VM ID |
| `ssh_public_keys` | `[]` | No | SSH keys to inject |

The pinned ISO is downloaded by PVE and is retained deliberately for rollback;
Autolab never auto-deletes old ISO files. Build and test a new template
separately before switching VM definitions to it.

### GitHub CI variables and secrets

In the Packer workflow, these map to GitHub repository variables and secrets:

| Packer variable | GitHub type | GitHub name |
|---|---|---|
| `proxmox_endpoint` | Variable | `PROXMOX_ENDPOINT` |
| `proxmox_api_token` | Secret | `PROXMOX_API_TOKEN` |
| `ssh_password` | Secret | `PACKER_SSH_PASSWORD` |
| `proxmox_node_name` | Variable | `PROXMOX_NODE_NAME` |
| `proxmox_insecure_tls` | Variable | `PROXMOX_INSECURE_TLS` |
| `storage_pool` | Variable | `PROXMOX_STORAGE_POOL` |
| `cloud_init_storage_pool` | Variable | `PROXMOX_CLOUD_INIT_STORAGE_POOL` |
| `iso_url` | Variable | `PACKER_ISO_URL` |
| `iso_checksum` | Variable | `PACKER_ISO_CHECKSUM` |
| `network_bridge` | Variable | `PROXMOX_NETWORK_BRIDGE` |
| `ssh_public_keys` | Variable | `SSH_PUBLIC_KEYS` |

## Adding new templates

See [docs/gitops/template-lab-matrix.md](../../docs/gitops/template-lab-matrix.md)
for the disposable experiment menu and [template-catalog.yaml](./template-catalog.yaml)
for implemented templates plus documented experiment targets.

Add a new directory under `infra/packer/templates/` for each implemented OS
template (for example `templates/ubuntu-24.04/`). Each template owns its Packer
implementation, installer automation, `template-vars.pkr.hcl`, and example
`.pkrvars.hcl` file.

Then promote the template in `template-catalog.yaml` with `status: implemented`
so CI callers can resolve it through `scripts/resolve-packer-template.sh`.

The current checked-in build is Debian-specific because it uses Debian preseed.
Ubuntu Server uses Subiquity autoinstall instead, so Ubuntu support should be a
separate template implementation rather than a catalog alias for `debian-13`.
The workflow resolves one implemented template and runs Packer only inside that
template directory.

Talos is a cluster OS target, not a normal cloud-init server template. Start it
as an OpenTofu plus `talosctl` path using Talos Image Factory assets before
deciding whether Packer adds value.

## Deferred enhancements

Stop here until real use proves more depth is needed:

- Generate `setup-packer-pipeline` inputs and workflow forwarding from `template-schema.yaml` only if adding template variables becomes repetitive.
- Expand `template-schema.yaml` to cover all per-template `template-vars.pkr.hcl` files only when a second template needs different build defaults.
- Keep Stack wiring hand-written until a second real Stack proves the shape, per ADR-0003.
