---
tags: [gitops, apps, registry, release, template, services]
status: draft
audience: operator
---

# Our own apps

An **own app** is a whole application written here: its own repository, its
own containers and database, its own address. AUTOLAB builds its images,
pins them and runs them, the way it does for COSMOS. This page is how a new
one starts and how it is released.

It is not a module inside COSMOS (one more tile in the hub, in the COSMOS
repository; that repository's `new-module` skill), and not an upstream app
run from someone else's image (`services.md`, `apps.md`).

## The template

`templates/app/` is the starting point, and it is a whole small app, not a
blank page:

| part | what a new app starts with |
|---|---|
| server | Fastify and PostgreSQL, tests that run against a real Postgres |
| accounts | no sign-up; an admin adds each person; email and password, plus Google and Pocket ID for emails already on the list |
| web | React with Tailwind CSS and shadcn/ui, one theme file, dark and light |
| shell | an opening screen, a sign-in panel that switches on, a header with the theme switch, Settings with a grouped menu and User access |
| per app | the colours, the wordmark, the opening screen's centrepiece and its three words, the loader |

It was lifted from Novaflix, the first app built this way; a part improved
in one app is copied back here by hand. The `Dockerfile` has two targets:

| target | image | does |
|---|---|---|
| `server` | `<app>-server` | the API, as the `node` user |
| `gateway` | `<app>-gateway` | nginx: serves the web build, passes `/api/` to the server |

```sh
scripts/new-app.sh <name> <directory> [port-base]
```

writes the app into a new directory with the name filled in, installs its
dependencies and makes its first commit. Four local ports are taken from
`port-base` up (server, web dev server, built stack, Postgres), so two apps
run side by side. `docker compose --profile stack up --build` in the new
directory runs the same two images that are deployed.

The files under `templates/app/` carry their dotfile names without the dot
(`gitignore`, `github/`, `nvmrc`, `env.example`), so this repository's own
tooling does not read them; the script puts the dots back.

## Releasing

Which own apps exist is `.github/apps.json`:

| field | is |
|---|---|
| `repository` | where the code is |
| `targets` | the `Dockerfile` targets to build; each becomes the image `<app>-<target>` |
| `deploy_key` | the name of the secret holding a read-only deploy key for that repository |
| `tag_variable` | the default in `roles/container-services/defaults/main.yml` that pins the tag |
| `host` | the machine it runs on |

**Release app** (`app-release.yml`, inputs `app` and `sha`) does the whole
release in one run, in three jobs:

1. **publish** calls **Publish app images** (`app-publish.yml`). It checks the
   commit is on the app's `main`, builds each target on the runner *before*
   joining the tailnet, so a `RUN` step never has a route to the lab, and
   pushes to the lab's registry under `<sha>-<run id>-<attempt>`. A tag that
   exists is never overwritten.
2. **pin** changes `tag_variable` in a pull request and merges it. A version
   is a diff, the same as every other image here. This needs the repository
   setting "Allow GitHub Actions to create and approve pull requests".
3. **deploy** runs `05 - Ansible Builder`, playbook `services`, limited to
   `host`, and waits for it.

One release of an app runs at a time; a newer one waiting replaces an older
one that has not started. To roll back, release an older commit: the registry
keeps every tag. The database does not roll back with the code.

COSMOS predates this and still releases through its own two workflows
(`cosmos.md`). It moves here once an app has released this way.

## Proven

Novaflix was first released through **Release app** on 2026-11-22: publish,
pin (#331) and deploy all passed on the first run.
