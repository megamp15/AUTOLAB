---
tags: [gitops, tailscale, acl, policy, ci]
status: draft
audience: operator
---

# Tailnet policy GitOps

The tailnet policy is the half of Autolab access control that lives outside
OpenTofu and Ansible. `infra/tailscale/policy.hujson` is the source of truth,
applied by workflow **06 - Tailscale Policy**.

## Why this exists

Access to a Builder VM has two halves that must agree:

| Half | Where | Grants |
|---|---|---|
| The Unix account | `autolab_admin_users` in `builders/ansible/playbooks/harden.yml` | the account exists, with sudo |
| The tailnet rule | the `ssh` block in `infra/tailscale/policy.hujson` | that account may be reached |

Neither works alone. An account with no rule is unreachable; a rule with no
account is inert. While the policy lived only in the admin console, the two
could drift silently — and did: the policy had a rule for `tag:ci-runner` but
none for human operators, so nobody could SSH to their own Builder VMs while
the console's SSH quickstart still reported that Tailscale SSH was "already
allowed". See [01 - Tailscale SSH](./01-tailscale-ssh.md).

With the policy in git, both halves change in one reviewable PR, and
`sshTests` fail CI if a change would break access.

## How it runs

| Event | Mode | Effect |
|---|---|---|
| Pull request touching the policy | `test` | Validates syntax and runs `sshTests`. No change to the tailnet. |
| Push to `main` | `apply` | Makes the file the tailnet's live policy. |

**The repository becomes the source of truth.** Any edit made in the admin
console is overwritten by the next apply. Change the policy here, not there.

## Credentials: no new secrets

This workflow authenticates with **GitHub OIDC/WIF**, the same way the CI
runner joins the tailnet: GitHub mints a short-lived token, Tailscale exchanges
it for scoped access. No OAuth client secret is stored in this repository.

It reuses the existing CI-runner credential, so there is nothing new to create
beyond adding a scope to it.

### 1. Add `policy_file` to the CI-runner credential

Admin console → **Settings → OAuth clients / Trust credentials** → edit the
credential behind `TAILSCALE_OAUTH_CLIENT_ID` and add the **`policy_file`**
scope (read, validate, and modify).

`policy_file:read` is enough for `test` but not for `apply`.

### 2. Add one repository variable

| Name | Kind | Value |
|---|---|---|
| `TAILSCALE_TAILNET` | variable | Your tailnet name, from the admin console's top-left corner next to the logo (e.g. `megamp15.github`). An identifier, not a credential — hence a variable, not a secret. It cannot be `-`, unlike the OpenTofu provider's shorthand. |

`TAILSCALE_OAUTH_CLIENT_ID` and `TAILSCALE_OIDC_AUDIENCE` already exist and are
reused as-is.

### Deferred: split `policy_file` into its own credential

Reusing the CI-runner credential means it now holds `policy_file` **and**
`auth_keys`, and `connect-tailscale` hands it to every workflow that touches
the tailnet — 01, 02, 03, 04, 05, and 99. So a Packer build or a `tofu destroy`
runs with a credential that could rewrite the entire tailnet policy, including
the rules that gate recovery.

Accepted deliberately for a single-operator lab, where the blast radius is one
person's own infrastructure and the simplicity is worth more than the
separation.

Revisit when any of these becomes true:

- someone other than the tailnet owner can run these workflows
- the repo takes outside contributions that can trigger CI
- a workflow starts using third-party actions that are not pinned by digest

The fix is small and costs no secrets: create a second trust credential scoped
to `policy_file` only, claim-matched to this repository, and point workflow 06
at it via two repository **variables** (the client ID is not sensitive). The
other five workflows then lose ACL-write entirely.

| Credential | Scopes | Used by |
|---|---|---|
| CI runner | `auth_keys` (`tag:ci-runner`) + `policy_file` *(today)* | 01, 02, 03, 04, 05, 99, **and 06** |
| VM enrollment | `auth_keys` (`tag:autolab-vm`) + `devices:core` | OpenTofu key minting and device cleanup |
| *Policy (future)* | *`policy_file` only* | *06 alone* |

### 3. Confirm the file matches the live policy

Before the first apply, diff `infra/tailscale/policy.hujson` against the admin
console's Access controls page. The first apply **overwrites the live policy
with this file**, so any console-only change not represented here is lost.

### 4. Merge, and let the first apply run

Open a PR. The `test` run validates the policy and executes `sshTests` without
touching the tailnet — that is the safe rehearsal. Merge only once it is green.

### 5. Lock the admin console

Admin console → **Policy file management** → enable **"Prevent edits in the
admin console"** and set the External reference to this repository.

Do this last. It makes the drift structurally impossible rather than merely
discouraged, but until step 4 has succeeded you still want the console as an
escape hatch.

## Changing access

Adding or removing an operator is one PR touching two files:

```
builders/ansible/playbooks/harden.yml   # the account
infra/tailscale/policy.hujson           # the rule
```

Order matters when narrowing. Add the new name to the policy's `users` list and
let `harden.yml` create the account **before** removing the old names — the
human rule currently lists `megamp15`, `autolab`, and `gitops` for exactly that
reason. Drop `autolab` and `gitops` from it only once `megamp15` exists on
every Builder VM.

To revoke access urgently, delete the rule and merge: that cuts access
immediately, with no playbook run. Deleting the account is cleanup that can
follow at baseline cadence via `autolab_admin_users_absent`.

## Break-glass

If a bad policy locks CI out of the tailnet, the workflow cannot fix itself —
it needs the tailnet to reach GitHub's runners, and the runner needs the
policy to join. Recover in the admin console:

1. Turn off "Prevent edits in the admin console" (step 5 above).
2. Fix the policy there to restore access.
3. Copy the corrected policy back into `infra/tailscale/policy.hujson` and
   merge, so the file and the tailnet agree again before re-locking.

`autolab` remains the break-glass Unix account, reachable with its SSH key from
the Proxmox console if the tailnet itself is unavailable.

## Related docs

- [01 - Tailscale SSH](./01-tailscale-ssh.md) — the policy's SSH rules
- [Tailscale device lifecycle](./tailscale-device-lifecycle.md) — the other two OAuth clients
- [GitHub secrets & variables reference](./github-secrets-variables-reference.md)
