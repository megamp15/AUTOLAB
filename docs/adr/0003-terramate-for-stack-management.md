# ADR-0003: Terramate for stack management and code generation

## Status

Accepted

## Context

Autolab needs to manage multiple OpenTofu environments (stacks) with shared provider configuration and backend settings. Without Terramate, each stack would duplicate `providers.tf` and `versions.tf`.

## Decision

Use Terramate for code generation (`_base/*.tm.hcl`) and stack metadata. Generated files (`providers.tf`, `versions.tf`) are never hand-edited. Stack-specific config lives in `stack.tm.hcl` and the stack's own `*.tf` files.

For the first stack, keep `main.tf`, `variables.tf`, and `outputs.tf` hand-written because there is only one concrete stack shape. Provide a reusable stack template so new stacks do not start from memory. Promote stack module wiring to Terramate generation after a second real stack proves the abstraction and the duplicated wiring is stable.

## Consequences

- Adding a new environment starts from `infra/stacks/_template/`, then customizes `stack.tm.hcl` and `terraform.tfvars`.
- Provider and backend config changes are made once in `_base/` and regenerated.
- Stack wiring generation is deliberately deferred until at least two stacks need the same wiring; this avoids freezing a speculative template too early.
- Terramate is a build-time dependency; it must be installed before `tofu init`.
