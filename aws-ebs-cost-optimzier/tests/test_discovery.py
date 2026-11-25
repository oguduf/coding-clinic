from __future__ import annotations

from unittest.mock import Mock

from ebs_optimizer.discovery import discover_volumes, enabled_regions


def raw_volume(volume_id="vol-synthetic001", state="available"):
    return {
        "VolumeId": volume_id,
        "VolumeType": "gp3",
        "Size": 10,
        "CreateTime": "2025-01-01T00:00:00Z",
        "State": state,
        "AvailabilityZone": "us-east-1a",
        "Encrypted": True,
        "Tags": [{"Key": "Owner", "Value": "lab"}],
    }


class Paginator:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def paginate(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.pages)


class FakeEC2:
    def __init__(self, pages=None, failure=None, regions=None):
        self.paginator = Paginator(pages or [])
        self.failure = failure
        self.regions = regions or []

    def get_paginator(self, operation):
        assert operation == "describe_volumes"
        if self.failure:
            raise self.failure
        return self.paginator

    def describe_regions(self, **kwargs):
        return {"Regions": [{"RegionName": r} for r in self.regions]}


class FakeSession:
    def __init__(self, clients):
        self.clients = clients
        self.requests = []

    def client(self, service, **kwargs):
        self.requests.append((service, kwargs))
        if "region_name" in kwargs:
            return self.clients[kwargs["region_name"]]
        return self.clients["discovery"]


def test_enabled_regions_are_sorted_and_only_names_returned():
    assert enabled_regions(FakeEC2(regions=["us-west-2", "us-east-1"])) == [
        "us-east-1",
        "us-west-2",
    ]


def test_available_volumes_paginate_and_collect_metadata(account):
    paginator = Paginator(
        [{"Volumes": [raw_volume()]}, {"Volumes": [raw_volume("vol-synthetic002")]}]
    )
    client = FakeEC2()
    client.get_paginator = lambda operation: paginator
    session = FakeSession({"us-east-1": client})
    volumes, errors, regions = discover_volumes(session, account, ["us-east-1"])
    assert len(volumes) == 2
    assert volumes[0].account_id == account.account_id
    assert volumes[0].encrypted is True
    assert errors == []
    assert regions == {"us-east-1"}
    assert paginator.calls[0]["Filters"] == [{"Name": "status", "Values": ["available"]}]


def test_region_failure_is_partial_and_other_region_continues(account):
    good = FakeEC2([{"Volumes": [raw_volume()]}])
    bad = FakeEC2(failure=RuntimeError("throttled"))
    session = FakeSession({"us-east-1": good, "us-west-2": bad})
    volumes, errors, regions = discover_volumes(session, account, ["us-east-1", "us-west-2"])
    assert len(volumes) == 1
    assert len(errors) == 1
    assert errors[0].target == f"{account.account_id}/us-west-2"
    assert regions == {"us-east-1"}


def test_enabled_region_discovery_failure_returns_error(account):
    discovery = FakeEC2()
    discovery.describe_regions = Mock(side_effect=RuntimeError("denied"))
    volumes, errors, regions = discover_volumes(
        FakeSession({"discovery": discovery}), account, None
    )
    assert volumes == [] and regions == set()
    assert errors[0].target.endswith("region-discovery")


def test_empty_volume_response_is_success(account):
    session = FakeSession({"us-east-1": FakeEC2([{"Volumes": []}])})
    volumes, errors, regions = discover_volumes(session, account, ["us-east-1"])
    assert volumes == [] and errors == [] and regions == {"us-east-1"}
