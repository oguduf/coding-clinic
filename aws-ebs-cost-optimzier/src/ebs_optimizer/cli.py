"""Offline fixture CLI; intentionally exposes no live-scan or delete command."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from .config import ConfigurationError, load_config, load_json
from .deletion_plan import build_deletion_plan
from .filters import apply_age_filter, apply_cleanup_policy
from .logging_config import configure_logging
from .models import Account, ScanError, ScanResult, Volume, parse_utc
from .pricing import add_pricing, validate_pricing
from .reporting import build_report, write_reports


def _formats(value: str) -> list[str]:
    choices = [part.strip().lower() for part in value.split(",") if part.strip()]
    if not choices or set(choices) - {"csv", "json", "markdown"}:
        raise argparse.ArgumentTypeError("formats must be csv,json,markdown (any subset)")
    return list(dict.fromkeys(choices))


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        prog="ebs-optimizer",
        description="Offline-first EBS cost report generator. No live AWS mode is exposed.",
    )
    cli.add_argument("--fixture", type=Path, default=Path("examples/sample_organization.json"))
    cli.add_argument("--config", type=Path, default=Path("config/config.example.yaml"))
    cli.add_argument("--pricing", type=Path, default=Path("config/pricing.example.json"))
    cli.add_argument("--min-age-days", type=int)
    cli.add_argument("--format", type=_formats)
    cli.add_argument("--output-dir", type=Path)
    cli.add_argument(
        "--reference-time", help="ISO-8601 timestamp with timezone; makes age repeatable"
    )
    cli.add_argument("--generate-deletion-plan", action="store_true")
    return cli


def _fixture_scan(
    path: Path,
    *,
    include_accounts: list[str] | None = None,
    exclude_accounts: list[str] | None = None,
) -> tuple[ScanResult, list[Volume]]:
    fixture = load_json(path)
    accounts_raw = fixture.get("accounts")
    if not isinstance(accounts_raw, list):
        raise ConfigurationError("Fixture must contain an accounts list")
    result = ScanResult(execution_mode="offline-fixture")
    result.accounts_discovered = len(accounts_raw)
    result.reference_time = (
        parse_utc(fixture["reference_time"]) if fixture.get("reference_time") else None
    )
    parsed: list[Volume] = []
    include_set = set(include_accounts or [])
    exclude_set = set(exclude_accounts or [])
    for raw_account in accounts_raw:
        if not isinstance(raw_account, dict):
            raise ConfigurationError("Each fixture account must be a JSON object")
        account_id = str(raw_account.get("account_id", ""))
        status = str(raw_account.get("status", "ACTIVE")).upper()
        if (
            status != "ACTIVE"
            or (include_set and account_id not in include_set)
            or account_id in exclude_set
        ):
            continue
        if not isinstance(raw_account.get("volumes", []), list):
            raise ConfigurationError(f"Fixture volumes must be a list for account {account_id}")
        account = Account(
            account_id=account_id,
            name=str(raw_account.get("name", account_id)),
            status=status,
            environment=str(raw_account.get("environment", "unknown")),
        )
        account_failed = False
        for raw_volume in raw_account.get("volumes", []):
            result.volumes_inspected += 1
            if not isinstance(raw_volume, dict):
                account_failed = True
                result.errors.append(
                    ScanError(
                        "volume",
                        f"{account_id}/unknown",
                        "MalformedFixture",
                        "Volume must be a JSON object",
                    )
                )
                continue
            region = str(raw_volume.get("Region", ""))
            if region:
                result.regions_scanned.add(region)
            try:
                volume = Volume.from_aws(raw_volume, account, region)
                if volume.state == "available":
                    parsed.append(volume)
            except (ValueError, TypeError) as exc:
                account_failed = True
                result.errors.append(
                    ScanError("volume", f"{account_id}/{region}", "MalformedFixture", str(exc))
                )
        if account_failed:
            result.accounts_failed.add(account_id)
        else:
            result.accounts_scanned.add(account_id)
    result.volumes = sorted(parsed, key=lambda v: (v.account_id, v.region, v.volume_id))
    return result, result.volumes


def run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    configure_logging(config.get("application", {}).get("log_level", "INFO"))
    logger = logging.getLogger("ebs_optimizer")
    logger.info("scan started", extra={"fields": {"execution_mode": "offline-fixture"}})
    pricing = validate_pricing(load_json(args.pricing))
    aws_config = config.get("aws", {})
    result, volumes = _fixture_scan(
        args.fixture,
        include_accounts=aws_config.get("included_accounts"),
        exclude_accounts=aws_config.get("excluded_accounts"),
    )
    reference = (
        parse_utc(args.reference_time)
        if args.reference_time
        else result.reference_time or datetime.now(UTC)
    )
    result.reference_time = reference
    age_days = (
        args.min_age_days
        if args.min_age_days is not None
        else config["discovery"]["minimum_age_days"]
    )
    if isinstance(age_days, bool) or age_days < 0:
        raise ConfigurationError("--min-age-days must be zero or greater")
    aged = apply_age_filter(volumes, age_days, reference)
    priced = add_pricing(aged, pricing)
    policies = config.get("deletion_plan", {})
    processed = apply_cleanup_policy(
        priced,
        exclude_production=bool(policies.get("exclude_production", True)),
        protected_tags=policies.get("protected_tags", {}),
    )
    result.volumes = processed
    formats = args.format or config["reporting"]["formats"]
    output_dir = args.output_dir or Path(config["reporting"]["output_directory"])
    report = build_report(result, age_days)
    paths = write_reports(report, output_dir, formats)
    if args.generate_deletion_plan or policies.get("enabled", False):
        plan_path = output_dir / "ebs-deletion-review-plan.json"
        from .reporting import _atomic_write

        _atomic_write(
            plan_path, json.dumps(build_deletion_plan(processed), indent=2, sort_keys=True) + "\n"
        )
        paths.append(plan_path)
    logger = logging.getLogger("ebs_optimizer")
    logger.info(
        "offline scan complete",
        extra={"fields": {"accounts": len(result.accounts_scanned), "volumes": len(processed)}},
    )
    coverage = report["coverage"]
    print(
        "Mode: offline fixture | "
        f"accounts: {coverage['accounts_scanned']}/{coverage['accounts_discovered']} | "
        f"unattached: {coverage['unattached_volumes_found']} | "
        f"review candidates: {coverage['review_candidates']} | "
        f"estimated monthly USD: {coverage['estimated_monthly_candidate_cost_usd']}"
    )
    for path in paths:
        print(f"Wrote {path}")
    logger.info(
        "reports generated",
        extra={"fields": {"formats": formats, "report_count": len(paths)}},
    )
    logger.log(
        logging.WARNING if result.is_partial else logging.INFO,
        "scan completed",
        extra={
            "fields": {
                "execution_mode": "offline-fixture",
                "accounts_processed": len(result.accounts_scanned),
                "regions_processed": len(result.regions_scanned),
                "errors": len(result.errors),
                "coverage_complete": not result.is_partial,
            }
        },
    )
    return 2 if result.is_partial else 0


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    configure_logging("INFO")
    try:
        return run(args)
    except (ConfigurationError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
