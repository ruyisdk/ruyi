from contextlib import AbstractContextManager
import pathlib
from typing import Sequence, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from types import TracebackType
    from typing_extensions import Self

import tomlkit
from tomlkit.items import Table

from .errors import MalformedConfigFileError
from .schema import ensure_valid_config_kv, parse_config_key, validate_section

if TYPE_CHECKING:
    from . import GlobalConfig


class ConfigEditor(AbstractContextManager["ConfigEditor"]):
    def __init__(self, path: pathlib.Path) -> None:
        self._path = path
        self._touched = False
        try:
            with open(path) as fp:
                self._content = tomlkit.load(fp)
            if not isinstance(self._content, tomlkit.TOMLDocument):
                raise MalformedConfigFileError(path)
        except FileNotFoundError:
            self._content = tomlkit.document()

        self._stage = cast(tomlkit.TOMLDocument, self._content.copy())

    @classmethod
    def work_on_user_local_config(cls, gc: "GlobalConfig") -> "Self":
        return cls(gc.local_user_config_file)

    def __enter__(self) -> "Self":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: "TracebackType | None",
    ) -> bool | None:
        self._commit()
        return None

    def _commit(self) -> None:
        if not self._touched:
            return

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fp:
            tomlkit.dump(self._content, fp)

    def stage(self) -> None:
        self._content = self._stage
        self._touched = True
        self._stage = cast(tomlkit.TOMLDocument, self._content.copy())

    def set_value(self, key: str | Sequence[str], val: object | None) -> None:
        parsed_key = parse_config_key(key)
        ensure_valid_config_kv(parsed_key, check_val=True, val=val)

        section, sel = parsed_key[0], parsed_key[1:]
        if section in self._stage:
            existing_section = self._stage[section]
            if not isinstance(existing_section, Table):
                raise MalformedConfigFileError(self._path)
            existing_section.update({sel[0]: val})
        else:
            # append a section with its sole key set to val
            new_section = tomlkit.table()
            new_section.append(sel[0], val)
            self._stage.append(section, new_section)

    def unset_value(self, key: str | Sequence[str]) -> None:
        parsed_key = parse_config_key(key)
        ensure_valid_config_kv(parsed_key, check_val=False)

        section, sel = parsed_key[0], parsed_key[1:]
        if existing_section := self._stage.get(section):
            if not isinstance(existing_section, Table):
                raise MalformedConfigFileError(self._path)
            if sel[0] in existing_section:
                existing_section.pop(sel[0])

    def remove_section(self, section: str) -> None:
        validate_section(section)
        if section in self._stage:
            self._stage.pop(section)
