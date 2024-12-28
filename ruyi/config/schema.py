import datetime
import sys
from typing import Final, Sequence

from .errors import (
    InvalidConfigKeyError,
    InvalidConfigSectionError,
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


def validate_section(section: str) -> None:
    if section not in (
        SECTION_INSTALLATION,
        SECTION_PACKAGES,
        SECTION_REPO,
        SECTION_TELEMETRY,
    ):
        raise InvalidConfigSectionError(section)


def get_expected_type_for_config_key(key: str | Sequence[str]) -> type:
    parsed_key = parse_config_key(key)
    if len(parsed_key) != 2:
        # for now there's no nested config option
        raise InvalidConfigKeyError(key)

    section, sel = parsed_key
    if section == SECTION_INSTALLATION:
        return _get_expected_type_for_section_installation(sel)
    elif section == SECTION_PACKAGES:
        return _get_expected_type_for_section_packages(sel)
    elif section == SECTION_REPO:
        return _get_expected_type_for_section_repo(sel)
    elif section == SECTION_TELEMETRY:
        return _get_expected_type_for_section_telemetry(sel)
    else:
        raise InvalidConfigKeyError(key)


def _get_expected_type_for_section_installation(sel: str) -> type:
    if sel == KEY_INSTALLATION_EXTERNALLY_MANAGED:
        return bool
    else:
        raise InvalidConfigKeyError(sel)


def _get_expected_type_for_section_packages(sel: str) -> type:
    if sel == KEY_PACKAGES_PRERELEASES:
        return bool
    else:
        raise InvalidConfigKeyError(sel)


def _get_expected_type_for_section_repo(sel: str) -> type:
    if sel == KEY_REPO_BRANCH:
        return str
    elif sel == KEY_REPO_LOCAL:
        return str
    elif sel == KEY_REPO_REMOTE:
        return str
    else:
        raise InvalidConfigKeyError(sel)


def _get_expected_type_for_section_telemetry(sel: str) -> type:
    if sel == KEY_TELEMETRY_MODE:
        return str
    elif sel == KEY_TELEMETRY_PM_TELEMETRY_URL:
        return str
    elif sel == KEY_TELEMETRY_UPLOAD_CONSENT:
        return datetime.datetime
    else:
        raise InvalidConfigKeyError(sel)


def ensure_valid_config_kv(
    key: str | Sequence[str],
    check_val: bool = False,
    val: object | None = None,
) -> None:
    parsed_key = parse_config_key(key)
    if len(parsed_key) != 2:
        # for now there's no nested config option
        raise InvalidConfigKeyError(key)

    expected_type = get_expected_type_for_config_key(parsed_key)
    # validity of config key is already checked by get_expected_type_for_config_key
    _ensure_value_type(key, check_val, val, expected_type)

    if not check_val:
        return

    section, sel = parsed_key
    if section == SECTION_TELEMETRY:
        return _extra_validate_section_telemetry_kv(key, sel, val)


def _ensure_value_type(
    key: str | Sequence[str],
    check_val: bool,
    val: object | None,
    expected: type,
) -> None:
    if check_val and not isinstance(val, expected):
        raise InvalidConfigValueTypeError(key, val, expected)


def _extra_validate_section_telemetry_kv(
    key: str | Sequence[str],
    sel: str,
    val: object | None,
) -> None:
    if sel == KEY_TELEMETRY_MODE:
        # value type is already ensured earlier
        if val not in ("local", "off", "on"):
            raise InvalidConfigValueError(key, val)


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
        if v.tzinfo is None:
            raise ValueError("only timezone-aware datetimes are supported for safety")
        s = v.isoformat()
        if s.endswith("+00:00"):
            # use the shorter 'Z' suffix for UTC
            return f"{s[:-6]}Z"
        return s
    else:
        raise NotImplementedError(f"invalid type for config value: {type(v)}")


def decode_value(
    key: str | Sequence[str] | type,
    val: str,
) -> object:
    """Decodes the given string representation of a config value into a Python
    value, directed by type information implied by the config key."""

    if isinstance(key, type):
        expected_type = key
    else:
        expected_type = get_expected_type_for_config_key(key)

    if expected_type is bool:
        if val in ("true", "yes", "1"):
            return True
        elif val in ("false", "no", "0"):
            return False
        else:
            raise InvalidConfigValueError(key, val)
    elif expected_type is int:
        return int(val, 10)
    elif expected_type is str:
        return val
    elif expected_type is datetime.datetime:
        if sys.version_info < (3, 11) and val.endswith("Z"):
            # datetime.fromisoformat() did not support the 'Z' suffix until
            # Python 3.11
            val = f"{val[:-1]}+00:00"
        v = datetime.datetime.fromisoformat(val)
        return v.astimezone() if v.tzinfo is None else v
    else:
        raise NotImplementedError(f"invalid type for config value: {expected_type}")
