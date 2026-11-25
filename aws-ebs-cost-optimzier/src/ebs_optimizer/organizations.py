"""AWS Organizations account discovery adapter."""

from __future__ import annotations

from collections.abc import Iterable

from .models import Account


class OrganizationsDiscoveryError(RuntimeError):
    """AWS Organizations account enumeration failed."""


def discover_accounts(
    client: object,
    *,
    include: Iterable[str] | None = None,
    exclude: Iterable[str] = (),
) -> list[Account]:
    """List active accounts with boto3 pagination and deterministic ordering."""
    include_ids = set(include or ())
    exclude_ids = set(exclude)
    try:
        paginator = client.get_paginator("list_accounts")
    except Exception as exc:
        raise OrganizationsDiscoveryError("Cannot create Organizations account paginator") from exc
    accounts: list[Account] = []
    try:
        for page in paginator.paginate():
            for raw in page.get("Accounts", []):
                account_id = str(raw.get("Id", ""))
                status = str(raw.get("State", raw.get("Status", "UNKNOWN"))).upper()
                if status != "ACTIVE":
                    continue
                if not account_id.isdigit() or len(account_id) != 12:
                    raise ValueError("Organizations returned a malformed active account identifier")
                if include_ids and account_id not in include_ids:
                    continue
                if account_id in exclude_ids:
                    continue
                accounts.append(
                    Account(
                        account_id=account_id,
                        name=str(raw.get("Name", account_id)),
                        status=status,
                        environment="unknown",
                    )
                )
    except Exception as exc:
        raise OrganizationsDiscoveryError("Organizations list_accounts failed") from exc
    return sorted(accounts, key=lambda account: account.account_id)
