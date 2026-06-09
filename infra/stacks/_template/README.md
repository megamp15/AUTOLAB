# Stack template

Use this directory as the starting point for a new Autolab stack.

1. Copy `infra/stacks/_template/` to `infra/stacks/<name>/`.
2. Edit `stack.tm.hcl` with a new UUID, name, description, and tags.
3. Edit `terraform.tfvars.example` for the stack's machines and defaults.
4. Run `cd infra && terramate generate`.
5. Run `cd infra/stacks/<name> && tofu init -backend=false && tofu validate`.

The `lab` stack remains the canonical working example. If a second real stack repeats the same module wiring, promote the repeated `main.tf`/`variables.tf`/`outputs.tf` pattern into Terramate generation.
