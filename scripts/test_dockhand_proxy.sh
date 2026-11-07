#!/usr/bin/env bash
# Parse the actual nginx config with a production-length proxy credential.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_dir="$(mktemp -d)"
trap 'rm -rf "$test_dir"' EXIT
proxy_image=$(python3 - "$repo_dir" "$test_dir" <<'PY'
from pathlib import Path
import re, sys
role = Path(sys.argv[1], 'builders/ansible/roles/container-services')
config = (role / 'templates/dockhand-proxy.conf.j2').read_text()
config = config.replace('{{ autolab_dockhand_proxy_token.content | b64decode | trim }}', 'a' * 64)
Path(sys.argv[2], 'default.conf').write_text(config)
print(re.search(r'dockhand_proxy: "([^"]+)"', (role / 'defaults/main.yml').read_text())[1])
PY
)
docker run --rm --network none --add-host=dockhand:127.0.0.1 \
  -v "$test_dir/default.conf:/etc/nginx/conf.d/default.conf:ro" \
  "$proxy_image" nginx -t
