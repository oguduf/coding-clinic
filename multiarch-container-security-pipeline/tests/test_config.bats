#!/usr/bin/env bats
setup() { ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"; }
@test "pipeline example passes config validation" {
  run python3 "$ROOT/scripts/validate_config.py" "$ROOT/config/pipeline.example.yaml"
  [ "$status" -eq 0 ]
}
