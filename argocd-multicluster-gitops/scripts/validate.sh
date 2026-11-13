#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

for command_name in kubectl python3; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "$command_name" >&2
    exit 1
  fi
done

python3 - <<'PY'
try:
    import yaml  # noqa: F401
except ImportError as error:
    raise SystemExit("PyYAML is required for offline manifest checks. Install it with: python3 -m pip install PyYAML") from error
PY

required_files=(
  applicationset.yaml
  app/base/deployment.yaml
  app/base/service.yaml
  app/base/kustomization.yaml
  app/overlays/dev/kustomization.yaml
  app/overlays/dev/deployment-patch.yaml
  app/overlays/dev/namespace.yaml
  app/overlays/stage/kustomization.yaml
  app/overlays/stage/deployment-patch.yaml
  app/overlays/stage/namespace.yaml
  app/overlays/prod/kustomization.yaml
  app/overlays/prod/deployment-patch.yaml
  app/overlays/prod/namespace.yaml
)
for file in "${required_files[@]}"; do
  if [[ ! -f "$file" ]]; then
    printf 'Required file is missing: %s\n' "$file" >&2
    exit 1
  fi
done

render_dir="$(mktemp -d)"
trap 'rm -rf "$render_dir"' EXIT
for environment in dev stage prod; do
  printf 'Rendering %s overlay...\n' "$environment"
  kubectl kustomize "app/overlays/$environment" > "$render_dir/$environment.yaml"
done

python3 - "$ROOT_DIR" "$render_dir" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

root = Path(sys.argv[1])
render_dir = Path(sys.argv[2])
expected = {
    "dev": {"namespace": "app-dev", "replicas": 1, "cpu_request": "50m", "memory_request": "64Mi", "cpu_limit": "250m", "memory_limit": "128Mi"},
    "stage": {"namespace": "app-stage", "replicas": 2, "cpu_request": "100m", "memory_request": "128Mi", "cpu_limit": "500m", "memory_limit": "256Mi"},
    "prod": {"namespace": "app-prod", "replicas": 3, "cpu_request": "250m", "memory_request": "256Mi", "cpu_limit": "1", "memory_limit": "512Mi"},
}

def documents(path: Path) -> list[dict]:
    try:
        location = path.relative_to(root)
    except ValueError:
        location = path
    try:
        docs = [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc is not None]
    except yaml.YAMLError as error:
        raise SystemExit(f"Invalid YAML in {location}: {error}") from error
    if any(not isinstance(doc, dict) for doc in docs):
        raise SystemExit(f"YAML documents in {location} must be mappings")
    return docs

def contains_sensitive_key(value: object) -> bool:
    sensitive = {"password", "token", "clientsecret", "clientid", "accesskey", "secretkey", "privatekey", "kubeconfig", "authorization"}
    if isinstance(value, dict):
        return any(str(key).replace("_", "").lower() in sensitive or contains_sensitive_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_sensitive_key(item) for item in value)
    return False

# Parse every repository manifest locally and ensure no credentials or Secret objects are committed.
for path in [root / "applicationset.yaml", *sorted((root / "app").rglob("*.yaml")), *sorted((root / "app").rglob("*.yml"))]:
    for doc in documents(path):
        if doc.get("kind") == "Secret":
            raise SystemExit(f"Kubernetes Secret manifests must not be committed: {path.relative_to(root)}")
        if contains_sensitive_key(doc):
            raise SystemExit(f"Credential-like field found in {path.relative_to(root)}")
        text = path.read_text(encoding="utf-8")
        if re.search(r"https?://[^\s/]+:[^\s/@]+@", text):
            raise SystemExit(f"Credential-bearing URL found in {path.relative_to(root)}")

appset_docs = documents(root / "applicationset.yaml")
if len(appset_docs) != 1:
    raise SystemExit("applicationset.yaml must contain exactly one document")
appset = appset_docs[0]
if appset.get("apiVersion") != "argoproj.io/v1alpha1" or appset.get("kind") != "ApplicationSet":
    raise SystemExit("applicationset.yaml must define an argoproj.io/v1alpha1 ApplicationSet")
spec = appset.get("spec", {})
if not isinstance(spec, dict):
    raise SystemExit("ApplicationSet spec must be a mapping")
generators = spec.get("generators", [])
if not isinstance(generators, list) or len(generators) != 1 or not isinstance(generators[0], dict) or not isinstance(generators[0].get("list"), dict):
    raise SystemExit("ApplicationSet must use exactly one list generator")
elements = generators[0]["list"].get("elements", [])
if not isinstance(elements, list) or any(not isinstance(item, dict) for item in elements):
    raise SystemExit("ApplicationSet list elements must be mappings")
