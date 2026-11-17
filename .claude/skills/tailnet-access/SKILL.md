---
name: tailnet-access
description: Change who and what can reach AUTOLAB over Tailscale - the policy file, operator accounts, a device tag, an orphaned device. Use to add or remove an operator, open a path between machines, or when CI or a person cannot connect.
---

# Tailnet access

The policy is a file: `infra/tailscale/policy.hujson`. Workflow `06` tests
it on the pull request and applies it on merge. The design:
`docs/gitops/tailnet-policy-gitops.md`.

## Changing who can reach what

1. Edit `policy.hujson`. An operator is two edits in one pull request: the
   account in `playbooks/harden.yml` (`autolab_admin_users`) and the rule in
   the policy's `ssh` block.
2. Add or change the policy's own tests (`sshTests`, `tests`) for the rule:
   one that must be allowed, one that must be refused. `06` on the pull
   request runs them, and blocks a merge that would lock CI out.
3. `pull-request`. Merge applies the policy at once; the account needs `05`
   `harden`.
4. **When narrowing, order matters**: add the new name and let `harden`
   create the account on every machine before removing the old names.

Done when `06` is green on `main` and the person, or the machine, connects.

## Revoking now

Delete the rule and merge: access ends immediately, with no playbook run.
The account is cleaned up later through `autolab_admin_users_absent`.

## By hand

- **Split DNS** for `lab.<zone>` and the tailnet's global nameservers are
  set in the admin console: `docs/gitops/ingress.md`, "The tailnet side".
- **A device's tag** on something that is not a VM (the NAS):
  `tailscale up --advertise-tags=<tag>` on the device, after the policy that
  defines the tag has merged.
- **An orphaned device** (a VM destroyed before the cleanup hook existed):
  `scripts/tailscale-device-delete.sh <hostname>`, or the admin console.

## Locked out

A bad policy can stop CI from joining the tailnet, and then the workflow
cannot fix it. Give the user the break-glass steps from the doc: turn off
the admin console's edit lock, fix the policy there, copy it back into the
file, merge, lock again. `autolab` is the account that works from a node's
console when the tailnet itself is down.

## Guardrails

- `root` is never granted over Tailscale SSH on a VM.
- A tenant's machines are on the tenant's tailnet. Nothing in this policy
  reaches them, and that is the design.
