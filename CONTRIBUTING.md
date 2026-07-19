# Contributing to Autolab

Thanks for helping grow this project. It is aimed at **beginners** and **repeatable Proxmox bootstrap** — keep changes clear and tested on a real or VM host when you can.

## Before you open a PR

0. Review the [production-readiness gates](docs/production-readiness.md) that apply to your change and run the relevant checks locally.

1. Run script syntax checks locally:

   ```bash
   find docs/proxmox/scripts -name '*.sh' -exec bash -n {} \;
   ```

2. Do **not** commit secrets (`WPA_*`, real IPs you use at home, auth keys). Use [network.env.example](docs/proxmox/config/network.env.example) placeholders only.

3. Match doc frontmatter: `tags`, `status` (`alpha` | `draft` | `stable`), `audience`.

4. **Schema-driven config:** Make changes to the schema YAML files (not generated outputs):
   - Connection schema → [`infra/connection-schema.yaml`](infra/connection-schema.yaml)
   - Packer template schema → [`infra/packer/template-schema.yaml`](infra/packer/template-schema.yaml)
   - Network env schema → [`docs/proxmox/config/network-env-schema.yaml`](docs/proxmox/config/network-env-schema.yaml)
   - R2 backend config → [`infra/r2-config.yaml`](infra/r2-config.yaml)

   After editing a schema YAML, regenerate the adapter files with the corresponding generator script:
   ```bash
   bash scripts/generate-connection-adapters.sh     # OpenTofu, Packer connection, CI connection action
   bash scripts/generate-packer-template-adapters.sh # Packer template CI action
   bash scripts/generate-network-env-adapters.sh    # network.env.example + bash validation
   bash scripts/generate-r2-config.sh               # Terramate R2 defaults
   ```

## Branch and commits

- One logical change per PR when possible (scripts vs docs).
- Commit messages: what changed and **why** (e.g. “quote failover env vars — fixes source errors with special chars”).

## Docs style

- Full paths on first mention: `/etc/default/proxmox-network.env`, `/root/proxmox-setup/scripts/`.
- Say **bootstrap** vs **GitOps** using [docs/ROADMAP.md](docs/ROADMAP.md) terminology.
- Examples use placeholder subnets (`192.168.1.x`), not your home network.

## Reporting issues

Include: PVE version (`pveversion -v`), output of `ip -br link`, whether USB Ethernet was plugged in, and redact Wi‑Fi passwords.
