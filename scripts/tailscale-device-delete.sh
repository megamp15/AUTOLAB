#!/bin/bash
# tailscale-device-delete.sh — Revoke Tailscale device(s) by hostname + tag.
#
# Why this exists: VMs join Tailscale asynchronously via cloud-init, so their
# device IDs are unknowable at plan time. Instead of tracking device IDs in
# state, we resolve devices deterministically at destroy time by name + tag.
#
# Usage:
#   scripts/tailscale-device-delete.sh <hostname>
#
# Requires:
#   TAILSCALE_OAUTH_CLIENT_ID / TAILSCALE_OAUTH_CLIENT_SECRET
#   (exported by the GitHub destroy workflow; set them manually for local runs)
#
# Contract:
#   - 0 matching devices -> log and exit 0 (idempotent)
#   - >= 1 matches       -> delete every match; HTTP 404 counts as success
#   - persistent API failure after retries -> exit 1 with manual fallback
set -euo pipefail

TAG_FILTER="tag:autolab-vm"
API_BASE="https://api.tailscale.com/api/v2"

log() { echo "[tailscale-cleanup] $*"; }
die() { echo "[tailscale-cleanup] ERROR: $*" >&2; exit 1; }

[[ $# -eq 1 ]] || {
  echo "Usage: $0 <hostname>" >&2
  echo "Example: $0 lab-01" >&2
  exit 1
}
HOSTNAME_ARG="$1"

# Parse a field out of JSON. python3 is used instead of jq because it is
# present everywhere this script runs (local macOS, GitHub runners).
json_field() {
  python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"
}

for var in TAILSCALE_OAUTH_CLIENT_ID TAILSCALE_OAUTH_CLIENT_SECRET; do
  [[ -n "${!var:-}" ]] || die "$var is not set. Export it (the destroy workflow does) or run from your shell."
done

# --- Retry wrapper: transient API errors (5xx/network) get 3 total attempts ---
with_retries() {
  local desc="$1"; shift
  local attempt status
  for attempt in 1 2 3; do
    # NB: capture the status with a plain assignment — after an `if`, $? is
    # the if-statement's status (0), not the command's.
    "$@" && return 0
    status=$?
    if [[ $attempt -lt 3 ]]; then
      log "$desc failed (attempt $attempt/3), retrying in $((attempt * 2))s..."
      sleep $((attempt * 2))
    else
      return "$status"
    fi
  done
}

# --- Step 1: exchange OAuth client credentials for an access token ---
get_access_token() {
  curl -sS -u "$TAILSCALE_OAUTH_CLIENT_ID:$TAILSCALE_OAUTH_CLIENT_SECRET" \
    -d grant_type=client_credentials "$API_BASE/oauth/token" | json_field access_token
}

ACCESS_TOKEN=""
if ! ACCESS_TOKEN="$(with_retries "OAuth token exchange" get_access_token)" || [[ -z "$ACCESS_TOKEN" ]]; then
  die "Could not obtain Tailscale access token."
fi

# --- Step 2: list all devices in the tailnet ---
list_devices() {
  # Without --fail, an API error JSON is valid input to the parser below and
  # is mistaken for an empty device list.
  curl -fsS -H "Authorization: Bearer $ACCESS_TOKEN" "$API_BASE/tailnet/-/devices"
}

DEVICES_JSON=""
if ! DEVICES_JSON="$(with_retries "device list" list_devices)"; then
  api_failure_fallback() {
    cat >&2 <<EOF

Manual fallback — revoke via curl or the admin console:

  TOKEN=\$(curl -sS -u "\$TAILSCALE_OAUTH_CLIENT_ID:\$TAILSCALE_OAUTH_CLIENT_SECRET" \\
    -d grant_type=client_credentials https://api.tailscale.com/api/v2/oauth/token | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
  curl -sS -H "Authorization: Bearer \$TOKEN" https://api.tailscale.com/api/v2/tailnet/-/devices   # find the device id
  curl -sS -X DELETE -H "Authorization: Bearer \$TOKEN" https://api.tailscale.com/api/v2/device/<id>

Or remove it by hand: https://login.tailscale.com/admin/machines
EOF
  }
  api_failure_fallback
  die "Failed to list Tailscale devices after retries."
fi

# --- Step 3: filter client-side — match the hostname or Tailscale's numeric
# collision suffix, and require our tag. Device names are FQDNs like
# lab-01.tailnet-name.ts.net, so compare labels, not substrings. ---
MATCHING_IDS="$(printf '%s' "$DEVICES_JSON" | python3 -c '
import json, sys
hostname = sys.argv[1]
tag = sys.argv[2]
devices = json.load(sys.stdin).get("devices", [])
for d in devices:
    name = d.get("name", "")
    first_label = name.split(".")[0] if name else ""
    suffix = first_label.removeprefix(hostname + "-")
    if (first_label == hostname or (first_label.startswith(hostname + "-") and suffix.isdigit())) and tag in d.get("tags", []):
        print(d["id"])
' "$HOSTNAME_ARG" "$TAG_FILTER")"

if [[ -z "$MATCHING_IDS" ]]; then
  log "No devices tagged '$TAG_FILTER' named '$HOSTNAME_ARG' found. Nothing to do."
  exit 0
fi

# --- Step 4: delete every match; 404 counts as already-gone ---
delete_device() {
  local id="$1"
  # -w captures the HTTP code without fetching a body; curl still fails on
  # network errors, which we treat like any other retryable failure.
  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE \
    -H "Authorization: Bearer $ACCESS_TOKEN" "$API_BASE/device/$id")" || return 1
  case "$code" in
    200|204|404)
      log "Deleted device $id ($HOSTNAME_ARG) [HTTP $code]."
      ;;
    5*)
      log "Transient error deleting $id [HTTP $code]."
      return 1
      ;;
    *)
      die "Unexpected HTTP $code deleting device $id."
      ;;
  esac
}

FAILED=0
while IFS= read -r id; do
  [[ -n "$id" ]] || continue
  if ! with_retries "delete device $id" delete_device "$id"; then
    FAILED=1
  fi
done <<< "$MATCHING_IDS"

if [[ "$FAILED" -eq 1 ]]; then
  cat >&2 <<EOF

[tailscale-cleanup] ERROR: Failed to delete some devices after retries.

Manual fallback — revoke via curl or the admin console:

  TOKEN=\$(curl -sS -u "\$TAILSCALE_OAUTH_CLIENT_ID:\$TAILSCALE_OAUTH_CLIENT_SECRET" \\
    -d grant_type=client_credentials https://api.tailscale.com/api/v2/oauth/token | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
  curl -sS -H "Authorization: Bearer \$TOKEN" https://api.tailscale.com/api/v2/tailnet/-/devices   # find the device id
  curl -sS -X DELETE -H "Authorization: Bearer \$TOKEN" https://api.tailscale.com/api/v2/device/<id>

Or remove it by hand: https://login.tailscale.com/admin/machines
EOF
  exit 1
fi

log "Tailscale cleanup for '$HOSTNAME_ARG' complete."
