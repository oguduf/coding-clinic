"""Typed domain models shared by the AWS adapters and report generators."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


def parse_utc(value: str | datetime) -> datetime:
    """Parse an ISO-8601 timestamp and require an explicit UTC offset."""
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid ISO-8601 timestamp: {value!r}") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone offset")
    return result.astimezone(UTC)


def decimal_text(value: Decimal | None) -> str | None:
    return format(value, ".2f") if value is not None else None


@dataclass(frozen=True, slots=True)
class Account:
    account_id: str
    name: str
    status: str = "ACTIVE"
    environment: str = "unknown"


@dataclass(frozen=True, slots=True)
class Volume:
    account_id: str
    account_name: str
    environment: str
    region: str
    volume_id: str
    availability_zone: str
    volume_type: str
    size_gib: int
    create_time: datetime
    state: str
    tags: dict[str, str] = field(default_factory=dict)
    encrypted: bool = False
    kms_key_id: str | None = None
    iops: int | None = None
    throughput_mibps: int | None = None
    age_days: int = 0
    meets_age_threshold: bool = False
    eligible_for_review: bool = False
    exclusion_reason: str | None = None
    pricing_status: str = "unavailable"
    monthly_cost: Decimal | None = None
    pricing_source: str | None = None
    pricing_effective_date: str | None = None

    def __post_init__(self) -> None:
        if self.size_gib < 1:
            raise ValueError("EBS volume size must be positive")
        if self.iops is not None and self.iops < 0:
            raise ValueError("Provisioned IOPS cannot be negative")
        if self.throughput_mibps is not None and self.throughput_mibps < 0:
            raise ValueError("Provisioned throughput cannot be negative")
        if self.age_days < 0:
            raise ValueError("Volume age cannot be negative")

    @classmethod
    def from_aws(cls, raw: dict[str, Any], account: Account, region: str) -> Volume:
        try:
            attachments = raw.get("Attachments") or []
            state = str(raw.get("State", "unknown"))
            if attachments:
                state = "in-use"
            tags = {
                str(item["Key"]): str(item.get("Value", ""))
                for item in raw.get("Tags", [])
                if item.get("Key") is not None
            }
            return cls(
                account_id=account.account_id,
                account_name=account.name,
                environment=account.environment,
                region=region,
                volume_id=str(raw["VolumeId"]),
                availability_zone=str(raw.get("AvailabilityZone", "unknown")),
                volume_type=str(raw["VolumeType"]),
                size_gib=int(raw["Size"]),
                create_time=parse_utc(raw["CreateTime"]),
                state=state,
                tags=tags,
                encrypted=bool(raw.get("Encrypted", False)),
                kms_key_id=raw.get("KmsKeyId"),
                iops=int(raw["Iops"]) if raw.get("Iops") is not None else None,
                throughput_mibps=(
                    int(raw["Throughput"]) if raw.get("Throughput") is not None else None
                ),
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Malformed EBS volume response: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["create_time"] = self.create_time.isoformat().replace("+00:00", "Z")
        value["monthly_cost"] = decimal_text(self.monthly_cost)
        return value


@dataclass(frozen=True, slots=True)
class ScanError:
    scope: str
    target: str
    code: str
    message: str


@dataclass(slots=True)
class ScanResult:
    accounts_discovered: int = 0
    accounts_scanned: set[str] = field(default_factory=set)
    accounts_failed: set[str] = field(default_factory=set)
    regions_scanned: set[str] = field(default_factory=set)
    volumes_inspected: int = 0
    volumes: list[Volume] = field(default_factory=list)
    errors: list[ScanError] = field(default_factory=list)
    execution_mode: str = "fixture"
    reference_time: datetime | None = None

    @property
    def is_partial(self) -> bool:
        return bool(self.errors)
