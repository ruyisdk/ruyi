import datetime

import pytest

from ruyi.config.errors import InvalidConfigValueError
from ruyi.config.schema import decode_value, encode_value


def test_decode_value_bool() -> None:
    assert decode_value("installation.externally_managed", "true") is True
    assert decode_value("installation.externally_managed", "false") is False
    assert decode_value("installation.externally_managed", "yes") is True
    assert decode_value("installation.externally_managed", "no") is False
    assert decode_value("installation.externally_managed", "1") is True
    assert decode_value("installation.externally_managed", "0") is False
    with pytest.raises(InvalidConfigValueError):
        decode_value("installation.externally_managed", "invalid")
    with pytest.raises(InvalidConfigValueError):
        decode_value("installation.externally_managed", "x")
    with pytest.raises(InvalidConfigValueError):
        decode_value("installation.externally_managed", "True")


def test_decode_value_str() -> None:
    assert decode_value("repo.branch", "main") == "main"


def test_decode_value_datetime() -> None:
    tz_aware_dt = datetime.datetime(2024, 12, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    assert (
        decode_value("telemetry.upload_consent", "2024-12-01T12:00:00Z") == tz_aware_dt
    )

    # naive datetimes are decoded using the implicit local timezone
    decode_value("telemetry.upload_consent", "2024-12-01T12:00:00")


def test_encode_value_bool() -> None:
    assert encode_value(True) == "true"
    assert encode_value(False) == "false"


def test_encode_value_int() -> None:
    assert encode_value(123) == "123"


def test_encode_value_str() -> None:
    assert encode_value("") == ""
    assert encode_value("main") == "main"


def test_encode_value_datetime() -> None:
    tz_aware_dt = datetime.datetime(2024, 12, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    assert encode_value(tz_aware_dt) == "2024-12-01T12:00:00+00:00"

    # specifically check that naive datetimes are rejected
    tz_naive_dt = datetime.datetime(2024, 12, 1, 12, 0, 0)
    with pytest.raises(
        ValueError, match="only timezone-aware datetimes are supported for safety"
    ):
        encode_value(tz_naive_dt)
