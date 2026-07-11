---
tags: [gitops, github-actions, security]
status: draft
audience: operator
---

# Step 6 - GitHub Environments

GitHub Environments group secrets and optionally require approvals before sensitive workflows can run.

For a full secrets/variables table with "where to get it" per field, see [GitHub Secrets & Variables Reference](./github-secrets-variables-reference.md).

> **Personal lab shortcut:** repository-level secrets will still work because the workflows read values through `secrets.NAME`. The environment must still exist because the workflows target `environment: autolab-plan` and `environment: autolab-apply`. For safer separation, store the sensitive values as **environment secrets** and remove the duplicates from repository secrets later.

Autolab uses two environments:

| Environment | Workflow | Purpose |
|-------------|----------|---------|
| `autolab-plan` | `opentofu-plan.yml` | Run `tofu plan` against the real Proxmox host |
| `autolab-apply` | `opentofu-apply.yml` | Run `tofu apply` — optionally protected by required reviewers |

## Repository variables (non-sensitive)

Set these at **Settings → Secrets and variables → Actions → Variables**. These are non-sensitive, so repository variables are fine:

| Variable | Description | Example |
|----------|-------------|---------|
| `PROXMOX_HOST` | Proxmox Tailscale hostname | `<proxmox-host>` |
| `PROXMOX_NODE_NAME` | Proxmox node name | `pve` |
| `PROXMOX_INSECURE_TLS` | Allow Proxmox self-signed TLS certificates | `true` |
| `SSH_PUBLIC_KEYS` | SSH public keys for VM/LXC injection (comma-separated) | `ssh-ed25519 AAAA... autolab@example` |

These align with the connection schema's `ci_env`/`ci_source` vocabulary: values marked `ci_source: variable` are read from repository variables, while values marked `ci_source: secret` are read from environment secrets.

## Environment secrets

Create both environments first:

1. Go to your GitHub repository → **Settings** → **Environments**.
2. Click **New environment** and name it `autolab-plan`.
3. Click **New environment** again and name it `autolab-apply`.

For each environment, scroll to **Environment secrets** and click **Add environment secret** for each value below.

Both environments share the same set of secrets. If you already added these as repository secrets, the workflows can use them, but environment secrets are preferred because `autolab-apply` can have stronger protection rules than `autolab-plan`.

| Secret | Value comes from | Example / notes |
|--------|------------------|-----------------|
| `TAILSCALE_OAUTH_CLIENT_ID` | Tailscale admin console → OAuth client | Client ID for the CI runner OAuth client. |
| `TAILSCALE_OAUTH_SECRET` | Tailscale admin console → OAuth client | Client secret for the same OAuth client. Shown once. |
| `PROXMOX_ENDPOINT` | Your Tailscale MagicDNS hostname | `https://<proxmox-tailnet-host>:8006` |
| `PROXMOX_API_TOKEN` | Proxmox web UI → Datacenter → Permissions → API Tokens | Full token string, e.g. `gitops@pve!opentofu=SECRET`. Do not use your root password. |
| `R2_ACCOUNT_ID` | Cloudflare dashboard URL / R2 dashboard | The account ID used to build `https://ACCOUNT_ID.r2.cloudflarestorage.com`. |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 → Manage R2 API Tokens | Access key ID for the R2 state bucket. |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 → Manage R2 API Tokens | Secret access key for the R2 state bucket. Shown once. |
| `AUTOLAB_ADMIN_SSH_PUBLIC_KEY` | Your laptop | Output of `cat ~/.ssh/id_ed25519.pub` or your chosen public key. Public, but kept here so workflows consume one consistent source. |
| `TAILSCALE_VM_AUTHKEY` | Tailscale auth key for future VMs/LXCs | Optional for the first no-machine smoke test. Required later if VMs/LXCs should auto-join Tailscale. |

The generated `.github/actions/configure-proxmox-connection` action consumes this schema-driven mapping and exports the correct CI environment for OpenTofu and Packer jobs.

## If you already used repository secrets

That is okay for a single-user lab. Do this now:

1. Still create `autolab-plan` and `autolab-apply`; the workflows target those environment names.
2. Leave the environment secret lists empty if you want to move quickly.
3. Run **OpenTofu Plan** as a smoke test.
4. Later, copy the same secret names into each environment and delete the repository-level copies.

Use environment secrets when you want different protections for plan vs apply, or when more people get access to the repo.

## Required reviewers (Enterprise only)

**Required reviewers is a GitHub Enterprise feature.** It is not available on Free or Team plans for private repositories.

If you are on an Enterprise plan, you can add required reviewers to `autolab-apply`:

1. Open the `autolab-apply` environment page.
2. Under **Deployment branches**, choose **Selected branches** and add your default branch (e.g. `main`).
3. Under **Required reviewers**, add yourself or your team.

When required reviewers are set, any workflow run that targets the `autolab-apply` environment will pause and wait for an approved review before proceeding.

For Free/Team plans: leave **Required reviewers** off. You can still use environments for secret scoping, but approval gating must be handled differently (e.g., manual workflow dispatch with a confirmation input, or branch protection rules on a protected branch that triggers the apply workflow).

## Notes

- **PROXMOX_ENDPOINT** should use the Tailscale MagicDNS hostname (e.g. `https://<proxmox-tailnet-host>:8006`) rather than public DNS. The Tailscale IP (`https://<tailscale-ip>:8006`) also works, but MagicDNS is easier to read.
- **TAILSCALE_OAUTH_CLIENT_ID** and **TAILSCALE_OAUTH_SECRET** are preferred over long-lived auth keys. Create an OAuth client in the Tailscale admin console under Settings → OAuth clients. Use **Custom scopes** and grant only **Keys → Auth Keys → Write**. Configure it to create ephemeral nodes with the `tag:ci-runner` tag. The Tailscale ACL must allow traffic from that tag to the Proxmox host on port 8006.

Sources:

- [GitHub Environments](https://docs.github.com/en/actions/deployment/using-environments-for-deployment)
- [Step 2 - Secure GitHub runner](./02-secure-runner.md)
- [Step 5 - R2 state backend](./05-r2-state-backend.md)
