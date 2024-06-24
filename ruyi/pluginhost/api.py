import pathlib
import tomllib
from typing import Callable

from ruyi.cli.version import RUYI_SEMVER
from . import resolve_ruyi_load_path


class RuyiHostAPI:
    def __init__(
        self,
        plugin_root: pathlib.Path,
        this_file: pathlib.Path,
        this_plugin_dir: pathlib.Path,
    ) -> None:
        self._plugin_root = plugin_root
        self._this_file = this_file
        self._this_plugin_dir = this_plugin_dir

    @property
    def ruyi_version(self) -> str:
        return str(RUYI_SEMVER)

    @property
    def ruyi_plugin_api_rev(self) -> int:
        return 1

    def load_toml(self, path: str) -> object:
        resolved_path = resolve_ruyi_load_path(
            path,
            self._plugin_root,
            True,
            self._this_file,
        )
        with open(resolved_path, "rb") as f:
            return tomllib.load(f)


def _ruyi_plugin_rev(
    plugin_root: pathlib.Path,
    this_file: pathlib.Path,
    this_plugin_dir: pathlib.Path,
    rev: object,
) -> RuyiHostAPI:
    if not isinstance(rev, int):
        raise TypeError("rev must be int in ruyi_plugin_rev calls")
    if rev != 1:
        raise ValueError(
            f"Ruyi plugin API revision {rev} is not supported by this Ruyi"
        )
    return RuyiHostAPI(plugin_root, this_file, this_plugin_dir)


def make_ruyi_plugin_api_for_module(
    plugin_root: pathlib.Path,
    this_file: pathlib.Path,
    this_plugin_dir: pathlib.Path,
) -> Callable[[object], RuyiHostAPI]:
    return lambda rev: _ruyi_plugin_rev(plugin_root, this_file, this_plugin_dir, rev)
