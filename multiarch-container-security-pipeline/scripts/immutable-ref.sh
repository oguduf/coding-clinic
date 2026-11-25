#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# == 2 ]] || {
  echo 'Usage: immutable-ref.sh REGISTRY/REPOSITORY sha256:DIGEST' >&2
  exit 2
}
image=$1 digest=$2
[[ $image =~ ^[a-z0-9.-]+(/[a-z0-9._-]+)+$ ]] || {
  echo 'Invalid image repository' >&2
  exit 2
}
[[ $digest =~ ^sha256:[a-f0-9]{64}$ ]] || {
  echo 'Invalid immutable digest' >&2
  exit 2
}
printf '%s@%s\n' "$image" "$digest"
