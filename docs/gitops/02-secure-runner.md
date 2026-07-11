---
tags: [gitops, github-actions, tailscale, runner, security]
status: draft
audience: operator
---

# Step 2 - Secure GitHub Actions runner

GitHub-hosted runners should validate code. They should not reach your private Proxmox host directly.

Real `tofu plan` and `tofu apply` run on **ephemeral GitHub-hosted runners** that join your tailnet temporarily via Tailscale, execute the job, and disconnect when the job ends.

## Runner model

```mermaid
flowchart LR
  GH[GitHub Actions] --> R[Ephemeral GitHub-hosted runner\nubuntu-latest]
  R -- tailscale/github-action@v2 --> TS[Tailscale network]
  TS --> PVE[Proxmox API\nvia Tailscale hostname]
```

The runner uses `tailscale/github-action@v2` to authenticate with an OAuth client and joins the tailnet for the duration of the job. When the job finishes — success or failure — the runner disconnects automatically.

## Tailscale OAuth client setup

OAuth credentials are preferred over auth keys because they don't expire and don't need periodic rotation.

Create an OAuth client in the [Tailscale admin console](https://login.tailscale.com/admin/settings/oauth):

- Choose **Custom scopes**, not **All - Read & Write**.
- Under **Keys**, grant only **Auth Keys → Write**. Leave DNS, policy file, users, devices, OAuth keys, logging, and settings unchecked.
- Configure the client to create ephemeral nodes tagged with `tag:ci-runner` (or your chosen CI tag).
- Save the **Client ID** and **Client Secret**.

Then set these as GitHub secrets named `TAILSCALE_OAUTH_CLIENT_ID` and `TAILSCALE_OAUTH_SECRET` (see [Step 6 - GitHub Environments](./06-github-environments.md)).

> **Note**: Auth keys still work but need periodic rotation. OAuth credentials are the recommended approach for CI/CD pipelines.

### CI runner tag setup

Create a tag named `ci-runner` in the Tailscale admin console. In policy syntax this is `tag:ci-runner`, but the UI may ask for the tag name without the `tag:` prefix.

For **Tag owner**, choose the narrowest owner that should be allowed to assign this tag:

- Personal lab: choose your own identity, for example `<your-github-identity>`.
- Team lab: choose `autogroup:admin` if any tailnet admin should be able to assign it.

Avoid broad owners such as `autogroup:member` for CI/security tags. Do not use `autogroup:tagged` unless you intentionally want already-tagged devices to assign this tag.

Recommended tag-owner policy shape:

```json
{
  "tagOwners": {
    "tag:ci-runner": ["<your-github-identity>"],
    "tag:autolab": ["<your-github-identity>"]
  }
}
```

Use `autogroup:admin` instead of your identity if you want any tailnet admin to manage these tags.

## Tailscale ACL

The tailnet policy must allow the tagged CI runner to reach the Proxmox host on port 8006.

Example ACL snippet:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["tag:ci-runner"],
      "dst": ["tag:autolab:8006"]
    }
  ]
}
```

If your Proxmox host is tagged (e.g. `tag:autolab`), the runner needs a route to it. Adjust the ACL to match your tagging scheme. At minimum, the runner needs TCP access to the Proxmox host on port 8006.

## Recommended runner rules

- Use `ubuntu-latest` runners — no self-hosted infrastructure to maintain.
- Use `tailscale/github-action@v2` at the start of any job that needs tailnet access.
- Use GitHub Environments for apply approvals and secrets.
- Use a least-privilege Proxmox API token.
- Keep OpenTofu state, real tfvars, SSH private keys, and generated plans out of git.
- Runners are ephemeral by nature — no cleanup or rotation needed.

## GitHub workflow split

| Workflow | Runner | Secrets? | Purpose |
|----------|--------|----------|---------|
| `opentofu-ci.yml` | `ubuntu-latest` | No | format and static validation |
| `opentofu-plan.yml` | `ubuntu-latest` | Yes | real plan against Proxmox, optional plan artifacts |
| `opentofu-apply.yml` | `ubuntu-latest` | Yes | apply from a fresh plan or saved binary plan |

**The gate between plan and apply:**

- **Enterprise plans:** use environment "Required reviewers" on `autolab-apply`
- **Free/Team plans:** the apply workflow is `workflow_dispatch` only and requires a manual `confirm: apply` input. You must deliberately run the workflow and type `apply`. That is your human-in-the-loop gate.

## Caching and artifacts

- Cache OpenTofu provider plugins with `TF_PLUGIN_CACHE_DIR`.
- Key the cache from `.terraform.lock.hcl` when present.
- Upload text plans and logs with short retention.
- Do not upload binary plan files as normal PR artifacts.
- Treat saved plan files as sensitive because they can contain cleartext values.

## Fresh apply vs saved-plan apply

Autolab supports two apply modes:

| Mode | What happens | Use when |
|------|--------------|----------|
| `fresh` | The apply workflow runs a new plan, then applies that exact plan in the same job | Default and recommended |
| `saved-plan` | The apply workflow downloads a binary `tfplan` artifact from a previous plan run | You intentionally want to approve and apply the exact reviewed plan |

Use `fresh` while learning. It avoids the common failure where a saved plan from one workflow run no longer matches the later apply run because provider versions, workspace files, variables, state, or artifacts changed.

Use `saved-plan` only when:

- the plan run was trusted
- the binary plan artifact was uploaded intentionally
- the apply run uses the same environment
- the state has not changed since the plan
- the artifact is still within its short retention window

Saved binary plans are not redacted. Do not publish them broadly.

## Job summaries

Each OpenTofu workflow writes a GitHub job summary:

- CI shows the environment and validation result.
- Plan shows whether changes were detected and whether artifacts were uploaded.
- Apply shows the mode, result, fresh-plan summary when applicable, and final apply summary.

Sources:

- [tailscale/github-action](https://github.com/tailscale/github-action)
- [Tailscale OAuth clients](https://tailscale.com/kb/1215/oauth-clients)
- [Tailscale trust credentials scopes](https://tailscale.com/kb/1623/trust-credentials#scopes)
- [Tailscale tags](https://tailscale.com/kb/1068/tags)
- [Tailscale ephemeral auth keys](https://tailscale.com/kb/1111/ephemeral-nodes)
- [GitHub dependency caching](https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows)
- [GitHub workflow artifacts](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-what-your-workflow-does/storing-and-sharing-data-from-a-workflow)
- [GitHub environments](https://docs.github.com/en/actions/reference/deployments-and-environments)
- [OpenTofu CLI config and plugin cache](https://opentofu.org/docs/cli/config/config-file/)
- [OpenTofu plan command](https://opentofu.org/docs/cli/commands/plan/)
