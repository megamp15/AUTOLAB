# Photo Jobs

An AUTOLAB app for reviewing and running NAS photo workflows. One Expo,
Expo Router, React Native Web and TypeScript frontend targets web and iOS.
A separate Python API and worker manage durable jobs on Singularity.

**Where it stands.** The web app exists: a small Python service (`photo_jobs/`)
and one page (`web/index.html`) in the home page's design. It replaces the old
`sort.py` and `dupes.py` scripts: plan, review, apply and undo, with Live
Photos kept whole, plus deleting duplicates and reviewing Immich's trash. The Expo/iOS frontend is still deferred; it would use the
same API. See `README.md` for how to run it and `docs/design/ui-references.md`
for the saved references and agreed order.

## Design constraints

The user explicitly chose the existing design at home.lab.pmahir.space.
Preserve that visual identity when changing frameworks or adding platforms.
The incumbent implementation is
`builders/ansible/roles/observability-stack/templates/homepage/index.html`.

- Preserve the custom black hole animation. Reuse its implementation on web;
  adapt the rendering layer for native where needed while preserving its
  appearance, motion and interaction. Do not replace it with a stock effect.
- Preserve the current dark palette, Space Grotesk and IBM Plex Mono typography,
  thin borders, spacing character and restrained green/amber/red status colors.
- Platform-specific buttons, navigation and other controls may adapt to native
  interaction and accessibility conventions. They must still belong to the
  same design system.
- Component libraries provide behavior and accessible primitives. Their
  default dashboard layouts, fonts, colors and styling are not the design brief.
- Keep an appropriate reduced-motion version of the animation.

## Workflow constraints

- Preview the design locally before deploying the new app to the NAS.
- Immich's personal-media mount remains read-only.
- Separate preview, review and execution of file operations.
- Keep named event folders grouped; recursively sort loose uploads by date.
- Track Live Photo image/video relationships before cleanup is enabled.
- Deletion decisions must be explicit, attributable and recoverable where possible; a missing
  API response or missing asset in a scan is never a deletion instruction. Permanent deletion
  is a deliberate mode with a typed confirmation, a re-check of each file, and a record.
- Use the same authenticated job API for web, iOS and future automation.
- Keep NAS deployments paused during the user's UGOS update until they confirm
  Singularity is back. Local design and development can continue.
