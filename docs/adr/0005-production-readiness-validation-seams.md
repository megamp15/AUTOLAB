# ADR-0005: Production-readiness validation seams

## Status

Accepted

## Context

Autolab is moving from alpha scaffold toward real use on a Proxmox host. Several production paths had behaviour that only failed at runtime:

- Apply retry behaviour lived only inside `scripts/tofu-apply-with-retry.sh`.
- Tailscale enrollment for cloud-init VMs was an opaque shell string.
- R2 token setup passed credentials through text lines parsed with `grep` and `sed`.
- Schema generators were checked for drift, but generated adapters were not semantically validated by their consumers.

These are all places where the interface is the test surface: if CI or scripts can only test inside the implementation, bugs move to the host, VM boot, or apply workflow.

## Decision

Deepen the production seams that already have more than one caller or one operational failure mode:

- Keep retry behaviour in `scripts/lib/retry.sh` and have `tofu-apply-with-retry.sh` use it.
- Keep Tailscale install, join, retry, and logging composition inside the `cloud-init` module while preserving the existing `tailscale_auth_key` caller path.
- Use structured JSON output from `r2-create-token.sh` for automation; keep text output as the human adapter.
- Add semantic validation in CI after drift checks so generated OpenTofu and Packer adapters are parsed by their real consumers.
- Keep `proxmox-connection` aligned with ADR-0002: validation-only, with the Connection schema as the field source of truth.

## Consequences

- Apply retry behaviour is testable without OpenTofu by using fake commands in bats.
- VM Tailscale enrollment remains configurable without exposing command-building details to every Stack.
- R2 Backend setup no longer depends on human text formatting for credentials.
- CI catches schema-to-adapter translation failures, not just stale generated files.
- Future architecture reviews should not re-suggest removing `proxmox-connection` solely because it is shallow; ADR-0002 already accepts that trade-off unless the module stops providing validation or derived values.
