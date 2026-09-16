# Grafana dashboards (Git Sync)

Grafana owns this directory and writes to it. Edit a dashboard in the UI and
Grafana commits the JSON back here.

Each file is a resource envelope rather than a bare dashboard:

```
apiVersion: dashboard.grafana.app/v1
kind: Dashboard
metadata:
  name: autolab-proxmox      # the dashboard UID
spec:                        # the dashboard itself, minus id/uid/version
```

Grafana generates a random `metadata.name` for dashboards created through the
UI. The four migrated from file provisioning set it explicitly to the UID they
already had, so existing links keep working.

Datasources, alert rules, contact points and notification policies are **not**
here. They stay under `builders/ansible/roles/observability-stack/` as one-way
file provisioning, and are deliberately not editable in the UI. A dashboard
benefits from being dragged into shape; an alert threshold should be reviewed
before it changes.

Grafana authenticates with a fine-grained token scoped to this repository with
Contents read/write. It lives in Grafana's database on the stack host rather
than as a GitHub Actions secret like every other Autolab credential, so it is
rotated from Grafana's Provisioning page. See
`docs/gitops/github-secrets-variables-reference.md`.
