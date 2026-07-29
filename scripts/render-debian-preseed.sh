#!/bin/bash
# Render the tracked Debian preseed using only CI build inputs.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
template="${repo_root}/infra/packer/templates/debian-13/debian-13-preseed.cfg.tpl"
: "${AUTOLAB_PRESEED_PASSWORD:?AUTOLAB_PRESEED_PASSWORD is required}"
if [[ "${AUTOLAB_PRESEED_PASSWORD}" == *$'\n'* || "${AUTOLAB_PRESEED_PASSWORD}" == *$'\r'* ]]; then
  echo "ERROR: preseed password must not contain newlines." >&2
  exit 1
fi

AUTOLAB_PRESEED_TEMPLATE="${template}" python3 - <<'PY'
import json
import os
from pathlib import Path

text = Path(os.environ["AUTOLAB_PRESEED_TEMPLATE"]).read_text()
password = os.environ["AUTOLAB_PRESEED_PASSWORD"]
keys = [key.strip() for key in os.environ.get("AUTOLAB_PRESEED_KEYS", "").split(",") if key.strip()]
encoded_keys = [json.dumps(key).replace("'", "\\u0027") for key in keys]
rendered = []
in_key_loop = False
for line in text.replace("${root_password}", password).splitlines(keepends=True):
    if "%{ for key in ssh_keys" in line:
        in_key_loop = True
        body = line.split("~}", 1)[1]
        rendered.extend(body.replace("${jsonencode(key)}", key) for key in encoded_keys)
        continue
    if "%{ endfor" in line:
        in_key_loop = False
        rendered.append(line.split("~}", 1)[1])
        continue
    if in_key_loop:
        rendered.extend(
            line.replace("${jsonencode(key)}", key) for key in encoded_keys
        )
    else:
        rendered.append(line)
print("".join(rendered), end="")
PY
