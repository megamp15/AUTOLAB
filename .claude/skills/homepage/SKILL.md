---
name: homepage
description: Change AUTOLAB's own home page (home.lab) - a card, a tab, the architecture view, its status API. Use for a UI change to home, a new row or check, or a bug on the page.
---

# The home page

`home.lab.<zone>` is the lab's own page: one HTML file and a small read-only
API, in the observability role. What its views show:
`docs/gitops/operations.md`. dash (`dash.lab.<zone>`) is a different thing:
gethomepage, configured in the container-services role.

## Where things are

| what | where |
|---|---|
| the page | `roles/observability-stack/templates/homepage/index.html` |
| the cards | `autolab_obs_homepage_links` in the role's `defaults/main.yml` |
| a container's link | `CTR_APPS` in `index.html`, keyed by Compose service name |
| the status collector and access labels | `templates/autolab-obs-digest.py.j2` |
| the read-only API | `files/homepage_api.py`, `files/homepage_metrics.py` |
| design references | `docs/design/` |
| ui-sdk web components (accordion, segmented control) | `templates/homepage/ui-sdk.js`, rebuilt by `scripts/build_homepage_ui_sdk.sh` |

A new card for a service is `surfaces`, not this skill.

## Steps

1. Preview against the live read-only sources, from the repository root:
   `python3 scripts/preview_homepage.py`, then
   `http://127.0.0.1:8766/index.html` (`#architecture` for that tab).
   `--status`, `--prometheus` and `--loki` point it elsewhere.
2. Make the change. The page's rules:
   - status and progress are drawn once and patched in place: nothing
     pulses, flashes or replays a fade when data refreshes;
   - controls are the page's own (select, date, check, dialogs), never the
     browser's native ones; buttons are outlined and fill on hover;
   - a control with its own keys (a disclosure, a single choice, a tree) is a
     ui-sdk web component: add its entry to the build script, rebuild, and style
     it from its `data-slot` and state attributes (`ui-sdk` skill);
   - a source that failed is named on the page, never shown as an empty
     healthy lab;
   - the API accepts known identities and fixed ranges only: no arbitrary
     query, URL or write reaches a backend.
3. Tests. Done when they pass:
   - `python3 -m unittest discover -s scripts -p 'test_homepage*.py'`
   - the browser checks, against the preview:
     `agent-browser eval --stdin < scripts/test_homepage_canvas.js` and
     `scripts/test_homepage_details.js`.
4. Look at it in a browser at desktop and phone width, light and dark.
5. `pull-request`. The merge deploys it: the observability role applies on
   merge. Open `home.lab.<zone>` afterwards and check the change is there.

## Guardrails

- The API stays read-only and unpublished: it is reached through the
  page's own login, never on a port.
- home is never given a public name.
