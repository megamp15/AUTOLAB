# ADR-0004: Bash for bootstrap-phase scripts

## Status

Accepted

## Context

Bootstrap scripts run on a fresh Proxmox host with minimal tooling. Python, Ansible, or other runtimes cannot be assumed. Bash is universally available and requires no installation.

## Decision

Write bootstrap scripts in bash. Extract pure functions into `lib/` for testability. Use `bats` for unit tests of pure functions. The top-level orchestration scripts (`setup-proxmox-network.sh`, `configure-proxmox-network-env.sh`) provide a `--dry-run` flag for testing without side effects.

## Consequences

- Bootstrap scripts have no runtime dependencies beyond what Proxmox provides.
- Pure functions in `lib/` are testable with `bats`. Runtime daemons may source shared `lib/` functions installed alongside them; self-containment applies to the bootstrap script bundle, not to duplicating library functions inside every file.
- Orchestration scripts are harder to test; `--dry-run` mode provides a partial test surface.
- Bash is not ideal for complex logic; when scripts grow beyond ~200 lines, consider extracting logic into pure functions.
