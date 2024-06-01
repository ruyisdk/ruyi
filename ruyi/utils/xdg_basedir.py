# Re-implementation of necessary XDG Base Directory Specification semantics
# without pyxdg, which is under LGPL and not updated for the latest spec
# revision (0.6 vs 0.8 released in 2021).

import os
import pathlib
from typing import Iterable


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
    def config_dirs(self) -> Iterable[pathlib.Path]:
        # from highest precedence to lowest
        yield from _paths_from_env("XDG_CONFIG_DIRS", "/etc/xdg")

    @property
    def data_dirs(self) -> Iterable[pathlib.Path]:
        # from highest precedence to lowest
        yield from _paths_from_env("XDG_DATA_DIRS", "/usr/local/share/:/usr/share/")

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
    def app_config_dirs(self) -> Iterable[pathlib.Path]:
        # from highest precedence to lowest
        yield self.app_config
        for p in self.config_dirs:
            yield p / self.app_name

    @property
    def app_data_dirs(self) -> Iterable[pathlib.Path]:
        # from highest precedence to lowest
        yield self.app_data
        for p in self.data_dirs:
            yield p / self.app_name
