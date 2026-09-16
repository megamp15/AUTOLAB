# Grafana dashboards (Git Sync)

Grafana writes here. This directory is the **read-write** half of the split
described in `docs/gitops/observability.md`:

- Dashboards are owned by Git Sync. Edit them in the Grafana UI; Grafana
  commits the JSON back to this path.
- Datasources, alert rules, contact points and notification policies are owned
  by Ansible file provisioning under
  `builders/ansible/roles/observability-stack/`. Those are one-way, git to
  Grafana, and are not editable in the UI on purpose. An alert threshold should
  be reviewed before it changes, not dragged.

The four dashboards already provisioned from files have not been moved here.
Migrate them one at a time. Pointing both mechanisms at the same dashboard
produces two copies that are hard to tell apart in the UI.

Grafana authenticates with a fine-grained token scoped to this repository with
Contents read/write. It is stored in Grafana's database on the stack host, not
as a GitHub Actions secret like every other Autolab credential, so it is
rotated in Grafana's Provisioning page.
