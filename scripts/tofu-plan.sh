#!/bin/bash
# tofu-plan.sh — Run an OpenTofu plan and emit stable CI outputs.
#
# Interface:
#   bash scripts/tofu-plan.sh [--out tfplan] [--text plan.txt]
#                             [--parallelism N] [--summary-default TEXT]
#
# Writes plan text to --text, prints it to stdout, and appends has_changes and
# summary_line to GITHUB_OUTPUT when running inside GitHub Actions.
set -euo pipefail

PLAN_OUT="tfplan"
PLAN_TEXT="plan.txt"
PARALLELISM=""
SUMMARY_DEFAULT="Plan completed. Review the artifact for details."

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)
      PLAN_OUT="${2:?--out requires a path}"
      shift 2
      ;;
    --text)
      PLAN_TEXT="${2:?--text requires a path}"
      shift 2
      ;;
    --parallelism)
      PARALLELISM="${2:?--parallelism requires a value}"
      shift 2
      ;;
    --summary-default)
      SUMMARY_DEFAULT="${2:?--summary-default requires text}"
      shift 2
      ;;
    -h|--help)
      sed -n '2,8p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

plan_args=(-input=false -no-color -detailed-exitcode "-out=${PLAN_OUT}")
if [[ -n "$PARALLELISM" ]]; then
  plan_args+=("-parallelism=${PARALLELISM}")
fi

set +e
tofu plan "${plan_args[@]}" > "$PLAN_TEXT"
exit_code=$?
set -e

if [[ "$exit_code" -eq 0 ]]; then
  has_changes=false
elif [[ "$exit_code" -eq 2 ]]; then
  has_changes=true
else
  cat "$PLAN_TEXT"
  exit "$exit_code"
fi

tofu show -no-color "$PLAN_OUT" > "$PLAN_TEXT"
cat "$PLAN_TEXT"

summary_line="$(grep -E '^(Plan:|No changes\.)' "$PLAN_TEXT" | tail -n 1 || true)"
summary_line="${summary_line:-$SUMMARY_DEFAULT}"

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  {
    printf 'has_changes=%s\n' "$has_changes"
    printf 'summary_line=%s\n' "$summary_line"
  } >> "$GITHUB_OUTPUT"
fi
