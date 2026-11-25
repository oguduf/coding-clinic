"""Explicit, injectable AWS orchestration adapter; never called by the CLI."""

from __future__ import annotations

from botocore.config import Config

from .assume_role import RoleAssumptionError, assume_account_role
from .discovery import discover_volumes
from .models import ScanError, ScanResult
from .organizations import OrganizationsDiscoveryError, discover_accounts


def scan_organization(
    management_session: object,
    *,
    role_name: str,
    regions: list[str] | None,
    include_accounts: list[str] | None = None,
    exclude_accounts: list[str] | None = None,
    session_factory: object | None = None,
) -> ScanResult:
    """Run a read-only scan using injected sessions; callers own authorization."""
    result = ScanResult(execution_mode="live-adapter")
    try:
        accounts = discover_accounts(
            management_session.client(
                "organizations", config=Config(retries={"mode": "standard", "max_attempts": 8})
            ),
            include=include_accounts,
            exclude=exclude_accounts or (),
        )
    except OrganizationsDiscoveryError as exc:
        result.errors.append(
            ScanError("organization", "management-account", "ListAccountsFailed", str(exc))
        )
        return result
    result.accounts_discovered = len(accounts)
    for account in accounts:
        try:
            factory = session_factory
            if factory is None:
                import boto3

                factory = boto3.Session
            member_session = assume_account_role(
                management_session.client(
                    "sts", config=Config(retries={"mode": "standard", "max_attempts": 8})
                ),
                account.account_id,
                role_name,
                session_factory=factory,
            )
        except RoleAssumptionError as exc:
            result.accounts_failed.add(account.account_id)
            result.errors.append(
                ScanError("account", account.account_id, "AssumeRoleFailed", str(exc))
            )
            continue
        volumes, errors, scanned = discover_volumes(member_session, account, regions)
        result.volumes.extend(volumes)
        result.volumes_inspected += len(volumes)
        result.regions_scanned.update(scanned)
        result.errors.extend(errors)
        if any(error.scope == "region" for error in errors):
            result.accounts_failed.add(account.account_id)
        else:
            result.accounts_scanned.add(account.account_id)
    result.volumes.sort(key=lambda v: (v.account_id, v.region, v.volume_id))
    return result
