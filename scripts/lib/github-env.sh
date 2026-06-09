#!/bin/bash
# github-env.sh — Safely write heredoc values to GITHUB_ENV
#
# Interface:
#   append_github_env NAME VALUE
#     Append a heredoc-delimited block for NAME to GITHUB_ENV.
#     Safely handles multi-line values via the AUTOLAB_ENV delimiter.
#     Exits with an error if GITHUB_ENV is not set.
#
# Bash 3.2 compatible (macOS default /bin/bash).
# shellcheck disable=SC2034

append_github_env() {
  local name="$1" value="$2"
  if [[ -z "${GITHUB_ENV:-}" ]]; then
    echo "ERROR: GITHUB_ENV is not set — cannot write environment variable '${name}'" >&2
    exit 1
  fi
  {
    printf '%s<<AUTOLAB_ENV\n' "${name}"
    printf '%s\n' "${value}"
    printf 'AUTOLAB_ENV\n'
  } >> "${GITHUB_ENV}"
}
