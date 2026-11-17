---
name: cosmos-release
description: Release, roll back or debug a release of COSMOS (the owner's hub) on AUTOLAB. Use when a COSMOS change should go live, a release failed, or an older version is wanted back.
---

# Releasing COSMOS

COSMOS lives in its own repository; this one builds, pins and deploys it.
The whole flow and what was proven: `docs/gitops/cosmos.md`, "Releasing".

## What happens by itself

A merge to COSMOS `main` that passes its CI dispatches **Release COSMOS**
here with the commit. That runs three jobs in order:

1. **publish**: builds both images and pushes them to the lab's registry,
   under a tag that is never overwritten.
2. **pin**: opens and merges a pull request changing
   `autolab_services_cosmos_image_tag`.
3. **deploy**: `05` `services` on jwst, apply, and waits. The role checks
   that the gateway refuses a direct request and that an authenticated one
   reaches the API and the database.

So a normal release needs nothing from here.

## By hand

```
gh workflow run cosmos-release.yml --ref main -f cosmos_sha=<a commit on COSMOS main>
```

Follow it with `run-workflow`'s steps. "Publish COSMOS images"
(`cosmos-publish.yml`) alone builds and pushes without pinning or deploying.

## Rolling back

Release an older commit the same way, or a pull request putting the
previous tag back followed by `05` `services` on jwst. The registry keeps
every tag. The database does not roll back with the code.

## When a release fails

| failed job | usually |
|---|---|
| publish | the build itself: read COSMOS's CI for the same commit |
| pin | the repository setting that lets Actions create and approve pull requests, or a conflicting open pin |
| deploy | the services run: read it as any `05` run; the previous image keeps running |

## Guardrails

- The installed phone app carries its own copy of the UI: a release
  changes what a browser loads, not a native build.
- One release at a time; a newer one waiting replaces an older one that
  has not started.
