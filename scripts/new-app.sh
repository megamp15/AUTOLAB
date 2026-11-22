#!/usr/bin/env bash
# Starts a new app of our own from templates/app: Fastify, PostgreSQL, React with
# Tailwind and shadcn/ui, two images
# and CI. It writes the app into a new directory, makes its first commit there, and
# stops. Putting it on the lab is docs/gitops/own-apps.md.
#
#   scripts/new-app.sh <name> <directory> [port-base]
#
# <name>       lowercase, what the repository, the containers and the address are called
# <directory>  where to create it; must not exist
# [port-base]  four local ports are taken from here up (default 3500): the server, the
#              web dev server, the built stack, and Postgres. Give each app its own, so
#              two can run side by side.
set -euo pipefail

name="${1:-}"
target="${2:-}"
base="${3:-3500}"

if [[ ! "$name" =~ ^[a-z][a-z0-9-]{1,30}$ ]]; then
  echo 'name: lowercase letters, digits and hyphens, starting with a letter' >&2
  exit 2
fi
if [[ -z "$target" || -e "$target" ]]; then
  echo 'directory: give a path that does not exist yet' >&2
  exit 2
fi
if [[ ! "$base" =~ ^[0-9]{4,5}$ ]]; then
  echo 'port-base: a port number, such as 3500' >&2
  exit 2
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
title="$(tr '[:lower:]' '[:upper:]' <<<"${name:0:1}")${name:1}"

mkdir -p "$target"
cp -R "$here/templates/app/." "$target/"
cd "$target"
mv gitignore .gitignore
mv github .github
mv nvmrc .nvmrc
mv env.example .env.example

while IFS= read -r -d '' file; do
  sed -e "s/__App__/${title}/g" -e "s/__app__/${name}/g" \
    -e "s/__SERVER_PORT__/${base}/g" -e "s/__WEB_PORT__/$((base + 1))/g" \
    -e "s/__STACK_PORT__/$((base + 2))/g" -e "s/__DB_PORT__/$((base + 3))/g" \
    "$file" > "$file.new"
  mv "$file.new" "$file"
done < <(find . -type f -print0)

cp .env.example .env
npm install --silent
git init --quiet --initial-branch main
git add --all
git commit --quiet --message "Start ${title} from the app template"

cat <<DONE
${title} is in ${target}.

  docker compose up -d db     the database, on 127.0.0.1:$((base + 3))
  npm run dev:server          the API, on :${base}
  npm run dev:web             the app, on http://127.0.0.1:$((base + 1))
  npm run check               lint, types, tests, build

Next: docs/gitops/own-apps.md, to give it a repository and put it on the lab.
DONE
