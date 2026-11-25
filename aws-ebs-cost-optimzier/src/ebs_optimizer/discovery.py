"""Read-only EC2 region and EBS volume discovery adapters."""

from __future__ import annotations

from collections.abc import Iterable

from botocore.config import Config

from .models import Account, ScanError, Volume

RETRY_CONFIG = Config(retries={"mode": "standard", "max_attempts": 8})
REGION_DISCOVERY_REGION = "us-east-1"


def enabled_regions(ec2_client: object) -> list[str]:
    response = ec2_client.describe_regions(AllRegions=False)
    return sorted(
        region["RegionName"] for region in response.get("Regions", []) if region.get("RegionName")
    )


def discover_volumes(
    session: object,
    account: Account,
    regions: Iterable[str] | None,
) -> tuple[list[Volume], list[ScanError], set[str]]:
    """Collect all volume pages; isolate errors to the affected region."""
    errors: list[ScanError] = []
    volumes: list[Volume] = []
    scanned: set[str] = set()
    try:
        target_regions = (
            list(regions)
            if regions
            else enabled_regions(
                session.client("ec2", region_name=REGION_DISCOVERY_REGION, config=RETRY_CONFIG)
            )
        )
    except Exception as exc:
        response = getattr(exc, "response", {})
        code = response.get("Error", {}).get("Code", type(exc).__name__)
        error = ScanError("region", f"{account.account_id}/region-discovery", code, str(exc))
        return [], [error], set()
    for region in sorted(set(target_regions)):
        try:
            client = session.client("ec2", region_name=region, config=RETRY_CONFIG)
            paginator = client.get_paginator("describe_volumes")
            for page in paginator.paginate(Filters=[{"Name": "status", "Values": ["available"]}]):
                for raw in page.get("Volumes", []):
                    volume = Volume.from_aws(raw, account, region)
                    if volume.state == "available" and not raw.get("Attachments"):
                        volumes.append(volume)
            scanned.add(region)
        except Exception as exc:  # one bad region should not hide other results
            response = getattr(exc, "response", {})
            code = response.get("Error", {}).get("Code", type(exc).__name__)
            errors.append(ScanError("region", f"{account.account_id}/{region}", code, str(exc)))
    return sorted(volumes, key=lambda v: (v.account_id, v.region, v.volume_id)), errors, scanned
