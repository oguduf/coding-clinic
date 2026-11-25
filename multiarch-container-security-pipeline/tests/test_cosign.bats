#!/usr/bin/env bats
setup() {
  ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  mkdir -p "$BATS_TEST_TMPDIR/bin"
  cat >"$BATS_TEST_TMPDIR/bin/cosign" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$*" >"${COSIGN_LOG:?}"
if [[ -n ${EXPECTED_IDENTITY:-} && " $* " != *"--certificate-identity $EXPECTED_IDENTITY"* ]]; then
  exit 8
fi
if [[ -n ${EXPECTED_ISSUER:-} && " $* " != *"--certificate-oidc-issuer $EXPECTED_ISSUER"* ]]; then
  exit 9
fi
exit "${COSIGN_EXIT_CODE:-0}"
MOCK
  chmod +x "$BATS_TEST_TMPDIR/bin/cosign"
  export PATH="$BATS_TEST_TMPDIR/bin:$PATH"
  export COSIGN_LOG="$BATS_TEST_TMPDIR/cosign.log"
}
@test "verifier uses immutable reference, expected identity and issuer" {
  ref="registry.example.invalid/team/app@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  run bash "$ROOT/scripts/verify-signature.sh" "$ref" "https://github.com/example/repo/workflow.yml@refs/heads/main" "https://token.actions.githubusercontent.com"
  [ "$status" -eq 0 ]
  grep -q -- '--certificate-identity https://github.com/example/repo/workflow.yml@refs/heads/main' "$COSIGN_LOG"
  grep -q -- '--certificate-oidc-issuer https://token.actions.githubusercontent.com' "$COSIGN_LOG"
}
@test "invalid digest and failed verification propagate as failure" {
  run bash "$ROOT/scripts/verify-signature.sh" "registry.example.invalid/team/app:latest" identity issuer
  [ "$status" -eq 2 ]
  export COSIGN_EXIT_CODE=9
  run bash "$ROOT/scripts/verify-signature.sh" "registry.example.invalid/team/app@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" identity issuer
  [ "$status" -eq 9 ]
}
@test "unexpected identity or issuer causes verification failure" {
  ref="registry.example.invalid/team/app@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  export EXPECTED_IDENTITY='https://github.com/example/repo/workflow.yml@refs/heads/main'
  run bash "$ROOT/scripts/verify-signature.sh" "$ref" "https://github.com/attacker/other.yml@refs/heads/main" "https://token.actions.githubusercontent.com"
  [ "$status" -eq 8 ]
  export EXPECTED_ISSUER='https://token.actions.githubusercontent.com'
  run bash "$ROOT/scripts/verify-signature.sh" "$ref" "$EXPECTED_IDENTITY" "https://issuer.invalid"
  [ "$status" -eq 9 ]
}
