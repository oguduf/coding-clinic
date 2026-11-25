#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# == 3 ]] || {
  echo 'Usage: verify-signature.sh IMAGE@sha256:DIGEST EXPECTED_IDENTITY EXPECTED_ISSUER' >&2
  exit 2
}
image_ref=$1 identity=$2 issuer=$3
[[ $image_ref =~ ^[a-z0-9.-]+(/[a-z0-9._-]+)+@sha256:[a-f0-9]{64}$ ]] || {
  echo 'Image reference must use a valid immutable sha256 digest' >&2
  exit 2
}
command -v cosign >/dev/null || {
  echo 'cosign is required' >&2
  exit 127
}
cosign verify "$image_ref" --certificate-identity "$identity" --certificate-oidc-issuer "$issuer"
