#!/usr/bin/env bash
# Exercise the real media access guard: a library file locked at mode 000 is
# found as uid 1000, repaired by root, and a healthy rerun changes nothing.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_dir="$(mktemp -d)"
trap 'rm -rf "$test_dir"' EXIT
python3 - "$repo_dir" "$test_dir" <<'PY'
from pathlib import Path
import sys
source = Path(sys.argv[1], 'builders/ansible/roles/container-services/templates/autolab-media-access.sh.j2').read_text()
source = source.replace('root="{{ autolab_services_media_root }}"', 'root="/tmp/media-test/media-stack"')
assert '{{' not in source, 'a template variable is left unreplaced'
Path(sys.argv[2], 'guard.sh').write_text(source)
PY
docker run --rm -i --network none -v "$test_dir/guard.sh:/guard.sh:ro" debian:trixie-slim bash -s <<'SH'
set -euo pipefail
mkdir -p "/tmp/media-test/media-stack/media/tv/Show/Season 01"
echo video > "/tmp/media-test/media-stack/media/tv/Show/Season 01/S01E01.mkv"
chown -R 1000:1000 /tmp/media-test/media-stack/media
# The share's own folder is root's, as on aurora, and must be left so.
chmod 0755 /tmp/media-test /tmp/media-test/media-stack
chmod 000 "/tmp/media-test/media-stack/media/tv/Show/Season 01/S01E01.mkv"
cd /
set +e
bash /guard.sh --check
result=$?
set -e
if [ "$result" != 3 ]; then
  echo "FAIL: a locked library file went undetected (exit $result)" >&2
  exit 1
fi
[ ! -e /var/lib/autolab/media-access-repairs ] || { echo "FAIL: --check changed something" >&2; exit 1; }
bash /guard.sh | grep -q REPAIRED
setpriv --reuid=1000 --regid=1000 --clear-groups -- test -r "/tmp/media-test/media-stack/media/tv/Show/Season 01/S01E01.mkv"
bash /guard.sh --check
# Healthy reruns neither repair again nor increase the counter.
out=$(bash /guard.sh)
[ -z "$out" ] || { echo "FAIL: a healthy run said: $out" >&2; exit 1; }
[ "$(cat /var/lib/autolab/media-access-repairs)" = 1 ]
grep -q '^autolab_media_readable 1$' /var/lib/autolab/textfile/autolab_media_access.prom
[ "$(stat -c %a:%u /tmp/media-test/media-stack)" = 755:0 ] || { echo "FAIL: the share folder was changed" >&2; exit 1; }
echo 'PASS: locked file detected, repaired, and healthy rerun is unchanged'
SH
