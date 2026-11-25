"""Fail-closed evaluator for two platform-specific Trivy JSON reports."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Any

SEVERITIES = ("UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL")


def evaluate(reports: dict[str, Path], blocked: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {"passed": True, "architectures": {}, "errors": []}
    for arch, path in reports.items():
        if not path.is_file():
            result["errors"].append(f"{arch}: report missing: {path}")
            result["passed"] = False
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("Results"), list):
                raise ValueError("expected object with Results array")
            if not data["Results"]:
                raise ValueError("Results array is empty; no image scan evidence was produced")
            counts = {severity: 0 for severity in SEVERITIES}
            for scan in data["Results"]:
                if not isinstance(scan, dict):
                    raise ValueError("Results entries must be objects")
                vulns = scan.get("Vulnerabilities") or []
                if not isinstance(vulns, list):
                    raise ValueError("Vulnerabilities must be an array")
                for vuln in vulns:
                    if not isinstance(vuln, dict) or vuln.get("Severity") not in counts:
                        raise ValueError("malformed vulnerability entry or severity")
                    counts[vuln["Severity"]] += 1
            failed = any(counts[s] for s in blocked)
            result["architectures"][arch] = {"counts": counts, "passed": not failed}
            result["passed"] &= not failed
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            result["errors"].append(f"{arch}: invalid report: {exc}")
            result["passed"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amd64", required=True, type=Path)
    parser.add_argument("--arm64", required=True, type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--severity", default="HIGH,CRITICAL")
    args = parser.parse_args()
    blocked = {item.strip().upper() for item in args.severity.split(",") if item.strip()}
    if not blocked or not blocked <= set(SEVERITIES):
        print("Invalid severity list", file=sys.stderr)
        return 2
    result = evaluate({"linux/amd64": args.amd64, "linux/arm64": args.arm64}, blocked)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.summary:
        args.summary.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
