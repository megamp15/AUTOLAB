---
name: ansible-role
description: Write or change an Ansible role or playbook for AUTOLAB in the house style, and wire it into the workflow. Use for a new kind of host configuration, a new playbook choice in workflow 05, or when ansible-lint or check mode fails.
---

# A role or a playbook

Layout and the baseline contract: `builders/ansible/README.md`.

## The house style

- **Selected by machine policy.** A role runs on the machine whose
  `builder` block asks for it (`builder.backup.server`, `builder.services`),
  never on a hostname written in the playbook. Moving a job to another
  machine is then a machines-map change.
- **Idempotent.** A second run reports `changed=0`.
- **Check mode works on a host that has never been applied.** A task that
  reads something an earlier task would create is guarded: `stat` first,
  then `when: not ansible_check_mode or <that>.stat.exists`.
- **Refuses clearly.** An `assert` at the top for each required input, with
  a message that says which variable or GitHub secret is missing.
- **Secrets**: `no_log: true` on tasks that touch one; files `0600`, under
  `/etc/autolab/`; a secret that only protects local data is generated on
  the host, not passed in (`secret`).
- **Defaults carry the reasons.** Every variable in `defaults/main.yml` has
  a comment saying what it is for and why it has that value.
- **Pinned.** Images and packages by exact version (`bump-version`).
- **Docker ports** bind the tailnet address, never `0.0.0.0`.
- **A probe before a commitment.** Where a wrong precondition would fail
  late and obscurely (a mount, a permission, a peer), test it first, as the
  user that will use it, and fail with a readable message.
- **Tags** on roles in a playbook, so a slice can run alone.

## Steps

1. Find the nearest existing role and copy its shape: `tasks/main.yml`,
   `defaults/main.yml`, `templates/`, `handlers/`.
2. A new `builder` option: add it to the machines schema
   (`infra/stacks/<stack>/variables.tf` and
   `infra/modules/machine-normalization/variables.tf`), so the inventory
   carries it. Check `scripts/test_generate_ansible_inventory.py`.
3. A new playbook: `builders/ansible/playbooks/<name>.yml`, with a header
   comment saying what it does and what must run before it. Add `<name>` to
   the `playbook` options in `.github/workflows/05_ansible-builder.yml`. A
   workflow file or input that is new can only be dispatched once it is on
   `main`.
4. A secret or variable it reads: `secret`.
5. Checks, from `builders/ansible`. Done when both exit 0:

   ```
   for pb in playbooks/*.yml; do ansible-playbook -i inventories/lab/hosts.example.yml --syntax-check "$pb"; done
   ansible-lint playbooks roles
   ```

6. A template whose output matters (routes, policies): a test in
   `scripts/test_*.py` that renders it with Jinja and asserts on the result,
   like `test_private_dashboards.py`.
7. Its page in `docs/gitops/`, and `builders/ansible/README.md` if it adds a
   playbook. `pull-request`.
8. `run-workflow`: check mode on one host first (`limit=<host>`), then
   apply, then a second apply to see `changed=0`. `prove`.

## Guardrails

- The VM baseline never runs on a Proxmox node; nodes have their own
  playbook and workflow.
- A role does not print a value it was given as a secret, including in
  `debug` and in failure messages.
