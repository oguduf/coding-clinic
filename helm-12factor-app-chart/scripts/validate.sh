#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
chart_dir="$root_dir/charts/twelve-factor-app"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

command -v helm >/dev/null 2>&1 || { echo "helm is required" >&2; exit 1; }
helm lint "$chart_dir"

for environment in dev stage prod; do
  helm template "demo-$environment" "$chart_dir" \
    --namespace "app-$environment" \
    -f "$root_dir/environments/$environment-values.yaml" \
    > "$tmp_dir/$environment.yaml"
done

has_kind() {
  local manifest="$1"
  local kind="$2"
  grep -q "^kind: $kind$" "$manifest"
}

has_kind "$tmp_dir/dev.yaml" Deployment
has_kind "$tmp_dir/dev.yaml" Service
has_kind "$tmp_dir/dev.yaml" ConfigMap
has_kind "$tmp_dir/dev.yaml" NetworkPolicy
grep -q '^apiVersion: networking.k8s.io/v1$' "$tmp_dir/dev.yaml"
grep -q 'kubernetes.io/metadata.name: ingress-nginx' "$tmp_dir/dev.yaml"
grep -q 'port: 8080' "$tmp_dir/dev.yaml"
grep -q 'port: 53' "$tmp_dir/dev.yaml"
if has_kind "$tmp_dir/dev.yaml" HorizontalPodAutoscaler || has_kind "$tmp_dir/dev.yaml" PodDisruptionBudget || has_kind "$tmp_dir/dev.yaml" ExternalSecret; then
  echo "DEV unexpectedly rendered HPA, PDB, or ExternalSecret" >&2
  exit 1
fi

for environment in stage prod; do
  has_kind "$tmp_dir/$environment.yaml" Deployment
  has_kind "$tmp_dir/$environment.yaml" HorizontalPodAutoscaler
  has_kind "$tmp_dir/$environment.yaml" PodDisruptionBudget
  has_kind "$tmp_dir/$environment.yaml" NetworkPolicy
  has_kind "$tmp_dir/$environment.yaml" ExternalSecret
done

if grep -Eq '^[[:space:]]+replicas:' "$tmp_dir/stage.yaml" || grep -Eq '^[[:space:]]+replicas:' "$tmp_dir/prod.yaml"; then
  echo "Deployment must not set replicas when HPA is enabled" >&2
  exit 1
fi

cat > "$tmp_dir/invalid-values.yaml" <<'EOF'
image:
  repository: ""
EOF
if helm template invalid "$chart_dir" -f "$tmp_dir/invalid-values.yaml" > /dev/null 2>&1; then
  echo "Helm accepted an invalid image repository" >&2
  exit 1
fi

cat > "$tmp_dir/invalid-hpa-values.yaml" <<'EOF'
autoscaling:
  enabled: true
  minReplicas: 5
  maxReplicas: 2
EOF
if helm template invalid "$chart_dir" -f "$tmp_dir/invalid-hpa-values.yaml" > /dev/null 2>&1; then
  echo "Helm accepted maxReplicas below minReplicas" >&2
  exit 1
fi

echo "Helm chart validation passed for DEV, STAGE, and PROD."
