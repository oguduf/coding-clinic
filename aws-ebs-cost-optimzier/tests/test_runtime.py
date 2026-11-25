from __future__ import annotations

from unittest.mock import Mock

from ebs_optimizer.runtime import scan_organization


def test_runtime_organization_failure_is_explicit():
    client = Mock()
    client.get_paginator.side_effect = RuntimeError("access denied")
    session = Mock()
    session.client.return_value = client
    result = scan_organization(session, role_name="InventoryRole", regions=["us-east-1"])
    assert result.is_partial
    assert result.errors[0].code == "ListAccountsFailed"


def test_runtime_scans_member_through_mocked_sts_and_ec2(account):
    org_paginator = Mock()
    org_paginator.paginate.return_value = [
        {"Accounts": [{"Id": account.account_id, "Name": account.name, "State": "ACTIVE"}]}
    ]
    organizations = Mock()
    organizations.get_paginator.return_value = org_paginator
    sts = Mock()
    sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "fake-access",
            "SecretAccessKey": "fake-secret",
            "SessionToken": "fake-token",
        }
    }
    management = Mock()
    management.client.side_effect = lambda name, **kwargs: (
        organizations if name == "organizations" else sts
    )

    volume_page = {
        "Volumes": [
            {
                "VolumeId": "vol-mock001",
                "VolumeType": "gp3",
                "Size": 1,
                "CreateTime": "2025-01-01T00:00:00Z",
                "State": "available",
                "AvailabilityZone": "us-east-1a",
                "Encrypted": True,
            }
        ]
    }
    paginator = Mock()
    paginator.paginate.return_value = [volume_page]
    ec2 = Mock()
    ec2.get_paginator.return_value = paginator
    member_session = Mock()
    member_session.client.return_value = ec2
    factory = Mock(return_value=member_session)

    result = scan_organization(
        management,
        role_name="InventoryRole",
        regions=["us-east-1"],
        session_factory=factory,
    )
    assert result.accounts_discovered == 1
    assert result.accounts_scanned == {account.account_id}
    assert result.volumes[0].volume_id == "vol-mock001"
    sts.assume_role.assert_called_once()
    factory.assert_called_once()


def test_runtime_assume_role_failure_marks_account_failed():
    org = Mock()
    page = Mock()
    page.paginate.return_value = [
        {"Accounts": [{"Id": "000000000101", "Name": "dev", "State": "ACTIVE"}]}
    ]
    org.get_paginator.return_value = page
    sts = Mock()
    sts.assume_role.side_effect = RuntimeError("AccessDenied")
    management = Mock()
    management.client.side_effect = lambda name, **kwargs: org if name == "organizations" else sts
    result = scan_organization(management, role_name="InventoryRole", regions=["us-east-1"])
    assert result.accounts_failed == {"000000000101"}
    assert result.errors[0].code == "AssumeRoleFailed"
