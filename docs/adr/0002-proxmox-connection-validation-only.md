# ADR-0002: Proxmox connection module is validation-only

## Status

Accepted

## Context

The `proxmox-connection` OpenTofu module validates connection parameters and provides derived values (normalised endpoint, web UI URL). However, the OpenTofu provider block cannot reference module outputs — it must read from `var.proxmox_*` directly. This means connection variables are declared in both the stack's `variables.tf` and the module's `variables.tf`, with different names.

## Decision

Accept the duplication as a Terraform/OpenTofu limitation. The module provides plan-time validation and derived values; the provider block reads from stack-level variables directly. Generate the stack's connection variables from the connection schema to make the duplication automatic and harmless.

## Consequences

- The `proxmox-connection` module is shallow by necessity — its interface is nearly as wide as its implementation.
- Stack connection variables are generated from the schema, so the duplication is automatic and drift-free.
- The module still provides value: validation regexes, normalised endpoint, and a single module call for compute modules to consume.