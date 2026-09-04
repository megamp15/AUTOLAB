## Summary

<!-- What changed and why. Link the issue if there is one. -->

## Layer

<!-- Bootstrap / Provision / Template / Configure / CI / Docs -->

## Checklist

- [ ] `bash -n` passes for changed scripts
- [ ] `bash scripts/check-schema-drift.sh` passes (if a schema YAML or generated adapter changed, the generator was re-run and its output committed)
- [ ] `tofu fmt -check -recursive infra` and `tofu validate` pass (if infra changed)
- [ ] `bats docs/proxmox/scripts/tests/` passes
- [ ] No secrets, real IPs, or auth keys; examples use placeholders
- [ ] Docs updated where behaviour changed (guide, README, CONTEXT.md, or an ADR for architecture decisions)

## Testing

<!-- What you ran, and against what: local checks only, a dry-run on a host, a manual workflow dispatch (link the run), or a real Proxmox host. -->
