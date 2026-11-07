#!/usr/bin/env bash
# Exercise the real PBS access guard as Linux uid 34, including unreadable
# snapshot indexes beneath an otherwise accessible datastore.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_dir="$(mktemp -d)"
trap 'rm -rf "$test_dir"' EXIT
python3 - "$repo_dir" "$test_dir" <<'PY'
from pathlib import Path
import sys
source = Path(sys.argv[1], 'builders/ansible/roles/pbs/templates/autolab-pbs-access.sh.j2').read_text()
start = source.index('datastores=(')
end = source.index('\n', start)
source = source[:start] + 'datastores=("/tmp/pbs-test/store")' + source[end:]
Path(sys.argv[2], 'guard.sh').write_text(source)
PY
docker run --rm -i --network none -v "$test_dir/guard.sh:/guard.sh:ro" debian:trixie-slim bash -s <<'SH'
set -euo pipefail
mkdir -p /tmp/pbs-test/store/{.chunks/0000,vm/301/snapshot}
chown -R backup:backup /tmp/pbs-test
chmod 0750 /tmp/pbs-test/store /tmp/pbs-test/store/.chunks
echo index > /tmp/pbs-test/store/vm/301/snapshot/drive-scsi0.img.fidx
chown root:root /tmp/pbs-test/store/vm/301/snapshot/drive-scsi0.img.fidx
chmod 0600 /tmp/pbs-test/store/vm/301/snapshot/drive-scsi0.img.fidx
set +e
bash /guard.sh --check
result=$?
set -e
if [ "$result" != 3 ]; then
  echo "FAIL: unreadable snapshot index went undetected (exit $result)" >&2
  exit 1
fi
bash /guard.sh
runuser -u backup -- test -r /tmp/pbs-test/store/vm/301/snapshot/drive-scsi0.img.fidx
bash /guard.sh --check
# Healthy reruns neither repair again nor increase the counter.
bash /guard.sh
[ "$(cat /var/lib/autolab/pbs-access-repairs)" = 1 ]
echo 'PASS: unreadable index detected, repaired, and healthy rerun is unchanged'
SH
