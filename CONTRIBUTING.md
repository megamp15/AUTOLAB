# Contributing to Autolab

Thanks for helping grow this project. It is aimed at **beginners** and **repeatable Proxmox bootstrap**. Keep changes clear, and test on a real or virtual host when you can.

## Before you open a PR

Run the same checks CI runs. CI runs all of these on every push and pull request.

```bash
# 1. Bash syntax and ShellCheck for every script
find docs/proxmox/scripts scripts -name '*.sh' -exec bash -n {} \;
find docs/proxmox/scripts scripts -name '*.sh' -print0 | xargs -0 shellcheck -S warning
yamllint .github/ builders/ansible/ infra/*.yaml infra/packer/*.yaml docs/proxmox/config/*.yaml

# 2. Generated adapters match their schemas (needs yq)
bash scripts/check-schema-drift.sh

# 3. OpenTofu formatting and validation
tofu fmt -check -recursive infra
tofu -chdir=infra/stacks/lab init -backend=false -input=false
tofu -chdir=infra/stacks/lab validate

# 4. Bats suite for the bootstrap libraries and generators
bats docs/proxmox/scripts/tests/

# 5. Script unit tests (Python stdlib unittest + bash self-check)
python3 -m unittest discover -s scripts -p 'test_*.py'
bash scripts/test_tailscale-device-delete.sh

# 6. Bootstrap dry-run in a clean Debian container (needs Docker)
bash scripts/bootstrap-dry-run.sh

# 7. Ansible (pip install ansible-core ansible-lint)
cd builders/ansible
ansible-galaxy collection install -r requirements.yml
for pb in playbooks/*.yml; do ansible-playbook -i inventories/lab/hosts.example.yml --syntax-check "$pb"; done
ansible-lint playbooks roles
```

`90 - Scripts`, `97 - Ansible CI`, and `98 - OpenTofu CI` run on every push and pull request and are required to pass before merging to `main`. Review the [production-readiness gates](docs/production-readiness.md) that apply to your change. Plan, apply, Packer build, and the Ansible Builder run against a real host only through manual workflow dispatch.

### Rules

- **No secrets or site-specific values.** Wi-Fi credentials, real IPs, auth keys, and tokens stay out of git. Use the placeholders in [network.env.example](docs/proxmox/config/network.env.example) and the `*.example` files.
- **Edit schemas, not generated files.** The following YAML files are the source of truth. After changing one, run its generator and commit the regenerated output.

  | Schema | Generator |
  |--------|-----------|
  | [`infra/connection-schema.yaml`](infra/connection-schema.yaml) | `bash scripts/generate-connection-adapters.sh` |
  | [`infra/packer/template-schema.yaml`](infra/packer/template-schema.yaml) | `bash scripts/generate-packer-template-adapters.sh` |
  | [`docs/proxmox/config/network-env-schema.yaml`](docs/proxmox/config/network-env-schema.yaml) | `bash scripts/generate-network-env-adapters.sh` |
  | [`infra/r2-config.yaml`](infra/r2-config.yaml) | `bash scripts/generate-r2-config.sh` |

- **Machine inventory lives in git.** Change `infra/stacks/lab/machines.auto.tfvars` to add or alter lab VMs; do not rely on a local `terraform.tfvars` for inventory.
- **Docs carry frontmatter.** Guides under `docs/` use `tags`, `status` (`alpha` | `draft` | `stable`), and `audience`. Top-level READMEs and ADRs do not.
- **Record decisions.** Architecture-level choices get an ADR in [`docs/adr/`](docs/adr/). Shared vocabulary lives in [CONTEXT.md](CONTEXT.md); use those terms.

## Branches and commits

- One logical change per PR when possible (scripts vs docs vs infra).
- Conventional-style prefixes are used in history: `feat(builder):`, `fix(packer):`, `docs:`, `ci:`, `test:`, `chore:`.
- Say what changed and **why** (for example: `fix(bootstrap): quote failover env vars — special chars broke source`).

## Docs style

- Full paths on first mention: `/etc/default/proxmox-network.env`, `/root/proxmox-setup/scripts/`.
- Use **bootstrap** vs **GitOps** as defined in [docs/ROADMAP.md](docs/ROADMAP.md).
- Examples use placeholder subnets (`192.168.1.x`) and hostnames (`pve.example.ts.net`), not your home network.

## Reporting issues

Include: PVE version (`pveversion -v`), output of `ip -br link`, whether USB Ethernet was plugged in, and the workflow run link for CI failures. Redact Wi-Fi passwords and tokens.
