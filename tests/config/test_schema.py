import datetime

import pytest

from ruyi.config.errors import InvalidConfigValueError
from ruyi.config.schema import decode_value, encode_value, _decode_single_type_value
from ruyi.utils.toml import NoneValue


def test_decode_value_bool() -> None:
    assert decode_value("installation.externally_managed", "true") is True

    assert _decode_single_type_value(None, "true", bool) is True
    assert _decode_single_type_value(None, "false", bool) is False
    assert _decode_single_type_value(None, "yes", bool) is True
    assert _decode_single_type_value(None, "no", bool) is False
    assert _decode_single_type_value(None, "1", bool) is True
    assert _decode_single_type_value(None, "0", bool) is False
    with pytest.raises(InvalidConfigValueError):
        _decode_single_type_value(None, "invalid", bool)
    with pytest.raises(InvalidConfigValueError):
        _decode_single_type_value(None, "x", bool)
    with pytest.raises(InvalidConfigValueError):
        _decode_single_type_value(None, "True", bool)


def test_decode_value_str() -> None:
    assert decode_value("repo.branch", "main") == "main"
    assert _decode_single_type_value(None, "main", str) == "main"


def test_decode_value_datetime() -> None:
    tz_aware_dt = datetime.datetime(2024, 12, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    assert (
        decode_value("telemetry.upload_consent", "2024-12-01T12:00:00Z") == tz_aware_dt
    )
    assert (
        _decode_single_type_value(None, "2024-12-01T12:00:00Z", datetime.datetime)
        == tz_aware_dt
    )
    assert (
        _decode_single_type_value(None, "2024-12-01T12:00:00+00:00", datetime.datetime)
        == tz_aware_dt
    )

    # naive datetimes are decoded using the implicit local timezone
    _decode_single_type_value(None, "2024-12-01T12:00:00", datetime.datetime)


def test_encode_value_none() -> None:
    with pytest.raises(NoneValue):
        encode_value(None)


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
    assert encode_value(tz_aware_dt) == "2024-12-01T12:00:00Z"

    # specifically check that naive datetimes are rejected
    tz_naive_dt = datetime.datetime(2024, 12, 1, 12, 0, 0)
    with pytest.raises(
        ValueError, match="only timezone-aware datetimes are supported for safety"
    ):
        encode_value(tz_naive_dt)
