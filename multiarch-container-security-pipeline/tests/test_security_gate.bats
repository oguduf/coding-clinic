#!/usr/bin/env bats
setup() { ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"; }
@test "clean amd64 and arm64 reports pass" {
  run bash "$ROOT/scripts/evaluate-trivy.sh" --amd64 "$ROOT/tests/fixtures/trivy-clean-amd64.json" --arm64 "$ROOT/tests/fixtures/trivy-clean-arm64.json"
  [ "$status" -eq 0 ]
}
@test "high and critical findings fail" {
  run bash "$ROOT/scripts/evaluate-trivy.sh" --amd64 "$ROOT/tests/fixtures/trivy-high.json" --arm64 "$ROOT/tests/fixtures/trivy-clean-arm64.json"
  [ "$status" -eq 1 ]
  run bash "$ROOT/scripts/evaluate-trivy.sh" --amd64 "$ROOT/tests/fixtures/trivy-clean-amd64.json" --arm64 "$ROOT/tests/fixtures/trivy-critical.json"
  [ "$status" -eq 1 ]
}
@test "missing and malformed reports fail closed" {
  run bash "$ROOT/scripts/evaluate-trivy.sh" --amd64 "$ROOT/tests/fixtures/missing.json" --arm64 "$ROOT/tests/fixtures/trivy-clean-arm64.json"
  [ "$status" -eq 1 ]
  run bash "$ROOT/scripts/evaluate-trivy.sh" --amd64 "$ROOT/tests/fixtures/trivy-malformed.json" --arm64 "$ROOT/tests/fixtures/trivy-clean-arm64.json"
  [ "$status" -eq 1 ]
}
