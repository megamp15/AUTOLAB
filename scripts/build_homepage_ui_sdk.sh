#!/usr/bin/env bash
# Rebuilds the home page's ui-sdk bundle (templates/homepage/ui-sdk.js): the web components
# the page uses, in one file, since the page has no build step. Bump VERSION on purpose.
#   scripts/build_homepage_ui_sdk.sh
set -euo pipefail
VERSION=0.1.0-beta.16
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/builders/ansible/roles/observability-stack/templates/homepage/ui-sdk.js"
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
npm init -y >/dev/null
npm install --silent --save-exact "@ui-sdk/web@$VERSION" "@ui-sdk/core@$VERSION" esbuild@0.25.0
printf 'import "@ui-sdk/web/segmented-control";\nimport "@ui-sdk/web/accordion";\n' > entry.js
{
  printf '/* @ui-sdk/web %s (Vercel, Apache-2.0): segmented-control and accordion.\n   Built by scripts/build_homepage_ui_sdk.sh; do not edit. */\n' "$VERSION"
  npx esbuild entry.js --bundle --minify --format=esm --target=es2022 --log-level=warning
} > "$OUT"
echo "wrote $OUT ($(wc -c < "$OUT") bytes)"