if {item.get("environment") for item in elements} != set(expected) or len(elements) != 3:
    raise SystemExit("ApplicationSet list must define exactly dev, stage, and prod")
app_names = [f"demo-app-{item['environment']}" for item in elements]
if len(app_names) != len(set(app_names)):
    raise SystemExit("Generated Application names must be unique")
for item in elements:
    env = item["environment"]
    expected_values = expected[env]
    if item.get("namespace") != expected_values["namespace"]:
        raise SystemExit(f"ApplicationSet has the wrong namespace for {env}")
    if not item.get("cluster") or not str(item.get("server", "")).endswith(".example.invalid"):
        raise SystemExit(f"ApplicationSet must use a placeholder cluster URL for {env}")
    overlay = item.get("overlay", "")
    if not (root / overlay / "kustomization.yaml").is_file():
        raise SystemExit(f"ApplicationSet overlay path does not exist: {overlay}")
template_value = spec.get("template", {})
if not isinstance(template_value, dict):
    raise SystemExit("ApplicationSet template must be a mapping")
template = template_value.get("spec", {})
template_metadata = template_value.get("metadata", {})
if not isinstance(template, dict) or not isinstance(template_metadata, dict):
    raise SystemExit("ApplicationSet template metadata and spec must be mappings")
source = template.get("source", {})
destination = template.get("destination", {})
sync = template.get("syncPolicy", {})
automated = sync.get("automated", {})
if template_metadata.get("name") != "demo-app-{{environment}}":
    raise SystemExit("Application template name must generate demo-app-<environment>")
if template.get("project") != "default" or source.get("targetRevision") != "main":
    raise SystemExit("Application template must use project default and targetRevision main")
if source.get("path") != "{{overlay}}" or destination.get("server") != "{{server}}" or destination.get("namespace") != "{{namespace}}":
    raise SystemExit("Application template must use each list entry's overlay, server, and namespace")
if "example-org" not in str(source.get("repoURL", "")):
    raise SystemExit("ApplicationSet source must keep the documented example repository placeholder")
if automated.get("selfHeal") is not True or automated.get("prune") is not False:
    raise SystemExit("Automated sync must enable selfHeal and keep prune disabled")
if "CreateNamespace=true" not in sync.get("syncOptions", []):
    raise SystemExit("Application template must set CreateNamespace=true")

for env, values in expected.items():
    docs = documents(render_dir / f"{env}.yaml")
    namespace = values["namespace"]
    ns_docs = [doc for doc in docs if doc.get("kind") == "Namespace" and doc.get("metadata", {}).get("name") == namespace]
    deployments = [doc for doc in docs if doc.get("kind") == "Deployment" and doc.get("metadata", {}).get("name") == "demo-app"]
    services = [doc for doc in docs if doc.get("kind") == "Service" and doc.get("metadata", {}).get("name") == "demo-app"]
    if len(ns_docs) != 1 or len(deployments) != 1 or len(services) != 1:
        raise SystemExit(f"{env} overlay must render one namespace, deployment, and service")
    deployment, service = deployments[0], services[0]
    if deployment.get("metadata", {}).get("namespace") != namespace or service.get("metadata", {}).get("namespace") != namespace:
        raise SystemExit(f"{env} overlay resources do not target {namespace}")
    if deployment.get("spec", {}).get("replicas") != values["replicas"]:
        raise SystemExit(f"{env} overlay must have {values['replicas']} replicas")
    labels = deployment.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {})
    if labels.get("environment") != env:
        raise SystemExit(f"{env} Pod template is missing its environment label")
    containers = deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
    container = next((item for item in containers if item.get("name") == "nginx"), None)
    if container is None:
        raise SystemExit(f"{env} Deployment has no nginx container")
    resources = container.get("resources", {})
    if resources.get("requests", {}) != {"cpu": values["cpu_request"], "memory": values["memory_request"]}:
        raise SystemExit(f"{env} resource requests are incorrect")
    if resources.get("limits", {}) != {"cpu": values["cpu_limit"], "memory": values["memory_limit"]}:
        raise SystemExit(f"{env} resource limits are incorrect")
    env_vars = {item.get("name"): item.get("value") for item in container.get("env", [])}
    if env_vars.get("APP_ENV") != env:
        raise SystemExit(f"{env} overlay has the wrong APP_ENV value")
    print(f"PASS: {env} namespace, replicas, labels, and resources")

print("PASS: ApplicationSet structure, environments, paths, and sync safeguards")
print("PASS: no Kubernetes Secret objects or credential-bearing URLs")
PY

printf 'All local GitOps validations passed. No cluster was contacted.\n'
