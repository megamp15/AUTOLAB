# ADR-0001: Schema-driven code generation for connection and network config

## Status

Accepted

## Context

Autolab needs to keep Proxmox connection fields consistent across three consumers: the OpenTofu `proxmox-connection` module, Packer variable definitions, and CI environment variables. Similarly, network env fields must stay consistent between the env file template, bash validation, and the interactive wizard. R2 backend settings must also stay consistent between Terramate backend globals and setup scripts.

Without a single source of truth, adding or changing a field requires editing multiple files by hand — error-prone and easy to miss.

## Decision

Define connection fields in `infra/connection-schema.yaml`, network env fields in `docs/proxmox/config/network-env-schema.yaml`, and R2 backend settings in `infra/r2-config.yaml`. Generator scripts produce adapter files from these schemas:

- `scripts/generate-connection-adapters.sh` renders OpenTofu module variables, stack variables, and Packer connection variables.
- `scripts/generate-network-env-adapters.sh` renders the env example, the full generated bash validation module, and the generated key lists/default application used by bootstrap scripts.
- `scripts/generate-r2-config.sh` renders Terramate R2 globals.

Bootstrap scripts treat the network env schema as the source of truth for field iteration: they walk the generated schema keys instead of keeping separate field lists in shell code. The only intentional sidecar is `/etc/default/proxmox-wifi-extra.list`, which remains a user-managed extra-SSID file outside the main schema-driven env.

CI checks for drift between schemas/config and generated outputs.

## Consequences

- Adding a field or shared config value means editing one YAML file and re-running the generator.
- Generated files must not be hand-edited (they carry AUTO-GENERATED headers).
- Consumer-facing names live in schema rows (`module_var`, `opentofu_var`, `packer_var`, `ci_env`, `ci_source`); generators should be pure renderers, not repositories of per-field case statements.
- CI drift detection (`--check` mode) catches accidental hand-edits to generated files.
