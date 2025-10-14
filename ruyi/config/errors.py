from os import PathLike
from typing import Any, Sequence


class InvalidConfigSectionError(Exception):
    def __init__(self, section: str) -> None:
        super().__init__()
        self._section = section

    def __str__(self) -> str:
        return f"invalid config section: {self._section}"

    def __repr__(self) -> str:
        return f"InvalidConfigSectionError({self._section!r})"


class InvalidConfigKeyError(Exception):
    def __init__(self, key: str | Sequence[str]) -> None:
        super().__init__()
        self._key = key

    def __str__(self) -> str:
        return f"invalid config key: {self._key}"

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
        return f"invalid value type for config key {self._key}: {type(self._val)}, expected {self._expected}"

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
        return (
            f"invalid config value for key {self._key} (type {self._typ}): {self._val}"
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
        return f"malformed config file: {self._path}"

    def __repr__(self) -> str:
        return f"MalformedConfigFileError({self._path:!r})"


class ProtectedGlobalConfigError(Exception):
    def __init__(self, key: str | Sequence[str]) -> None:
        super().__init__()
        self._key = key

    def __str__(self) -> str:
        return f"attempt to modify protected global config key: {self._key}"

    def __repr__(self) -> str:
        return f"ProtectedGlobalConfigError({self._key!r})"
