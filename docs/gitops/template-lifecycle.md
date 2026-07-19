---
tags: [gitops, packer, opentofu, proxmox, lifecycle]
status: draft
audience: maintainer
---

# GitOps template lifecycle

This is the agreed target lifecycle for Autolab's templates and machines. It is
a phased implementation plan, not a second stack architecture.

## Goal and operating rules

- All desired configuration and machine inventory are versioned in git.
- OpenTofu remote state is stored in Cloudflare R2.
- GitHub Actions is the sole writer for normal operation: it runs Packer and
  OpenTofu through protected, reviewable workflows.
- Operators do not run local `tofu apply` or `tofu destroy` for normal
  operation. Local commands remain useful for validation and investigation.
- Bootstrap is still an explicit pre-GitOps phase. A Proxmox host must have
  working networking and Tailscale access before Actions can operate it.

The migration moves machine intent from local-only inputs into reviewed git
configuration while keeping credentials outside the repository.

## Environments and their purpose

| Environment | Lifetime | Purpose | Destruction rule |
|---|---|---|---|
| `template-validation` | Ephemeral | Build a Packer candidate, clone a disposable VM, run validation, then exercise the OpenTofu destroy path | Always destroy in cleanup, including after failed validation |
| `integration-test` | Persistent | A test/canary VM for any later server layer: Ansible, Docker, Kubernetes, monitoring, or similar | Keep it between runs so later-layer behavior can be observed; replace deliberately |
| `lab` | Long-lived | Real machines and services used by the homelab | Change only through reviewed desired state and protected Actions |

`integration-test` is not a builder-only environment. It is the persistent
place to test the server layers that consume a reachable builder target. A
builder-only smoke test belongs in `template-validation`.

## Immutable template releases

A template build produces an immutable release identity: the OS/template name,
source revision, Packer configuration, ISO URL, checksum, and resulting
Proxmox template identity. A release moves through these states:

1. **Candidate** — Packer built it, but no consumer may use it yet.
2. **Validated** — `template-validation` completed its clone, checks, and
   cleanup successfully.
3. **Promoted** — the release was deliberately approved for consumption.
4. **Pinned** — each machine definition names the exact promoted release it
   consumes; it does not silently follow `latest`.

Template replacement is therefore a release change, not an in-place repair of
the machines that happen to use the old template. A new release is built and
tested before machine definitions switch. Old templates and ISO files are
retired deliberately after rollback needs, dependents, and retention have been
reviewed. No cleanup job or build should auto-delete them.

The existing `force_rebuild` workflow control is not a lifecycle strategy. Do
not use it as a blind replacement mechanism; rebuilds still need a candidate,
validation, promotion, and explicit machine pin update.

## First Debian 13.6 Packer test run

This run verifies the new pinned URL flow on the existing single implemented
template. It does not promote a new multi-template architecture.

1. In Proxmox, inspect the `local` ISO storage. If an ISO was uploaded
   manually and you want to prove that PVE downloads the ISO itself, delete
   that manually uploaded ISO first. Do not delete an ISO you need for
   rollback without recording that decision.
2. In the GitHub repository variables, set:
   - `PACKER_ISO_URL` to
     `https://cdimage.debian.org/debian-cd/13.6.0/amd64/iso-cd/debian-13.6.0-amd64-netinst.iso`
   - `PACKER_ISO_CHECKSUM` to
     `sha256:65273beed27b2df543b68b65630ba525cfbad8df2b12035732b2dff87d6664e7`
3. Manually dispatch **Packer Build** for `debian-13`. Use the normal
   repository variables and secrets; do not use a local Packer build as a
   substitute for the CI run.
4. Watch the Packer and Proxmox task logs. Packer should ask PVE to download
   the URL into `local`, verify the checksum, install Debian 13.6, and create
   the current template VM identity `9000`.
5. Before using the result for a machine, treat it as a candidate and run the
   validation environment described above. The current lab machine map is not
   switched by this runbook.

Expected outcomes:

- The ISO appears in Proxmox `local` storage without a manual upload.
- The downloaded ISO passes the pinned SHA-256 check.
- Packer completes and leaves the Debian 13 template available for testing.
- The workflow records enough output to identify the candidate and its source
  revision.

Failure checks:

- Confirm both repository variables are present and have no surrounding quotes
  or whitespace.
- Confirm the Proxmox host can resolve and reach `cdimage.debian.org`.
- Confirm `local` storage has capacity and supports ISO content.
- Compare the URL and checksum exactly with this runbook; do not replace the
  checksum with a blank value or an unverified value.
- Inspect the PVE download task and Packer logs before retrying. A retry is not
  a promotion and must not delete the previous known-good artifact.

### Manual ISO fallback

The manual ISO fallback is a **Packer configuration fallback**, not Terraform
configuration and not an OpenTofu download mechanism. It would mean changing
the Packer source to use an operator-provided Proxmox ISO path after automatic
PVE download has demonstrably failed. No fallback code is added now. Add it
only after an actual automatic-download failure has been diagnosed and the
fallback has its own validation and documentation.

## Staged implementation plan

### Stage 0 — Preserve baseline compatibility

Keep the existing single `debian-13` Packer workflow working while the
local-only machine input is migrated into reviewed git configuration.

**Acceptance:** the Packer catalog resolves, the pinned Debian ISO
configuration validates, and the migration does not unexpectedly destroy
declared machines.

### Stage 1 — Add ephemeral template validation

Add the `template-validation` workflow path. It must build or select a
candidate, clone a disposable VM, run the minimum health checks, and always run
OpenTofu destroy in cleanup. Keep candidate artifacts and logs for review, but
do not leave the validation VM behind.

**Acceptance:** success, failed checks, and cancelled runs all demonstrate a
destroy attempt; a failed validation cannot be promoted.

### Stage 2 — Add persistent integration testing

Add the `integration-test` machine definition and protected workflow updates.
Use it to test the server layers after the template is proven: first Ansible,
then any Docker, Kubernetes, monitoring, or other later layer that is added.

**Acceptance:** a reviewed run can update the persistent canary, report its
exact template release, and leave it available for inspection without making
the long-lived `lab` machines depend on an unvalidated candidate.

### Stage 3 — Move machine intent into git and make Actions authoritative

Move the machine map out of untracked local-only configuration into reviewed
git configuration, while keeping secrets and real credentials outside git.
Route normal plan, apply, and destroy operations through protected GitHub
Actions backed by R2 state. Remove normal-operation instructions for local
apply/destroy.

**Acceptance:** a clean checkout plus repository configuration is sufficient
for Actions to plan and apply the declared machines; no local `terraform.tfvars`
is needed to discover desired machines, and state remains in R2.

### Stage 4 — Promote exact releases and retire deliberately

Add the smallest release metadata and promotion record needed to pin each
machine to an exact validated template. Define an operator-reviewed retirement
check for old templates and ISO artifacts. Do not build a multi-template
upgrade manager or an ISO cleanup job as part of this stage.

**Acceptance:** a machine change shows the old and new exact release, links to
the validation result, supports rollback to the retained old release, and has
an explicit human decision before old artifacts are removed.
