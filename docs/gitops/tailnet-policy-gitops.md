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

Workflow 06 reuses the existing CI-runner OAuth client —
`TAILSCALE_OAUTH_CLIENT_ID` + `TAILSCALE_OAUTH_SECRET`, both already present.
No new secret, variable, or client is introduced.

The tailnet is passed as `tailnet: '-'`, the "default tailnet for this
credential" shorthand the OpenTofu provider also uses. `gitops-pusher` only
checks that the value exists, then interpolates it into
`/api/v2/tailnet/<value>/acl`, so the credential resolves its own tailnet and
no name has to be configured. If it ever fails to resolve, substitute the
literal tailnet name from the admin console's top-left corner
(`megamp15.github`) — note that is the *tailnet name*, not the MagicDNS suffix
(`bobtail-dinosaur.ts.net`), which is a different value.

### 1. Scope the CI-runner client

Admin console → **Settings → OAuth clients** → the client behind
`TAILSCALE_OAUTH_CLIENT_ID` → under **General**, enable **Policy File: Write**
(Write implies Read).

That client then holds:

| Scope | Why |
|---|---|
| `auth_keys`, owning `tag:ci-runner` | `connect-tailscale` brings the runner onto the tailnet |
| `policy_file` (Write) | this workflow reads, validates, and applies the policy |

`policy_file` Read alone is enough for `test` but fails on `apply`.

### 2. Nothing else

There is no second step.

## Credential inventory

Three Tailscale credentials exist, and only the first is shared:

| Credential | Scopes | Used by |
|---|---|---|
| CI runner (`TAILSCALE_OAUTH_CLIENT_ID`) | `auth_keys` (`tag:ci-runner`) + `policy_file` | 01, 02, 03, 04, 05, 99 for tailnet access; **06** for the policy |
| VM enrollment (`TAILSCALE_VM_OAUTH_CLIENT_ID`) | `auth_keys` (`tag:autolab-vm`) + `devices:core` | OpenTofu key minting and destroy-time device cleanup |
| *Policy-only (future)* | *`policy_file`* | *06 alone — see below* |

### Deferred: split `policy_file` into a third client

Reusing the CI-runner client means `policy_file` rides along wherever that
client goes — and `connect-tailscale` hands it to **every** workflow that
touches the tailnet: 01, 02, 03, 04, 05, 99. So a Packer build or a
`tofu destroy` runs with a credential that could rewrite the entire tailnet
policy, including the SSH rules that gate recovery.

Accepted deliberately for a single-operator lab, where the blast radius is one
person's own infrastructure.

Revisit when any of these becomes true:

- someone other than the tailnet owner can run these workflows
- the repo takes outside contributions that can trigger CI
- a workflow starts using third-party actions not pinned by digest

The fix is a third OAuth client scoped `policy_file` only, alongside the
CI-runner and VM-enrollment clients, with workflow 06 pointed at it and
`policy_file` removed from the CI-runner client.

**This costs a new secret.** CI authenticates with a classic OAuth client ID
and secret, so a separate client means a `TAILSCALE_POLICY_OAUTH_SECRET`
alongside its ID. (It would cost nothing if CI moved to OIDC/WIF first, where
there is no secret to store — see below.) Tracked in
[issue #4](https://github.com/megamp15/AUTOLAB/issues/4).

### Deferred: move CI to OIDC/WIF

`connect-tailscale` and `setup-opentofu-pipeline` both accept an `audience`
input, and `gitops-acl-action` supports OIDC too — but no workflow passes one
and no `TAILSCALE_OIDC_AUDIENCE` variable is set. The path is wired and unused.

Adopting it would delete `TAILSCALE_OAUTH_SECRET` outright: GitHub mints a
short-lived token per run, Tailscale exchanges it, and no long-lived Tailscale
credential is stored in the repository at all. It would also make the
policy-only client split free, since a client ID is not sensitive and needs
only a repository variable.

The work is a Tailscale trust credential with claim matching for this
repository, plus passing the audience through six workflows. Not done today;
the current OAuth client path is proven working.

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
