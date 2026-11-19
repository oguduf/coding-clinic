#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v kustomize >/dev/null 2>&1; then
  render() { kustomize build "$1"; }
elif command -v kubectl >/dev/null 2>&1; then
  render() { kubectl kustomize "$1"; }
else
  echo "Install kustomize or kubectl to render the examples." >&2
  exit 127
fi
for app in app-one app-two; do
  render "examples/$app" > "/tmp/$app-rendered.yaml"
  test -s "/tmp/$app-rendered.yaml"
done
if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Install Python 3 to run the offline tests." >&2
  exit 127
fi
"$PYTHON" -m unittest discover -s tests -v