"""Validate the portable pipeline YAML shape and fail closed on enabled publishing."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import yaml


def validate(path: Path) -> list[str]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [f"Unable to parse config: {exc}"]
    if not isinstance(data, dict):
        return ["configuration root must be a mapping"]
    errors: list[str] = []
    if data.get("image", {}).get("platforms") != ["linux/amd64", "linux/arm64"]:
        errors.append("image.platforms must contain linux/amd64 and linux/arm64 in order")
    publishing = data.get("publishing", {})
    if not isinstance(publishing, dict) or publishing.get("enabled") is not False:
        errors.append("publishing.enabled must be false in repository configuration")
    severity = data.get("security", {}).get("severity")
    if not isinstance(severity, list) or not severity or not set(severity) <= {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        errors.append("security.severity must be a non-empty list of valid levels")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=Path("config/pipeline.example.yaml"))
    args = parser.parse_args()
    errors = validate(args.path)
    if errors:
        print("\n".join(f"FAIL: {item}" for item in errors), file=sys.stderr)
        return 1
    print(f"Valid configuration: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
