"""Read-only auditor for pod security and resource settings.

Offline JSON input is the default workflow; cluster discovery is only attempted
when the caller explicitly supplies --live.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

CONFIG_KEYS = {
    "check_privileged",
    "check_hostpath",
    "check_resource_limits",
    "fail_on_violations",
}
CONFIG_PATH = Path(__file__).with_name("config.json")


class AuditError(Exception):
    """Invalid input or execution error safe to display to the operator."""


def validate_config(config: Any) -> dict[str, bool]:
    if not isinstance(config, dict):
        raise AuditError("Configuration must be a JSON object.")
    missing = CONFIG_KEYS - config.keys()
    unknown = config.keys() - CONFIG_KEYS
    if missing:
        raise AuditError(f"Configuration is missing keys: {', '.join(sorted(missing))}.")
    if unknown:
        raise AuditError(f"Configuration has unknown keys: {', '.join(sorted(unknown))}.")
    if any(type(config[key]) is not bool for key in CONFIG_KEYS):
        raise AuditError("Every configuration value must be true or false.")
    return dict(config)


def load_config(path: str | Path) -> dict[str, bool]:
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError:
        raise AuditError("Could not read the configuration file.") from None
    except json.JSONDecodeError:
        raise AuditError("Configuration file is not valid JSON.") from None
    return validate_config(config)


def validate_pod_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise AuditError("Pod input must be a Kubernetes PodList JSON object with an items array.")

    for index, pod in enumerate(payload["items"]):
        if not isinstance(pod, dict):
            raise AuditError(f"Pod item {index} must be a JSON object.")
        metadata = pod.get("metadata")
        if not isinstance(metadata, dict):
            raise AuditError(f"Pod item {index} is missing metadata.")
        if not isinstance(metadata.get("name"), str) or not metadata["name"]:
            raise AuditError(f"Pod item {index} is missing metadata.name.")
        if not isinstance(metadata.get("namespace"), str) or not metadata["namespace"]:
            raise AuditError(f"Pod item {index} is missing metadata.namespace.")
        if not isinstance(pod.get("spec"), dict):
            raise AuditError(f"Pod item {index} is missing spec.")
        status = pod.get("status")
        if not isinstance(status, dict) or not isinstance(status.get("phase"), str):
            raise AuditError(f"Pod item {index} is missing status.phase.")
        spec = pod["spec"]
        if not isinstance(spec.get("containers"), list) or not spec["containers"]:
            raise AuditError(f"Pod item {index} spec.containers must be a non-empty array.")
        for field in ("containers", "initContainers", "ephemeralContainers", "volumes"):
            value = spec.get(field, [])
            if not isinstance(value, list):
                raise AuditError(f"Pod item {index} spec.{field} must be an array.")
            if field != "volumes" and any(not isinstance(container, dict) for container in value):
                raise AuditError(f"Pod item {index} spec.{field} entries must be objects.")
            if field == "volumes" and any(not isinstance(volume, dict) for volume in value):
                raise AuditError(f"Pod item {index} spec.volumes entries must be objects.")
    return payload["items"]


def load_pods_file(path: str | Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError:
        raise AuditError("Could not read the pod input file.") from None
    except json.JSONDecodeError:
        raise AuditError("Pod input file is not valid JSON.") from None
    return validate_pod_list(payload)


def load_live_pods() -> list[dict[str, Any]]:
    """Read all namespaces using kubectl; this is called only for explicit --live."""
    command = ["kubectl", "get", "pods", "--all-namespaces", "-o", "json"]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise AuditError("Could not execute kubectl pod discovery.") from None
    if completed.returncode != 0:
        raise AuditError(f"kubectl pod discovery failed with exit code {completed.returncode}.")
    try:
        payload = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError):
        raise AuditError("kubectl returned invalid pod JSON.") from None
    return validate_pod_list(payload)


def _safe_host_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value.startswith("/") or len(value) > 256:
        return None
    if not all(character.isprintable() for character in value):
        return None
    return value


def _container_violations(
    pod: dict[str, Any],
    container: dict[str, Any],
    *,
    check_privileged: bool,
    check_limits: bool,
    container_type: str,
) -> list[dict[str, Any]]:
    metadata = pod["metadata"]
    container_name = container.get("name") or "<unnamed>"
    violations: list[dict[str, Any]] = []
    security_context = container.get("securityContext") or {}
    if not isinstance(security_context, dict):
        security_context = {}

    if check_privileged and security_context.get("privileged") is True:
        violations.append(
            {
                "namespace": metadata["namespace"],
                "pod": metadata["name"],
                "container": container_name,
                "rule": "privileged-container",
                "description": f"Privileged {container_type} container",
            }
        )

    if check_limits:
        resources = container.get("resources") or {}
        limits = resources.get("limits") if isinstance(resources, dict) else {}
        if not isinstance(limits, dict):
            limits = {}
        for resource in ("cpu", "memory"):
            if limits.get(resource) in (None, ""):
                violations.append(
                    {
                        "namespace": metadata["namespace"],
                        "pod": metadata["name"],
                        "container": container_name,
                        "rule": f"missing-{resource}-limit",
                        "description": f"Missing {resource.upper()} limit",
                    }
                )
    return violations


def audit_pods(pods: list[dict[str, Any]], config: dict[str, bool]) -> dict[str, Any]:
    pods = validate_pod_list({"items": pods})
    config = validate_config(config)
    running = [pod for pod in pods if pod["status"]["phase"] == "Running"]
    skipped = len(pods) - len(running)
    violations: list[dict[str, Any]] = []
    noncompliant_pods: set[tuple[str, str]] = set()

    for pod in running:
        pod_violations: list[dict[str, Any]] = []
        spec = pod["spec"]
        for volume in spec.get("volumes", []):
            host_path = volume.get("hostPath")
            if config["check_hostpath"] and host_path is not None:
                violation: dict[str, Any] = {
                    "namespace": pod["metadata"]["namespace"],
                    "pod": pod["metadata"]["name"],
                    "volume": volume.get("name") or "<unnamed>",
                    "rule": "hostpath-volume",
                    "description": "Pod uses a hostPath volume",
                }
                safe_path = _safe_host_path(
                    host_path.get("path") if isinstance(host_path, dict) else None
                )
                if safe_path is not None:
                    violation["host_path"] = safe_path
                pod_violations.append(violation)

        for container in spec.get("containers", []):
            pod_violations.extend(
                _container_violations(
                    pod,
                    container,
                    check_privileged=config["check_privileged"],
                    check_limits=config["check_resource_limits"],
                    container_type="regular",
                )
            )
        for container in spec.get("initContainers", []):
            pod_violations.extend(
                _container_violations(
                    pod,
                    container,
                    check_privileged=config["check_privileged"],
                    check_limits=config["check_resource_limits"],
                    container_type="init",
                )
            )
        for container in spec.get("ephemeralContainers", []):
            pod_violations.extend(
                _container_violations(
                    pod,
                    container,
                    check_privileged=config["check_privileged"],
                    check_limits=False,
                    container_type="ephemeral",
                )
            )

        if pod_violations:
            noncompliant_pods.add((pod["metadata"]["namespace"], pod["metadata"]["name"]))
            violations.extend(pod_violations)

    counts = {
        "total_pods_seen": len(pods),
        "running_pods_audited": len(running),
        "skipped_pods": skipped,
        "compliant_pods": len(running) - len(noncompliant_pods),
        "noncompliant_pods": len(noncompliant_pods),
        "violations": len(violations),
    }
    return {
        "report": "Kubernetes Pod Security Audit",
        "counts": counts,
        "overall_result": "FAIL" if violations else "PASS",
        "violations": violations,
    }


def audit_exit_code(report: dict[str, Any], config: dict[str, bool]) -> int:
    return int(bool(report["violations"]) and config["fail_on_violations"])


def render_terminal_report(report: dict[str, Any]) -> str:
    counts = report["counts"]
    lines = [
        report["report"],
        "=" * len(report["report"]),
        "",
        f"Running Pods Audited: {counts['running_pods_audited']}",
        f"Skipped Pods: {counts['skipped_pods']}",
        f"Compliant Pods: {counts['compliant_pods']}",
        f"Noncompliant Pods: {counts['noncompliant_pods']}",
        "",
        "Violations:",
    ]
    if report["violations"]:
        for violation in report["violations"]:
            location = f"{violation['namespace']}/{violation['pod']}"
            detail = violation["description"]
            if "container" in violation:
                detail += f" ({violation['container']})"
            if "volume" in violation:
                detail += f" ({violation['volume']})"
            if "host_path" in violation:
                detail += f" [hostPath: {violation['host_path']}]"
            lines.append(f"- {location}: {detail}")
    else:
        lines.append("- None")
    lines.extend(["", f"Overall Result: {report['overall_result']}"])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only Kubernetes pod security and resource auditor."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", help="Offline Kubernetes PodList JSON file.")
    mode.add_argument(
        "--live",
        action="store_true",
        help="Explicitly query the current cluster with read-only kubectl get pods.",
    )
    parser.add_argument("--config", default=str(CONFIG_PATH), help="JSON audit configuration.")
    parser.add_argument("--output", help="Optional path for a JSON compliance report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        pods = load_live_pods() if args.live else load_pods_file(args.input)
        report = audit_pods(pods, config)
        if args.output:
            Path(args.output).write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except AuditError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError:
        print("ERROR: Could not write the requested report file.", file=sys.stderr)
        return 2

    print(render_terminal_report(report))
    return audit_exit_code(report, config)


if __name__ == "__main__":
    raise SystemExit(main())

