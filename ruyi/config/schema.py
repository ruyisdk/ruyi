import datetime
from typing import Final, Sequence

from .errors import (
    InvalidConfigKeyError,
    InvalidConfigValueError,
    InvalidConfigValueTypeError,
)


def parse_config_key(key: str | Sequence[str]) -> list[str]:
    if isinstance(key, str):
        return key.split(".")
    return list(key)


SECTION_INSTALLATION: Final = "installation"
KEY_INSTALLATION_EXTERNALLY_MANAGED: Final = "externally_managed"

SECTION_PACKAGES: Final = "packages"
KEY_PACKAGES_PRERELEASES: Final = "prereleases"

SECTION_REPO: Final = "repo"
KEY_REPO_BRANCH: Final = "branch"
KEY_REPO_LOCAL: Final = "local"
KEY_REPO_REMOTE: Final = "remote"

SECTION_TELEMETRY: Final = "telemetry"
KEY_TELEMETRY_MODE: Final = "mode"
KEY_TELEMETRY_PM_TELEMETRY_URL: Final = "pm_telemetry_url"
KEY_TELEMETRY_UPLOAD_CONSENT: Final = "upload_consent"


def ensure_valid_config_kv(
    key: str | Sequence[str],
    check_val: bool = False,
    val: object | None = None,
) -> None:
    parsed_key = parse_config_key(key)
    if len(parsed_key) != 2:
        # for now there's no nested config option
        raise InvalidConfigKeyError(key)

    section, sel = parsed_key
    if section == SECTION_INSTALLATION:
        return _ensure_valid_section_installation_kv(key, sel, check_val, val)
    elif section == SECTION_PACKAGES:
        return _ensure_valid_section_packages_kv(key, sel, check_val, val)
    elif section == SECTION_REPO:
        return _ensure_valid_section_repo_kv(key, sel, check_val, val)
    elif section == SECTION_TELEMETRY:
        return _ensure_valid_section_telemetry_kv(key, sel, check_val, val)
    else:
        raise InvalidConfigKeyError(key)


def _ensure_value_type(
    key: str | Sequence[str],
    check_val: bool,
    val: object | None,
    expected: type,
) -> None:
    if check_val and not isinstance(val, expected):
        raise InvalidConfigValueTypeError(key, val, expected)


def _ensure_valid_section_installation_kv(
    key: str | Sequence[str],
    sel: str,
    check_val: bool,
    val: object | None,
) -> None:
    if sel == KEY_INSTALLATION_EXTERNALLY_MANAGED:
        return _ensure_value_type(key, check_val, val, bool)
    else:
        raise InvalidConfigKeyError(key)


def _ensure_valid_section_packages_kv(
    key: str | Sequence[str],
    sel: str,
    check_val: bool,
    val: object | None,
) -> None:
    if sel == KEY_PACKAGES_PRERELEASES:
        return _ensure_value_type(key, check_val, val, bool)
    else:
        raise InvalidConfigKeyError(key)


def _ensure_valid_section_repo_kv(
    key: str | Sequence[str],
    sel: str,
    check_val: bool,
    val: object | None,
) -> None:
    if sel == KEY_REPO_BRANCH:
        return _ensure_value_type(key, check_val, val, str)
    elif sel == KEY_REPO_LOCAL:
        return _ensure_value_type(key, check_val, val, str)
    elif sel == KEY_REPO_REMOTE:
        return _ensure_value_type(key, check_val, val, str)
    else:
        raise InvalidConfigKeyError(key)


def _ensure_valid_section_telemetry_kv(
    key: str | Sequence[str],
    sel: str,
    check_val: bool,
    val: object | None,
) -> None:
    if sel == KEY_TELEMETRY_MODE:
        _ensure_value_type(key, check_val, val, str)
        if check_val:
            if val not in ("local", "off", "on"):
                raise InvalidConfigValueError(key, val)
    elif sel == KEY_TELEMETRY_PM_TELEMETRY_URL:
        _ensure_value_type(key, check_val, val, str)
    elif sel == KEY_TELEMETRY_UPLOAD_CONSENT:
        _ensure_value_type(key, check_val, val, datetime.datetime)
    else:
        raise InvalidConfigKeyError(key)


def encode_value(v: object) -> str:
    """Encodes the given config value into a string representation suitable for
    display or storage into TOML config files."""

    if isinstance(v, bool):
        return "true" if v else "false"
    elif isinstance(v, int):
        return str(v)
    elif isinstance(v, str):
        return v
    elif isinstance(v, datetime.datetime):
        return v.isoformat()
    else:
        raise NotImplementedError(f"invalid type for config value: {type(v)}")
