# Re-implementation of necessary XDG Base Directory Specification semantics
# without pyxdg, which is under LGPL and not updated for the latest spec
# revision (0.6 vs 0.8 released in 2021).

import os
import pathlib
from typing import Iterable, NamedTuple


class XDGPathEntry(NamedTuple):
    path: pathlib.Path
    is_global: bool


def _paths_from_env(env: str, default: str) -> Iterable[pathlib.Path]:
    v = os.environ.get(env, default)
    for p in v.split(":"):
        yield pathlib.Path(p)


class XDGBaseDir:
    def __init__(self, app_name: str) -> None:
        self.app_name = app_name

    @property
    def cache_home(self) -> pathlib.Path:
        v = os.environ.get("XDG_CACHE_HOME", "")
        return pathlib.Path(v) if v else pathlib.Path.home() / ".cache"

    @property
    def config_home(self) -> pathlib.Path:
        v = os.environ.get("XDG_CONFIG_HOME", "")
        return pathlib.Path(v) if v else pathlib.Path.home() / ".config"

    @property
    def data_home(self) -> pathlib.Path:
        v = os.environ.get("XDG_DATA_HOME", "")
        return pathlib.Path(v) if v else pathlib.Path.home() / ".local" / "share"

    @property
    def state_home(self) -> pathlib.Path:
        v = os.environ.get("XDG_STATE_HOME", "")
        return pathlib.Path(v) if v else pathlib.Path.home() / ".local" / "state"

    @property
    def config_dirs(self) -> Iterable[XDGPathEntry]:
        # from highest precedence to lowest
        for p in _paths_from_env("XDG_CONFIG_DIRS", "/etc/xdg"):
            yield XDGPathEntry(p, True)

    @property
    def data_dirs(self) -> Iterable[XDGPathEntry]:
        # from highest precedence to lowest
        for p in _paths_from_env("XDG_DATA_DIRS", "/usr/local/share/:/usr/share/"):
            yield XDGPathEntry(p, True)

    # derived info

    @property
    def app_cache(self) -> pathlib.Path:
        return self.cache_home / self.app_name

    @property
    def app_config(self) -> pathlib.Path:
        return self.config_home / self.app_name

    @property
    def app_data(self) -> pathlib.Path:
        return self.data_home / self.app_name

    @property
    def app_state(self) -> pathlib.Path:
        return self.state_home / self.app_name

    @property
    def app_config_dirs(self) -> Iterable[XDGPathEntry]:
        # from highest precedence to lowest
        yield XDGPathEntry(self.app_config, False)
        for e in self.config_dirs:
            yield XDGPathEntry(e.path / self.app_name, e.is_global)

    @property
    def app_data_dirs(self) -> Iterable[XDGPathEntry]:
        # from highest precedence to lowest
        yield XDGPathEntry(self.app_data, False)
        for e in self.data_dirs:
            yield XDGPathEntry(e.path / self.app_name, e.is_global)
