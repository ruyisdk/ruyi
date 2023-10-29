import os.path
import tomllib
from typing import Any, Self

from xdg import BaseDirectory


class RuyiConfig:
    resource_name = "ruyi"

    def __init__(self) -> None:
        # all defaults
        self.override_repo_dir: str | None = None

    def get_repo_dir(self) -> str:
        return self.override_repo_dir or os.path.join(self.ensure_cache_dir(), "repo")

    @classmethod
    def init_from_config_data(cls, data: dict[str, Any]) -> Self:
        obj = cls()
        # TODO: read from data and override defaults
        return obj

    @classmethod
    def ensure_data_dir(cls) -> str:
        return BaseDirectory.save_data_path(cls.resource_name)

    @classmethod
    def get_first_data_dir(cls) -> str | None:
        for p in BaseDirectory.load_data_paths(cls.resource_name):
            return p

    @classmethod
    def ensure_config_dir(cls) -> str:
        return BaseDirectory.save_config_path(cls.resource_name)

    @classmethod
    def ensure_cache_dir(cls) -> str:
        return BaseDirectory.save_cache_path(cls.resource_name)

    @classmethod
    def get_config_file(cls) -> str | None:
        # TODO: maybe allow customization of config root
        config_dir = BaseDirectory.load_first_config(cls.resource_name)
        if config_dir is None:
            return None
        return os.path.join(config_dir, "config.toml")

    @classmethod
    def load_from_config(cls) -> Self:
        config_path = cls.get_config_file()
        if config_path is None:
            return cls()

        with open(config_path, "rb") as fp:
            return cls.init_from_config_data(tomllib.load(fp))
