# UI references

User-selected references for AUTOLAB and future projects:

| Reference | Use |
|---|---|
| [Skiper UI](https://skiper-ui.com) | Interaction and animation references; shadcn-compatible components |
| [Magic UI](https://magicui.design) | Animated React components and effects |
| [Cult UI](https://www.cult-ui.com) | Components, blocks and interaction patterns |
| [React Native Reusables](https://reactnativereusables.com) | Shared Expo/native/web controls with a shadcn-style approach |
| [shadcn area charts](https://ui.shadcn.com/charts/area) | History charts for infrastructure drilldowns and app views |

Use these selectively within the project's established design. AUTOLAB keeps
Home's palette, typography, thin borders and custom black hole animation.
Library defaults do not replace that visual identity. Check the selected
component's platform requirements and license before adoption. Expo DOM
components are an option for keeping web charts and custom animation inside
an iOS app; verify touch behavior and performance on the device.

## Current sequence

Finish the UGOS/NAS verification and make the existing Python/Docker photo
workflow work before building a new frontend. The Expo app, component-library
adoption and chart changes are deferred until that workflow is working.
