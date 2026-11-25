from __future__ import annotations

from unittest.mock import Mock

import pytest

from ebs_optimizer.assume_role import RoleAssumptionError, assume_account_role


def test_assumes_temporary_role_and_returns_session():
    sts = Mock()
    sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "temporary-access",
            "SecretAccessKey": "temporary-secret",
            "SessionToken": "temporary-token",
        }
    }
    factory = Mock(return_value="session")
    result = assume_account_role(sts, "000000000101", "InventoryRole", session_factory=factory)
    assert result == "session"
    kwargs = sts.assume_role.call_args.kwargs
    assert kwargs["RoleArn"] == "arn:aws:iam::000000000101:role/InventoryRole"
    assert kwargs["DurationSeconds"] == 900
    assert factory.call_args.kwargs["aws_session_token"] == "temporary-token"


@pytest.mark.parametrize("code", ["AccessDenied", "ExpiredToken", "NoSuchEntity"])
def test_sts_failures_raise_safe_error_without_secret(code):
    sts = Mock()
    error = RuntimeError("credential material should not be disclosed")
    error.response = {"Error": {"Code": code}}
    sts.assume_role.side_effect = error
    with pytest.raises(RoleAssumptionError) as caught:
        assume_account_role(sts, "000000000101", "InventoryRole")
    assert code in str(caught.value)
    assert "credential material" not in str(caught.value)


@pytest.mark.parametrize("account_id", ["123", "not-an-id", "00000000010x"])
def test_invalid_account_ids_rejected(account_id):
    with pytest.raises(ValueError):
        assume_account_role(Mock(), account_id, "InventoryRole")


def test_invalid_role_name_rejected():
    with pytest.raises(ValueError):
        assume_account_role(Mock(), "000000000101", "path/Role")
