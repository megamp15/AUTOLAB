#!/bin/bash
# Deprecated name — use refresh-network-scripts-from-repo.sh
echo "NOTE: sync-host-to-docs.sh was renamed to refresh-network-scripts-from-repo.sh" >&2
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/refresh-network-scripts-from-repo.sh" "$@"
