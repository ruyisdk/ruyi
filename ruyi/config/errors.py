from os import PathLike
from typing import Any, Sequence

from ..i18n import _


class InvalidConfigSectionError(Exception):
    def __init__(self, section: str) -> None:
        super().__init__()
        self._section = section

    def __str__(self) -> str:
        return _("invalid config section: {section}").format(section=self._section)

    def __repr__(self) -> str:
        return f"InvalidConfigSectionError({self._section!r})"


class InvalidConfigKeyError(Exception):
    def __init__(self, key: str | Sequence[str]) -> None:
        super().__init__()
        self._key = key

    def __str__(self) -> str:
        return _("invalid config key: {key}").format(key=self._key)

    def __repr__(self) -> str:
        return f"InvalidConfigKeyError({self._key:!r})"


class InvalidConfigValueTypeError(TypeError):
    def __init__(
        self,
        key: str | Sequence[str],
        val: object | None,
        expected: type | Sequence[type],
    ) -> None:
        super().__init__()
        self._key = key
        self._val = val
        self._expected = expected

    def __str__(self) -> str:
        return _(
            "invalid value type for config key {key}: {actual_type}, expected {expected_type}"
        ).format(
            key=self._key,
            actual_type=type(self._val),
            expected_type=self._expected,
        )

    def __repr__(self) -> str:
        return f"InvalidConfigValueTypeError({self._key!r}, {self._val!r}, {self._expected:!r})"


class InvalidConfigValueError(ValueError):
    def __init__(
        self,
        key: str | Sequence[str] | None,
        val: object | None,
        typ: type | Sequence[type],
    ) -> None:
        super().__init__()
        self._key = key
        self._val = val
        self._typ = typ

    def __str__(self) -> str:
        return _("invalid config value for key {key} (type {typ}): {val}").format(
            key=self._key,
            typ=self._typ,
            val=self._val,
        )

    def __repr__(self) -> str:
        return (
            f"InvalidConfigValueError({self._key:!r}, {self._val:!r}, {self._typ:!r})"
        )


class MalformedConfigFileError(Exception):
    def __init__(self, path: PathLike[Any]) -> None:
        super().__init__()
        self._path = path

    def __str__(self) -> str:
        return _("malformed config file: {path}").format(path=self._path)

    def __repr__(self) -> str:
        return f"MalformedConfigFileError({self._path:!r})"


class ProtectedGlobalConfigError(Exception):
    def __init__(self, key: str | Sequence[str]) -> None:
        super().__init__()
        self._key = key

    def __str__(self) -> str:
        return _("attempt to modify protected global config key: {key}").format(
            key=self._key,
        )

    def __repr__(self) -> str:
        return f"ProtectedGlobalConfigError({self._key!r})"
