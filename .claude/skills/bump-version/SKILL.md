---
name: bump-version
description: Bump a pinned version in AUTOLAB - a container image, the OIDC plugin, a provider, a collection, a GitHub Action. Use on a Diun notification, a security advisory, or a wanted feature.
---

# Bumping a pinned version

Everything is pinned on purpose: an image that changes underneath the lab
is what the lab is built to avoid. Diun says a newer tag exists; the bump
is a pull request.

## Where the pins are

| what | where |
|---|---|
| a service's image | `autolab_services_images` in `roles/container-services/defaults/main.yml` |
| cloudflared, Traefik, Pocket ID | `autolab_ingress_images`; the OIDC plugin's version beside them |
| Prometheus, Loki, Grafana, Alloy | the observability roles' defaults |
| an image this repository builds (qr, code-server) | its build files; the tag is a hash of them, so an edit is a new tag |
| COSMOS | `autolab_services_cosmos_image_tag`, set by a release: `cosmos-release` |
| OpenTofu providers | each Stack's `versions.tf` and its lock file |
| Ansible collections | `builders/ansible/requirements.yml` |
| GitHub Actions | the `uses:` lines in `.github/` |
| the VM template | `infra/packer/template-catalog.yaml`: `proxmox-node` |

## Steps

1. Read the release notes from the current pin to the new one. Look for: a
   migration, a renamed setting, a changed default, a dropped platform. Say
   what you found in the pull request, including "nothing".
2. A database-backed app: check the dump is recent, or take a backup (`08`
   for the VM) before the deploy.
3. Change the pin, and anything the notes require. One app per pull request.
4. A plugin or anything that reads a config this repository templates:
   check the template still matches the new version's options, from its
   source or docs at that version, not from memory.
5. `pull-request`, then `run-workflow` for the role that owns it, check
   then apply.
6. Done when the container is `healthy` on the new tag, the app opens, and
   sign-in still works for an app behind Pocket ID.

## Rolling back

The previous pin, in a pull request, and the same run. A database that the
new version migrated does not roll back with the image: restore it from the
dump taken in step 2.

## Guardrails

- A major version is its own pull request with its migration read first.
- Never `latest`, and never a tag changed on the host by hand.
