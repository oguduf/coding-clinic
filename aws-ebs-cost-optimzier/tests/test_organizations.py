from __future__ import annotations

from unittest.mock import Mock

import pytest

from ebs_optimizer.organizations import OrganizationsDiscoveryError, discover_accounts


def client_with_pages(pages):
    client = Mock()
    paginator = Mock()
    paginator.paginate.return_value = pages
    client.get_paginator.return_value = paginator
    return client


def test_discovers_one_and_multiple_active_accounts():
    client = client_with_pages(
        [
            {"Accounts": [{"Id": "000000000002", "Name": "two", "State": "ACTIVE"}]},
            {"Accounts": [{"Id": "000000000001", "Name": "one", "State": "ACTIVE"}]},
        ]
    )
    accounts = discover_accounts(client)
    assert [account.account_id for account in accounts] == ["000000000001", "000000000002"]
    client.get_paginator.assert_called_once_with("list_accounts")


def test_empty_organization_is_a_valid_empty_result():
    client = client_with_pages([{"Accounts": []}])
    assert discover_accounts(client) == []


def test_skips_suspended_closed_and_malformed_accounts():
    client = client_with_pages(
        [
            {
                "Accounts": [
                    {"Id": "000000000001", "Name": "suspended", "Status": "SUSPENDED"},
                    {"Id": "000000000002", "Name": "closed", "Status": "CLOSED"},
                ]
            }
        ]
    )
    assert discover_accounts(client) == []
    malformed = client_with_pages([{"Accounts": [{"Name": "missing id", "Status": "ACTIVE"}]}])
    with pytest.raises(OrganizationsDiscoveryError, match="list_accounts failed"):
        discover_accounts(malformed)


def test_include_and_exclude_filters_are_applied():
    client = client_with_pages(
        [
            {
                "Accounts": [
                    {"Id": "000000000001", "Name": "one", "Status": "ACTIVE"},
                    {"Id": "000000000002", "Name": "two", "Status": "ACTIVE"},
                    {"Id": "000000000003", "Name": "three", "Status": "ACTIVE"},
                ]
            }
        ]
    )
    result = discover_accounts(
        client, include=["000000000001", "000000000002"], exclude=["000000000002"]
    )
    assert [account.account_id for account in result] == ["000000000001"]


def test_organizations_api_error_is_not_silently_suppressed():
    client = Mock()
    client.get_paginator.side_effect = RuntimeError("denied")
    with pytest.raises(OrganizationsDiscoveryError, match="Organizations account paginator"):
        discover_accounts(client)
