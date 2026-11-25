#!/usr/bin/env bash
set -Eeuo pipefail
digest=${1:-}
[[ $digest =~ ^sha256:[a-f0-9]{64}$ ]] || {
  echo 'Expected sha256:<64 lowercase hex characters>' >&2
  exit 2
}
printf '%s\n' "$digest"
