#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

load test_helper

setup() {
  setup_bindir
  export GITHUB_OUTPUT="${TMPDIR}/github-output"
  : > "$GITHUB_OUTPUT"
}

mock_tofu_plan() {
  local plan_exit="$1"
  local show_output="$2"
  cat > "${TEST_BINDIR}/tofu" << MOCKTOFU
#!/bin/bash
set -euo pipefail
case "\$1" in
  plan)
    printf 'raw plan output\n'
    exit ${plan_exit}
    ;;
  show)
    cat <<'SHOWEOF'
${show_output}
SHOWEOF
    ;;
  *)
    echo "unexpected tofu command: \$*" >&2
    exit 99
    ;;
esac
MOCKTOFU
  chmod +x "${TEST_BINDIR}/tofu"
}

@test "tofu-plan reports no changes" {
  mock_tofu_plan 0 "No changes. Your infrastructure matches the configuration."

  run bash "${SCRIPT_DIR}/../../../scripts/tofu-plan.sh" --out "${TMPDIR}/tfplan" --text "${TMPDIR}/plan.txt"

  [ "$status" -eq 0 ]
  [[ "$output" == *"No changes."* ]]
  [[ "$(cat "$GITHUB_OUTPUT")" == *"has_changes=false"* ]]
  [[ "$(cat "$GITHUB_OUTPUT")" == *"summary_line=No changes."* ]]
}

@test "tofu-plan reports changes" {
  mock_tofu_plan 2 "Plan: 1 to add, 0 to change, 0 to destroy."

  run bash "${SCRIPT_DIR}/../../../scripts/tofu-plan.sh" --out "${TMPDIR}/tfplan" --text "${TMPDIR}/plan.txt" --parallelism 1

  [ "$status" -eq 0 ]
  [[ "$output" == *"Plan: 1 to add"* ]]
  [[ "$(cat "$GITHUB_OUTPUT")" == *"has_changes=true"* ]]
  [[ "$(cat "$GITHUB_OUTPUT")" == *"summary_line=Plan: 1 to add, 0 to change, 0 to destroy."* ]]
}

@test "tofu-plan returns tofu errors and does not emit outputs" {
  mock_tofu_plan 1 "should not be shown"

  run bash "${SCRIPT_DIR}/../../../scripts/tofu-plan.sh" --out "${TMPDIR}/tfplan" --text "${TMPDIR}/plan.txt"

  [ "$status" -eq 1 ]
  [[ "$output" == *"raw plan output"* ]]
  [ ! -s "$GITHUB_OUTPUT" ]
}
